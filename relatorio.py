# -*- coding: utf-8 -*-
"""
Gera o relatório dos testes (.docx) no formato ABNT para o TCC.

Chamado pelo botão "Gerar relatório" da página de testes, mas também pode
ser rodado direto (usa relatorio_config.json e testes.json):
    python relatorio.py
"""

import io
import os
import json
import time

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.shared import Cm, Pt, RGBColor

from cadastrar import BASE_DIR
from casos_teste import (
    CASOS, VISITANTE, calcular_metricas, metricas_por,
    carregar_resultados,
)

RELATORIO_PATH = os.path.join(BASE_DIR, "relatorio_tcc.docx")
NOMES_DECISAO = {"liberado": "Liberado", "negado": "Negado",
                 "sem_decisao": "Sem decisão"}


def pct(v):
    return "–" if v is None else f"{v:.1f}%".replace(".", ",")


def num(v, casas=2):
    return "–" if v is None else f"{v:.{casas}f}".replace(".", ",")


class Relatorio:
    """Monta o documento com numeração automática de tabelas e figuras."""

    def __init__(self, ano):
        self.doc = Document()
        self.ano = ano
        self.n_tabela = 0
        self.n_figura = 0
        self._estilos()

    def _estilos(self):
        for secao in self.doc.sections:
            secao.page_height, secao.page_width = Cm(29.7), Cm(21)
            secao.top_margin = secao.left_margin = Cm(3)
            secao.bottom_margin = secao.right_margin = Cm(2)

        normal = self.doc.styles["Normal"]
        normal.font.name = "Arial"
        normal.font.size = Pt(12)
        fmt = normal.paragraph_format
        fmt.line_spacing_rule = WD_LINE_SPACING.ONE_POINT_FIVE
        fmt.space_after = Pt(6)

        for nivel in (1, 2):
            estilo = self.doc.styles[f"Heading {nivel}"]
            estilo.font.name = "Arial"
            estilo.font.size = Pt(12)
            estilo.font.bold = True
            estilo.font.color.rgb = RGBColor(0, 0, 0)
            estilo.paragraph_format.space_before = Pt(18)
            estilo.paragraph_format.space_after = Pt(12)

    # ------------------------------------------------------------ texto

    def titulo(self, texto, nivel=1):
        self.doc.add_heading(texto.upper() if nivel == 1 else texto, nivel)

    def paragrafo(self, texto):
        p = self.doc.add_paragraph(texto)
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        p.paragraph_format.first_line_indent = Cm(1.25)
        return p

    def item(self, rotulo, texto):
        p = self.doc.add_paragraph(style="List Bullet")
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        p.add_run(rotulo).bold = True
        p.add_run(texto)

    def centralizado(self, texto, negrito=False, tamanho=12):
        p = self.doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p.add_run(texto)
        r.bold = negrito
        r.font.size = Pt(tamanho)
        return p

    def _legenda(self, texto):
        p = self.doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_after = Pt(2)
        p.paragraph_format.keep_with_next = True
        r = p.add_run(texto)
        r.font.size = Pt(10)
        r.bold = True

    def _fonte(self):
        p = self.doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_after = Pt(12)
        r = p.add_run(f"Fonte: elaborado pelo autor ({self.ano}).")
        r.font.size = Pt(10)

    # ------------------------------------------------------------ tabelas

    def tabela(self, titulo, cabecalho, linhas, larguras=None):
        self.n_tabela += 1
        self._legenda(f"Tabela {self.n_tabela} – {titulo}")
        t = self.doc.add_table(rows=1, cols=len(cabecalho))
        t.style = "Table Grid"
        t.alignment = WD_TABLE_ALIGNMENT.CENTER
        for i, texto in enumerate(cabecalho):
            self._celula(t.rows[0].cells[i], texto, negrito=True)
        for linha in linhas:
            celulas = t.add_row().cells
            for i, texto in enumerate(linha):
                self._celula(celulas[i], str(texto))
        if larguras:
            for linha in t.rows:
                for i, w in enumerate(larguras):
                    linha.cells[i].width = Cm(w)
        self._fonte()
        return self.n_tabela

    @staticmethod
    def _celula(celula, texto, negrito=False):
        celula.text = ""
        p = celula.paragraphs[0]
        p.paragraph_format.line_spacing = 1.0
        p.paragraph_format.space_after = Pt(0)
        p.paragraph_format.first_line_indent = Cm(0)
        r = p.add_run(texto)
        r.font.size = Pt(10)
        r.bold = negrito

    # ------------------------------------------------------------ figuras

    def figura(self, titulo, fig):
        self.n_figura += 1
        self._legenda(f"Figura {self.n_figura} – {titulo}")
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=200, bbox_inches="tight")
        buf.seek(0)
        p = self.doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.add_run().add_picture(buf, width=Cm(15))
        self._fonte()
        return self.n_figura

    def salvar(self, caminho):
        self.doc.save(caminho)


# ---------------------------------------------------------------- gráficos

def _grafico_barras(rotulos, series, titulo_y, limite=100):
    """series: lista de (nome, valores, cor). Retorna a figura."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(8, 3.6))
    largura = 0.8 / len(series)
    for i, (nome, valores, cor) in enumerate(series):
        xs = [x + (i - (len(series) - 1) / 2) * largura
              for x in range(len(rotulos))]
        vals = [v or 0 for v in valores]
        barras = ax.bar(xs, vals, largura, label=nome, color=cor)
        for b, v in zip(barras, valores):
            if v is not None:
                ax.annotate(f"{v:.0f}" if limite == 100 else f"{v:.1f}",
                            (b.get_x() + b.get_width() / 2, b.get_height()),
                            ha="center", va="bottom", fontsize=7,
                            xytext=(0, 2), textcoords="offset points")
    ax.set_xticks(range(len(rotulos)))
    ax.set_xticklabels(rotulos)
    ax.set_ylabel(titulo_y)
    if limite:
        ax.set_ylim(0, limite * 1.12)
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", alpha=.3)
    if len(series) > 1:
        ax.legend(frameon=False, fontsize=8)
    fig.tight_layout()
    return fig


# ---------------------------------------------------------------- relatório

def gerar_relatorio(config, parametros, resultados, pessoas,
                    caminho=RELATORIO_PATH):
    ano = time.strftime("%Y")
    rel = Relatorio(ano)

    # anonimização: P1..Pn na ordem alfabética dos cadastrados
    cadastrados = sorted(pessoas)
    if config.get("anonimizar"):
        apelidos = {n: f"P{i}" for i, n in enumerate(cadastrados, 1)}
    else:
        apelidos = {n: n for n in cadastrados}

    def nome(n):
        if n is None:
            return "–"
        return apelidos.get(n, n)

    geral = calcular_metricas(resultados)
    por_caso = metricas_por(resultados, "caso")
    por_participante = metricas_por(resultados, "participante")
    casos_feitos = [c for c in CASOS if c["id"] in por_caso]
    genuinos = [c for c in casos_feitos if c["esperado"] == "liberado"]
    fraudes = [c for c in casos_feitos if c["esperado"] == "negado"]

    # ------------------------------------------------------------ cabeçalho
    if config.get("instituicao"):
        rel.centralizado(config["instituicao"].upper(), negrito=True)
    if config.get("curso"):
        rel.centralizado(config["curso"].upper())
    rel.centralizado("")
    if config.get("titulo"):
        rel.centralizado(config["titulo"].upper(), negrito=True, tamanho=14)
    rel.centralizado("Relatório de testes do protótipo de controle de acesso "
                     "por reconhecimento facial", negrito=not config.get("titulo"))
    if config.get("autor"):
        rel.centralizado(config["autor"])
    rodape = ", ".join(x for x in (config.get("cidade"), ano) if x)
    rel.centralizado(rodape)

    # ------------------------------------------------------------ 1 objetivo
    rel.titulo("1 Objetivo")
    rel.paragrafo(
        "Este relatório apresenta os testes realizados com o protótipo de "
        "controle de acesso por reconhecimento facial desenvolvido neste "
        "trabalho. O protótipo simula uma porta que é liberada quando o rosto "
        "de uma pessoa cadastrada é reconhecido e permanece fechada quando o "
        "rosto não é reconhecido. Os testes têm como objetivo medir a "
        "confiabilidade do sistema em diferentes distâncias e ângulos do rosto "
        "em relação à câmera, e verificar sua resistência a tentativas de "
        "fraude, como a apresentação de fotos e vídeos de pessoas cadastradas "
        "e o acesso de pessoas não cadastradas.")

    # ------------------------------------------------------------ 2 metodologia
    rel.titulo("2 Metodologia")
    rel.titulo("2.1 Protótipo", 2)
    rel.paragrafo(
        "O protótipo foi implementado em Python com a biblioteca OpenCV e "
        "possui uma interface web desenvolvida com o framework Flask. A "
        "detecção do rosto em cada quadro do vídeo é feita com o classificador "
        "em cascata de Haar (Haar cascade) para faces frontais, considerando "
        "apenas o maior rosto encontrado, ou seja, o mais próximo da câmera. "
        "O rosto detectado é convertido para tons de cinza, redimensionado "
        "para 200 × 200 pixels e tem o histograma equalizado, para reduzir a "
        "influência da iluminação. O reconhecimento é feito com o algoritmo "
        "LBPH (Local Binary Patterns Histograms), que retorna a pessoa mais "
        "parecida e um valor de distância (chamado de confiança no OpenCV): "
        "quanto menor esse valor, mais parecido é o rosto com o cadastrado.")
    rel.paragrafo(
        f"Para evitar decisões baseadas em um único quadro, a porta só é "
        f"liberada quando a mesma pessoa é reconhecida em "
        f"{parametros['frames']} quadros seguidos com distância menor ou "
        f"igual ao limiar. Da mesma forma, o acesso é negado quando um rosto "
        f"não reconhecido aparece em {parametros['frames']} quadros seguidos. "
        f"A Tabela 1 resume os parâmetros utilizados.")
    rel.tabela("Parâmetros do protótipo", ["Parâmetro", "Valor"], [
        ["Detector de rosto", "Haar cascade (haarcascade_frontalface_default)"],
        ["Tamanho mínimo do rosto detectado", "80 × 80 pixels"],
        ["Algoritmo de reconhecimento", "LBPH (OpenCV)"],
        ["Pré-processamento", "Tons de cinza, 200 × 200 px, equalização de histograma"],
        ["Amostras por pessoa no cadastro", parametros["amostras"]],
        ["Limiar de distância (confiança)", num(parametros["limiar"], 1)],
        ["Quadros seguidos para decidir", parametros["frames"]],
        ["Tempo máximo por tentativa", f"{parametros['timeout']} s"],
    ], larguras=[7, 8])

    rel.titulo("2.2 Ambiente e equipamentos", 2)
    camera = config.get("camera") or "câmera de vídeo"
    rel.paragrafo(
        f"A captura de vídeo foi feita com {camera}, posicionado de forma fixa "
        f"para simular uma câmera instalada ao lado de uma porta. O vídeo foi "
        f"processado em um computador executando o protótipo, que exibia na "
        f"tela a imagem da câmera, a simulação da porta e o resultado de cada "
        f"tentativa.")

    rel.titulo("2.3 Participantes", 2)
    papeis = {}
    for n in cadastrados:
        papeis.setdefault(pessoas[n], []).append(nome(n))
    desc_papeis = "; ".join(f"{p}: {', '.join(ns)}"
                            for p, ns in sorted(papeis.items()))
    texto = (f"Participaram dos testes {len(cadastrados)} voluntários, todos "
             f"cadastrados no sistema ({desc_papeis}). ")
    if config.get("anonimizar"):
        texto += ("Para preservar a identidade dos voluntários, eles são "
                  "identificados neste relatório pelos códigos P1 a "
                  f"P{len(cadastrados)}. ")
    texto += (f"Cada participante foi cadastrado com {parametros['amostras']} "
              f"imagens do rosto capturadas pela própria câmera do protótipo.")
    if any(r["participante"] == VISITANTE for r in resultados):
        texto += (" No caso de teste de pessoa não cadastrada, foi utilizada "
                  "uma pessoa que não fazia parte do cadastro.")
    rel.paragrafo(texto)

    rel.titulo("2.4 Procedimento", 2)
    rel.paragrafo(
        f"Para cada caso de teste e cada participante foram realizadas "
        f"{parametros['tentativas']} tentativas. Em cada tentativa, o operador "
        f"selecionava o caso e o participante na tela de testes e iniciava a "
        f"tentativa; o sistema então registrava automaticamente a decisão da "
        f"porta (liberado ou negado), o nome reconhecido, o tempo até a "
        f"decisão e os valores de distância do LBPH em cada quadro. Quando "
        f"não houve decisão em {parametros['timeout']} segundos, por exemplo "
        f"porque o rosto não foi detectado, a tentativa foi registrada como "
        f"\"sem decisão\" e considerada uma rejeição.")

    rel.titulo("2.5 Métricas", 2)
    rel.paragrafo(
        "As tentativas foram divididas em genuínas, em que um participante "
        "cadastrado tenta entrar com o próprio rosto e o esperado é o acesso "
        "liberado, e de impostor, em que se tenta entrar com uma foto, um "
        "vídeo ou uma pessoa não cadastrada e o esperado é o acesso negado. "
        "Cada tentativa foi classificada como:")
    rel.item("Verdadeiro positivo (VP): ", "participante liberado e "
             "reconhecido corretamente como ele mesmo.")
    rel.item("Falso negativo (FN): ", "participante cadastrado teve o "
             "acesso negado ou não houve decisão.")
    rel.item("Falso positivo (FP): ", "acesso liberado indevidamente, seja "
             "para um impostor, seja para um participante reconhecido como "
             "outra pessoa.")
    rel.item("Verdadeiro negativo (VN): ", "impostor teve o acesso negado.")
    rel.paragrafo("A partir dessa classificação foram calculadas as métricas:")
    rel.item("Acurácia: ", "(VP + VN) / total de tentativas.")
    rel.item("Taxa de aceitação correta (TAR): ", "VP / tentativas genuínas.")
    rel.item("Taxa de falsa rejeição (FRR): ", "FN / tentativas genuínas.")
    rel.item("Taxa de erro de identificação: ", "participantes liberados "
             "como outra pessoa / tentativas genuínas.")
    rel.item("Taxa de falsa aceitação (FAR): ", "impostores liberados / "
             "tentativas de impostor.")

    # ------------------------------------------------------------ 3 casos
    rel.titulo("3 Casos de teste")
    t_casos = rel.n_tabela + 1
    rel.paragrafo(
        f"Foram definidos {len(CASOS)} casos de teste, apresentados na "
        f"Tabela {t_casos}. Os casos CT01 a CT04 variam a distância entre o "
        f"rosto e a câmera, sendo o CT01 a condição de referência; os casos "
        f"CT05 a CT07 variam o ângulo do rosto; e os casos CT08 a CT10 "
        f"simulam tentativas de fraude.")
    rel.tabela("Casos de teste", ["ID", "Grupo", "Descrição", "Procedimento",
                                  "Esperado"],
               [[c["id"], c["grupo"], c["titulo"], c["procedimento"],
                 "Liberado" if c["esperado"] == "liberado" else "Negado"]
                for c in CASOS], larguras=[1.3, 1.9, 3.5, 6.3, 2])

    # ------------------------------------------------------------ 4 resultados
    rel.titulo("4 Resultados")
    if not resultados:
        rel.paragrafo("Nenhuma tentativa foi registrada até o momento.")
        rel.salvar(caminho)
        return caminho

    datas = sorted(r["data"][:10] for r in resultados)
    periodo = (_data_br(datas[0]) if datas[0] == datas[-1]
               else f"{_data_br(datas[0])} a {_data_br(datas[-1])}")

    rel.titulo("4.1 Visão geral", 2)
    t_geral = rel.n_tabela + 1
    rel.paragrafo(
        f"Os testes foram realizados em {periodo}, totalizando "
        f"{geral['total']} tentativas, das quais {geral['genuinas']} genuínas "
        f"e {geral['impostoras']} de impostor. A Tabela {t_geral} apresenta "
        f"as métricas gerais. A acurácia geral foi de {pct(geral['acuracia'])}"
        + (f", com taxa de aceitação correta de {pct(geral['tar'])} e taxa de "
           f"falsa rejeição de {pct(geral['frr'])} nas tentativas genuínas"
           if geral["genuinas"] else "")
        + (f", e taxa de falsa aceitação de {pct(geral['far'])} nas "
           f"tentativas de impostor" if geral["impostoras"] else "")
        + ".")
    rel.tabela("Métricas gerais", ["Métrica", "Valor"], [
        ["Total de tentativas", geral["total"]],
        ["Tentativas genuínas / de impostor",
         f"{geral['genuinas']} / {geral['impostoras']}"],
        ["VP / FN / FP / VN",
         f"{geral['VP']} / {geral['FN']} / {geral['FP']} / {geral['VN']}"],
        ["Acurácia", pct(geral["acuracia"])],
        ["Taxa de aceitação correta (TAR)", pct(geral["tar"])],
        ["Taxa de falsa rejeição (FRR)", pct(geral["frr"])],
        ["Taxa de erro de identificação", pct(geral["erro_id"])],
        ["Taxa de falsa aceitação (FAR)", pct(geral["far"])],
        ["Tentativas sem decisão", geral["sem_deteccao"]],
        ["Tempo médio até a decisão", f"{num(geral['tempo_medio'])} s"],
        ["Distância LBPH média", num(geral["confianca_media"], 1)],
    ], larguras=[8, 5])

    rel.titulo("4.2 Resultados por caso de teste", 2)
    t_caso = rel.n_tabela + 1
    f_caso = rel.n_figura + 1
    rel.paragrafo(
        f"A Tabela {t_caso} detalha os resultados de cada caso de teste e a "
        f"Figura {f_caso} compara a acurácia obtida em cada um deles.")
    rel.tabela("Resultados por caso de teste",
               ["Caso", "N", "VP", "FN", "FP", "VN", "Acurácia",
                "Tempo médio (s)", "Dist. média"],
               [[c["id"], m["total"], m["VP"], m["FN"], m["FP"], m["VN"],
                 pct(m["acuracia"]), num(m["tempo_medio"]),
                 num(m["confianca_media"], 1)]
                for c in casos_feitos for m in [por_caso[c["id"]]]])
    rel.figura("Acurácia por caso de teste", _grafico_barras(
        [c["id"] for c in casos_feitos],
        [("Acurácia (%)", [por_caso[c["id"]]["acuracia"] for c in casos_feitos],
          "#2a6fdb")],
        "Acurácia (%)"))

    if genuinos:
        rel.titulo("4.3 Variação de distância e ângulo", 2)
        ref = por_caso.get("CT01")
        melhor = max(genuinos, key=lambda c: por_caso[c["id"]]["tar"])
        pior = min(genuinos, key=lambda c: por_caso[c["id"]]["tar"])
        f_gen = rel.n_figura + 1
        texto = (f"A Figura {f_gen} mostra a taxa de aceitação correta e a "
                 f"taxa de falsa rejeição nos casos genuínos. ")
        if ref:
            texto += (f"Na condição de referência (CT01, frontal a 50 cm), a "
                      f"taxa de aceitação correta foi de {pct(ref['tar'])}. ")
        texto += (f"O melhor desempenho foi observado no caso "
                  f"{melhor['id']} ({melhor['titulo'].lower()}), com "
                  f"{pct(por_caso[melhor['id']]['tar'])} de aceitação "
                  f"correta, e o pior no caso {pior['id']} "
                  f"({pior['titulo'].lower()}), com "
                  f"{pct(por_caso[pior['id']]['tar'])}.")
        rel.paragrafo(texto)

        sem = [(c, por_caso[c["id"]]["sem_deteccao"]) for c in genuinos
               if por_caso[c["id"]]["sem_deteccao"]]
        if sem:
            lista = ", ".join(f"{c['id']} ({n})" for c, n in sem)
            rel.paragrafo(
                f"Houve tentativas sem decisão nos casos {lista}. Nessas "
                f"tentativas o rosto não chegou a ser detectado de forma "
                f"contínua, o que é esperado em rostos muito distantes "
                f"(menores que o tamanho mínimo de 80 × 80 pixels do detector) "
                f"ou muito girados, já que o classificador de Haar utilizado "
                f"foi treinado para faces frontais.")
        erros_id = sum(por_caso[c["id"]]["FP"] for c in genuinos)
        if erros_id:
            rel.paragrafo(
                f"Em {erros_id} tentativa(s) genuína(s) o participante foi "
                f"liberado, porém reconhecido como outra pessoa cadastrada. "
                f"Embora a porta tenha sido aberta para alguém autorizado, "
                f"esse erro é grave em um controle de acesso, pois o registro "
                f"de entrada fica associado à pessoa errada.")
        else:
            rel.paragrafo(
                "Em nenhuma tentativa genuína um participante foi reconhecido "
                "como outra pessoa cadastrada.")
        rel.figura("Aceitação correta e falsa rejeição nos casos genuínos",
                   _grafico_barras(
                       [c["id"] for c in genuinos],
                       [("TAR (%)", [por_caso[c["id"]]["tar"] for c in genuinos],
                         "#2a9d5c"),
                        ("FRR (%)", [por_caso[c["id"]]["frr"] for c in genuinos],
                         "#d9534f")],
                       "Taxa (%)"))

    if fraudes:
        rel.titulo("4.4 Tentativas de fraude", 2)
        partes = []
        for c in fraudes:
            m = por_caso[c["id"]]
            partes.append(f"no caso {c['id']} ({c['titulo'].lower()}), "
                          f"{m['FP']} de {m['total']} tentativas foram "
                          f"aceitas indevidamente (FAR de {pct(m['far'])})")
        rel.paragrafo("Nas tentativas de impostor, " + "; ".join(partes) + ".")
        spoof = [c for c in fraudes if c["id"] in ("CT08", "CT09")]
        aceitos = sum(por_caso[c["id"]]["FP"] for c in spoof)
        if spoof and aceitos:
            rel.paragrafo(
                "A aceitação de fotos e vídeos exibidos na tela de um celular "
                "evidencia que o protótipo não possui detecção de vivacidade "
                "(liveness detection): o LBPH compara apenas a textura da "
                "imagem do rosto em tons de cinza e não tem como diferenciar "
                "um rosto real de uma reprodução. Essa é uma limitação "
                "conhecida de sistemas de reconhecimento facial baseados "
                "apenas em imagens 2D.")
        elif spoof:
            rel.paragrafo(
                "Nenhuma foto ou vídeo exibido no celular foi aceito. Vale "
                "observar, porém, que o protótipo não possui uma etapa "
                "específica de detecção de vivacidade (liveness detection); "
                "a rejeição se deve provavelmente às diferenças que a tela "
                "introduz na imagem (reflexos, brilho, moiré e perda de "
                "nitidez), que aumentam a distância LBPH. Com uma reprodução "
                "de melhor qualidade o resultado poderia ser diferente.")

    rel.titulo("4.5 Resultados por participante", 2)
    t_part = rel.n_tabela + 1
    rel.paragrafo(f"A Tabela {t_part} apresenta os resultados agrupados por "
                  f"participante.")
    rel.tabela("Resultados por participante",
               ["Participante", "N", "VP", "FN", "FP", "VN", "Acurácia",
                "Dist. média"],
               [[nome(p), m["total"], m["VP"], m["FN"], m["FP"], m["VN"],
                 pct(m["acuracia"]), num(m["confianca_media"], 1)]
                for p, m in sorted(por_participante.items(),
                                   key=lambda kv: nome(kv[0]))])

    # ------------------------------------------------------------ 5 conclusão
    rel.titulo("5 Considerações sobre os resultados")
    texto = (f"Os testes mostraram que o protótipo atingiu acurácia geral de "
             f"{pct(geral['acuracia'])} nas {geral['total']} tentativas "
             f"realizadas. ")
    if genuinos:
        texto += (f"Nas tentativas genuínas, o melhor desempenho ocorreu no "
                  f"caso {melhor['id']} ({melhor['titulo'].lower()}) e o "
                  f"pior no caso {pior['id']} ({pior['titulo'].lower()}), o "
                  f"que deve ser levado em conta no posicionamento da câmera "
                  f"e na orientação das pessoas em uma instalação real. ")
    if fraudes:
        texto += (f"Nas tentativas de impostor, a taxa de falsa aceitação "
                  f"foi de {pct(geral['far'])}. ")
    texto += (
        "Como melhorias futuras, sugerem-se o uso de detectores e "
        "reconhecedores baseados em redes neurais, mais tolerantes a "
        "variações de ângulo e distância, a inclusão de detecção de "
        "vivacidade para impedir o uso de fotos e vídeos, e o ajuste do "
        "limiar de distância a partir de um número maior de participantes.")
    rel.paragrafo(texto)

    # ------------------------------------------------------------ apêndice
    rel.titulo("Apêndice A – Registro das tentativas")
    rel.tabela("Registro de todas as tentativas",
               ["Caso", "Participante", "Nº", "Decisão", "Reconhecido como",
                "Classif.", "Tempo (s)", "Dist. média"],
               [[r["caso"], nome(r["participante"]), r["tentativa"],
                 NOMES_DECISAO[r["decisao"]], nome(r["nome_reconhecido"]),
                 r["classificacao"], num(r["tempo"]),
                 num(r["confianca_media"], 1)]
                for r in sorted(resultados, key=lambda r: (
                    r["caso"], nome(r["participante"]), r["tentativa"]))])

    rel.salvar(caminho)
    return caminho


def _data_br(iso):
    a, m, d = iso.split("-")
    return f"{d}/{m}/{a}"


if __name__ == "__main__":
    from app import (carregar_pessoas, carregar_relatorio_config,
                     LIMIAR_CONFIANCA, FRAMES_PARA_CONFIRMAR,
                     TIMEOUT_TENTATIVA, ROTACAO)
    from cadastrar import NUM_AMOSTRAS
    from casos_teste import TENTATIVAS_POR_CASO

    arquivo = gerar_relatorio(
        carregar_relatorio_config(),
        {"limiar": LIMIAR_CONFIANCA, "frames": FRAMES_PARA_CONFIRMAR,
         "amostras": NUM_AMOSTRAS, "timeout": TIMEOUT_TENTATIVA,
         "tentativas": TENTATIVAS_POR_CASO, "rotacao": ROTACAO},
        carregar_resultados(), carregar_pessoas())
    print(f"Relatório gerado: {arquivo}")

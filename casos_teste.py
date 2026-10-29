# -*- coding: utf-8 -*-
"""
Casos de teste do controle de acesso e cálculo das métricas.

Usado pela página de testes (app.py) e pelo gerador de relatório
(relatorio.py), para que os dois usem exatamente as mesmas regras.

Classificação de cada tentativa:
    VP  verdadeiro positivo  - pessoa cadastrada liberada como ela mesma
    FN  falso negativo       - pessoa cadastrada barrada (ou não detectada)
    FP  falso positivo       - acesso liberado indevidamente (fraude/visitante
                               aceito, ou cadastrado liberado como OUTRA pessoa)
    VN  verdadeiro negativo  - fraude/visitante barrado
"""

import os
import json

from cadastrar import BASE_DIR

RESULTADOS_PATH = os.path.join(BASE_DIR, "testes.json")

TENTATIVAS_POR_CASO = 5
VISITANTE = "Visitante (não cadastrado)"

# esperado: "liberado" = tentativa genuína, "negado" = tentativa de impostor
CASOS = [
    {
        "id": "CT01", "grupo": "Distância", "esperado": "liberado",
        "titulo": "Frontal a 50 cm, referência",
        "procedimento": "Fique de frente para a câmera, a cerca de 50 cm, "
                        "rosto neutro e parado até a porta responder.",
    },
    {
        "id": "CT02", "grupo": "Distância", "esperado": "liberado",
        "titulo": "Muito perto, a 25 cm",
        "procedimento": "Aproxime o rosto até cerca de 25 cm da câmera, "
                        "olhando de frente.",
    },
    {
        "id": "CT03", "grupo": "Distância", "esperado": "liberado",
        "titulo": "Distância média, a 1 m",
        "procedimento": "Fique de frente para a câmera a cerca de 1 metro.",
    },
    {
        "id": "CT04", "grupo": "Distância", "esperado": "liberado",
        "titulo": "Longe, a 2 m",
        "procedimento": "Fique de frente para a câmera a cerca de 2 metros.",
    },
    {
        "id": "CT05", "grupo": "Ângulo", "esperado": "liberado",
        "titulo": "Rosto girado ~30° para o lado",
        "procedimento": "A 50 cm, gire a cabeça cerca de 30° para a esquerda "
                        "ou direita (alterne entre as tentativas).",
    },
    {
        "id": "CT06", "grupo": "Ângulo", "esperado": "liberado",
        "titulo": "Rosto quase de perfil, ~60°",
        "procedimento": "A 50 cm, gire a cabeça cerca de 60°, quase de perfil.",
    },
    {
        "id": "CT07", "grupo": "Ângulo", "esperado": "liberado",
        "titulo": "Cabeça inclinada ~20° para cima ou baixo",
        "procedimento": "A 50 cm, incline a cabeça cerca de 20° para cima ou "
                        "para baixo (alterne entre as tentativas).",
    },
    {
        "id": "CT08", "grupo": "Fraude", "esperado": "negado",
        "titulo": "Foto do cadastrado na tela do celular",
        "procedimento": "Mostre para a câmera, a cerca de 30 cm, uma foto "
                        "frontal do participante selecionado na tela de outro "
                        "celular (brilho no máximo).",
    },
    {
        "id": "CT09", "grupo": "Fraude", "esperado": "negado",
        "titulo": "Vídeo do cadastrado na tela do celular",
        "procedimento": "Mostre para a câmera um vídeo do participante "
                        "selecionado (rosto de frente, se mexendo) na tela de "
                        "outro celular.",
    },
    {
        "id": "CT10", "grupo": "Fraude", "esperado": "negado",
        "titulo": "Pessoa não cadastrada",
        "procedimento": "Uma pessoa que NÃO foi cadastrada fica de frente "
                        "para a câmera a 50 cm. Selecione o participante "
                        f"\"{VISITANTE}\".",
        "somente_visitante": True,
    },
]

CASOS_POR_ID = {c["id"]: c for c in CASOS}


def participantes_do_caso(caso, pessoas):
    """Quem participa de um caso: os cadastrados ou só o visitante."""
    if caso.get("somente_visitante"):
        return [VISITANTE]
    return sorted(pessoas)


def classificar(caso, participante, decisao, nome_reconhecido):
    """Retorna VP, FN, FP ou VN para uma tentativa."""
    liberou = decisao == "liberado"
    if caso["esperado"] == "liberado":
        if liberou:
            return "VP" if nome_reconhecido == participante else "FP"
        return "FN"
    return "FP" if liberou else "VN"


# ---------------------------------------------------------------- persistência

def carregar_resultados():
    if os.path.exists(RESULTADOS_PATH):
        with open(RESULTADOS_PATH, encoding="utf-8") as f:
            return json.load(f)
    return []


def salvar_resultados(resultados):
    with open(RESULTADOS_PATH, "w", encoding="utf-8") as f:
        json.dump(resultados, f, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------- métricas

def _pct(parte, total):
    return round(100.0 * parte / total, 1) if total else None


def _media(valores):
    valores = [v for v in valores if v is not None]
    return round(sum(valores) / len(valores), 2) if valores else None


def calcular_metricas(resultados):
    """Métricas de um conjunto de tentativas.

    acuracia   (VP + VN) / total
    tar        taxa de aceitação correta  = VP / genuínas
    frr        taxa de falsa rejeição     = FN / genuínas
    erro_id    liberado como outra pessoa = FP / genuínas
    far        taxa de falsa aceitação    = FP / impostoras
    """
    cont = {"VP": 0, "FN": 0, "FP": 0, "VN": 0}
    fp_genuinas = fp_impostoras = 0
    genuinas = impostoras = sem_deteccao = 0
    for r in resultados:
        cont[r["classificacao"]] += 1
        if r["esperado"] == "liberado":
            genuinas += 1
            fp_genuinas += r["classificacao"] == "FP"
        else:
            impostoras += 1
            fp_impostoras += r["classificacao"] == "FP"
        sem_deteccao += r["decisao"] == "sem_decisao"

    total = len(resultados)
    return {
        "total": total,
        "genuinas": genuinas,
        "impostoras": impostoras,
        **cont,
        "sem_deteccao": sem_deteccao,
        "acuracia": _pct(cont["VP"] + cont["VN"], total),
        "tar": _pct(cont["VP"], genuinas),
        "frr": _pct(cont["FN"], genuinas),
        "erro_id": _pct(fp_genuinas, genuinas),
        "far": _pct(fp_impostoras, impostoras),
        "tempo_medio": _media([r["tempo"] for r in resultados
                               if r["decisao"] != "sem_decisao"]),
        "confianca_media": _media([r["confianca_media"] for r in resultados]),
    }


def metricas_por(resultados, chave):
    """Agrupa os resultados por uma chave (ex.: 'caso') e calcula métricas."""
    grupos = {}
    for r in resultados:
        grupos.setdefault(r[chave], []).append(r)
    return {k: calcular_metricas(v) for k, v in sorted(grupos.items())}

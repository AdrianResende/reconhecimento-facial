# -*- coding: utf-8 -*-
"""
Dashboard web de reconhecimento facial para universidade.

- Cadastro de pessoas com nome e papel (Professor/Estudante).
- Registro de presença: simula uma câmera na porta da sala de aula; quem é
  reconhecido tem a presença registrada na lista do dia, quem não é
  reconhecido não tem a presença registrada.
- Módulo de testes: registra tentativas por caso de teste e participante,
  calcula as métricas e gera o relatório (.docx) para o TCC.

Uso:
    python app.py                                   # webcam do notebook
    python app.py http://192.168.10.140:4747/video 90   # iPhone (com rotação)

Depois abra http://localhost:5000 no navegador.
"""

import os
import io
import sys
import csv
import json
import time
import shutil
import threading
from collections import Counter

import cv2
import numpy as np

from haar import carregar_cascade, parse_fonte_e_rotacao, girar_frame
from cadastrar import (
    BASE_DIR, DATASET_DIR, MODELO_PATH, LABELS_PATH,
    NUM_AMOSTRAS, detectar_rosto, preprocessar_rosto, treinar_modelo,
)
from casos_teste import (
    CASOS, CASOS_POR_ID, TENTATIVAS_POR_CASO, NOMES_DECISAO,
    participantes_do_caso, classificar, carregar_resultados,
    salvar_resultados, calcular_metricas, metricas_por,
)

try:
    from flask import (
        Flask, Response, jsonify, redirect, render_template, request,
        send_file, url_for,
    )
except ImportError:
    sys.exit("Flask não instalado. Rode: pip install -r requirements.txt")

PESSOAS_PATH = os.path.join(BASE_DIR, "pessoas.json")  # nome -> papel
# data -> {nome: {"papel", "hora"}}
PRESENCAS_PATH = os.path.join(BASE_DIR, "presencas.json")
RELATORIO_CONFIG_PATH = os.path.join(BASE_DIR, "relatorio_config.json")
PAPEIS = ["Professor", "Estudante"]

LIMIAR_CONFIANCA = 50.0
FRAMES_PARA_CONFIRMAR = 10
TEMPO_PORTA_ABERTA = 4     # segundos mostrando liberado/negado
TIMEOUT_TENTATIVA = 15     # segundos sem decisão = "sem decisão" no teste

app = Flask(__name__)

# Fonte de vídeo e rotação vêm da linha de comando (iguais aos outros scripts)
FONTE, ROTACAO = parse_fonte_e_rotacao(sys.argv)

# Só um stream pode usar a câmera por vez
trava_camera = threading.Lock()
# Protege o estado da porta e a tentativa de teste em andamento
trava_estado = threading.Lock()

# Estado do cadastro em andamento (lido pela página via /cadastro/status)
captura = {
    "ativo": False, "nome": None, "papel": None,
    "capturadas": 0, "concluido": False, "erro": None,
}

# Estado da porta da sala (lido pelas páginas de presença e de testes)
# estado: aguardando | verificando | liberado | negado
# ja_registrada: hora da presença anterior, se a pessoa já tinha entrado hoje
porta = {
    "estado": "aguardando", "progresso": 0, "nome": None, "papel": None,
    "confianca": None, "hora": None, "ja_registrada": None,
    "bloqueado_ate": 0.0, "reiniciar": False,
}

tentativa = None        # teste em andamento (dict) ou None
ultimo_resultado = None  # última tentativa registrada


# ---------------------------------------------------------------- dados

def carregar_pessoas():
    if os.path.exists(PESSOAS_PATH):
        with open(PESSOAS_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {}


def salvar_pessoas(pessoas):
    with open(PESSOAS_PATH, "w", encoding="utf-8") as f:
        json.dump(pessoas, f, ensure_ascii=False, indent=2)


def contar_amostras(nome):
    pasta = os.path.join(DATASET_DIR, nome)
    return len(os.listdir(pasta)) if os.path.isdir(pasta) else 0


def carregar_presencas():
    if os.path.exists(PRESENCAS_PATH):
        with open(PRESENCAS_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {}


def registrar_presenca(nome, papel, hora):
    """Marca presença no dia de hoje; retorna a hora anterior se já havia."""
    presencas = carregar_presencas()
    hoje = presencas.setdefault(time.strftime("%Y-%m-%d"), {})
    if nome in hoje:
        return hoje[nome]["hora"]
    hoje[nome] = {"papel": papel, "hora": hora}
    with open(PRESENCAS_PATH, "w", encoding="utf-8") as f:
        json.dump(presencas, f, ensure_ascii=False, indent=2)
    return None


def carregar_relatorio_config():
    if os.path.exists(RELATORIO_CONFIG_PATH):
        with open(RELATORIO_CONFIG_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {}


def abrir_camera():
    camera = cv2.VideoCapture(FONTE)
    if not camera.isOpened():
        raise RuntimeError(f"Não foi possível abrir a fonte de vídeo: {FONTE!r}")
    return camera


def ler_frame(camera, falhas):
    """Lê um frame; após várias falhas seguidas reabre a câmera.

    Retorna (camera, frame ou None, falhas). Sem isso, se o DroidCam cair o
    loop de vídeo ficaria preso para sempre segurando a câmera.
    """
    ok, frame = camera.read()
    if ok:
        return camera, girar_frame(frame, ROTACAO), 0
    falhas += 1
    time.sleep(0.05)
    if falhas % 40 == 0:  # ~2 s sem imagem: tenta reconectar
        camera.release()
        camera = cv2.VideoCapture(FONTE)
    return camera, None, falhas


def frame_sem_sinal():
    frame = np.full((480, 640, 3), 40, np.uint8)
    cv2.putText(frame, "Sem sinal da camera - reconectando...", (60, 240),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (200, 200, 200), 2)
    return frame


def frame_para_jpeg(frame):
    ok, jpeg = cv2.imencode(".jpg", frame)
    return (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n"
            + jpeg.tobytes() + b"\r\n") if ok else b""


def estado_porta_publico():
    return {k: porta[k] for k in
            ("estado", "progresso", "nome", "papel", "confianca", "hora",
             "ja_registrada")}


# ---------------------------------------------------------------- decisões

def registrar_decisao(decisao, nome, papel, confianca, marcar_presenca):
    """Mostra a decisão na porta, marca a presença e fecha a tentativa.

    marcar_presenca é falso na página de testes, para as tentativas não
    entrarem na lista de presença do dia.
    """
    with trava_estado:
        hora = time.strftime("%H:%M:%S")
        ja_registrada = None
        if decisao == "liberado" and marcar_presenca:
            ja_registrada = registrar_presenca(nome, papel, hora)
        porta.update(estado=decisao, nome=nome, papel=papel,
                     confianca=confianca, hora=hora,
                     ja_registrada=ja_registrada,
                     progresso=FRAMES_PARA_CONFIRMAR,
                     bloqueado_ate=time.time() + TEMPO_PORTA_ABERTA)
        if tentativa is not None:
            finalizar_tentativa(decisao, nome)


def finalizar_tentativa(decisao, nome_reconhecido):
    """Grava a tentativa em andamento (chamar com trava_estado)."""
    global tentativa, ultimo_resultado
    t = tentativa
    tentativa = None
    caso = CASOS_POR_ID[t["caso"]]
    confiancas = t["confiancas"]

    # sem decisão: registra o nome que o modelo mais "chutou" (se houve rosto)
    if nome_reconhecido is None and t["previstos"]:
        nome_reconhecido = Counter(t["previstos"]).most_common(1)[0][0]

    resultado = {
        "id": int(time.time() * 1000),
        "data": time.strftime("%Y-%m-%d %H:%M:%S"),
        "caso": caso["id"],
        "grupo": caso["grupo"],
        "participante": t["participante"],
        "tentativa": t["numero"],
        "esperado": caso["esperado"],
        "decisao": decisao,
        "nome_reconhecido": nome_reconhecido,
        "classificacao": classificar(caso, t["participante"], decisao,
                                     nome_reconhecido),
        "tempo": round(time.time() - t["inicio"], 2),
        "frames_com_rosto": len(confiancas),
        "confianca_media": (round(sum(confiancas) / len(confiancas), 1)
                            if confiancas else None),
        "confianca_min": round(min(confiancas), 1) if confiancas else None,
    }
    resultados = carregar_resultados()
    resultados.append(resultado)
    salvar_resultados(resultados)
    ultimo_resultado = resultado


def verificar_timeout():
    with trava_estado:
        if (tentativa is not None
                and time.time() - tentativa["inicio"] > TIMEOUT_TENTATIVA):
            finalizar_tentativa("sem_decisao", None)


# ---------------------------------------------------------------- páginas

@app.route("/")
def index():
    pessoas = carregar_pessoas()
    lista = [
        {"nome": nome, "papel": papel, "amostras": contar_amostras(nome)}
        for nome, papel in sorted(pessoas.items())
    ]
    return render_template(
        "index.html",
        pessoas=lista,
        total_professores=sum(1 for p in lista if p["papel"] == "Professor"),
        total_estudantes=sum(1 for p in lista if p["papel"] == "Estudante"),
        modelo_ok=os.path.exists(MODELO_PATH),
        total_testes=len(carregar_resultados()),
    )


@app.route("/cadastro", methods=["GET", "POST"])
def cadastro():
    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        papel = request.form.get("papel", "")
        if not nome or papel not in PAPEIS:
            return render_template("cadastro.html", papeis=PAPEIS,
                                   erro="Preencha o nome e escolha o papel.")
        captura.update(ativo=True, nome=nome, papel=papel,
                       capturadas=0, concluido=False, erro=None)
        return redirect(url_for("capturando"))
    return render_template("cadastro.html", papeis=PAPEIS, erro=None)


@app.route("/cadastro/capturando")
def capturando():
    if not captura["ativo"] and not captura["concluido"]:
        return redirect(url_for("cadastro"))
    return render_template("capturando.html", captura=captura,
                           total=NUM_AMOSTRAS)


@app.route("/cadastro/status")
def cadastro_status():
    return jsonify(capturadas=captura["capturadas"], total=NUM_AMOSTRAS,
                   concluido=captura["concluido"], erro=captura["erro"])


@app.route("/remover/<nome>", methods=["POST"])
def remover(nome):
    pessoas = carregar_pessoas()
    pessoas.pop(nome, None)
    salvar_pessoas(pessoas)
    shutil.rmtree(os.path.join(DATASET_DIR, nome), ignore_errors=True)

    # retreina com quem sobrou (ou apaga o modelo se não sobrou ninguém)
    if pessoas:
        treinar_modelo()
    else:
        for arq in (MODELO_PATH, LABELS_PATH):
            if os.path.exists(arq):
                os.remove(arq)
    return redirect(url_for("index"))


# ---------------------------------------------------------------- presença

@app.route("/presenca")
def pagina_presenca():
    if not os.path.exists(MODELO_PATH):
        return redirect(url_for("index"))
    return render_template("presenca.html", frames=FRAMES_PARA_CONFIRMAR,
                           total_cadastrados=len(carregar_pessoas()))


@app.route("/presenca/status")
def presenca_status():
    hoje = carregar_presencas().get(time.strftime("%Y-%m-%d"), {})
    lista = sorted(({"nome": n, **d} for n, d in hoje.items()),
                   key=lambda p: p["hora"], reverse=True)
    return jsonify(porta=estado_porta_publico(), presentes=lista)


@app.route("/presenca/csv")
def presenca_csv():
    """Lista de presença de todos os dias, para abrir no Excel."""
    pessoas = carregar_pessoas()
    saida = io.StringIO()
    escritor = csv.writer(saida, delimiter=";")
    escritor.writerow(["data", "nome", "papel", "situacao", "hora_entrada"])
    for data, presentes in sorted(carregar_presencas().items()):
        for nome in sorted(set(pessoas) | set(presentes)):
            p = presentes.get(nome)
            escritor.writerow([data, nome, pessoas.get(nome, p and p["papel"]),
                               "Presente" if p else "Ausente",
                               p["hora"] if p else ""])
    dados = ("\ufeff" + saida.getvalue()).encode("utf-8")
    return send_file(io.BytesIO(dados), mimetype="text/csv",
                     as_attachment=True, download_name="lista_presenca.csv")


# ---------------------------------------------------------------- testes

@app.route("/testes")
def pagina_testes():
    if not os.path.exists(MODELO_PATH):
        return redirect(url_for("index"))
    return render_template(
        "testes.html",
        casos=CASOS, nomes_decisao=NOMES_DECISAO,
        frames=FRAMES_PARA_CONFIRMAR,
        tentativas_por_caso=TENTATIVAS_POR_CASO,
        timeout=TIMEOUT_TENTATIVA,
        config=carregar_relatorio_config(),
    )


@app.route("/testes/dados")
def testes_dados():
    """Tudo que a página de testes precisa para se redesenhar."""
    verificar_timeout()
    pessoas = carregar_pessoas()
    resultados = carregar_resultados()

    contagem = Counter((r["caso"], r["participante"]) for r in resultados)
    matriz = {
        c["id"]: {p: contagem[(c["id"], p)]
                  for p in participantes_do_caso(c, pessoas)}
        for c in CASOS
    }
    with trava_estado:
        t = None
        if tentativa is not None:
            t = {k: tentativa[k] for k in ("caso", "participante", "numero")}
            t["decorrido"] = round(time.time() - tentativa["inicio"], 1)
        return jsonify(
            porta=estado_porta_publico(),
            tentativa=t,
            ultimo=ultimo_resultado,
            matriz=matriz,
            geral=calcular_metricas(resultados),
            por_caso=metricas_por(resultados, "caso"),
            resultados=resultados[::-1],
        )


@app.route("/testes/iniciar", methods=["POST"])
def testes_iniciar():
    global tentativa
    dados = request.get_json(force=True)
    caso = CASOS_POR_ID.get(dados.get("caso"))
    participante = dados.get("participante")
    if caso is None or participante not in participantes_do_caso(
            caso, carregar_pessoas()):
        return jsonify(erro="Caso ou participante inválido."), 400

    feitas = sum(1 for r in carregar_resultados()
                 if r["caso"] == caso["id"] and r["participante"] == participante)
    with trava_estado:
        if tentativa is not None:
            return jsonify(erro="Já existe uma tentativa em andamento."), 409
        tentativa = {
            "caso": caso["id"], "participante": participante,
            "numero": feitas + 1, "inicio": time.time(),
            "confiancas": [], "previstos": [],
        }
        # começa do zero: fecha a porta e zera a contagem de frames
        porta.update(estado="aguardando", progresso=0, bloqueado_ate=0.0,
                     reiniciar=True)
    return jsonify(ok=True)


@app.route("/testes/cancelar", methods=["POST"])
def testes_cancelar():
    global tentativa
    with trava_estado:
        tentativa = None
    return jsonify(ok=True)


@app.route("/testes/remover/<int:id_resultado>", methods=["POST"])
def testes_remover(id_resultado):
    global ultimo_resultado
    resultados = [r for r in carregar_resultados() if r["id"] != id_resultado]
    salvar_resultados(resultados)
    if ultimo_resultado and ultimo_resultado["id"] == id_resultado:
        ultimo_resultado = None
    return jsonify(ok=True)


@app.route("/testes/limpar", methods=["POST"])
def testes_limpar():
    global ultimo_resultado
    salvar_resultados([])
    ultimo_resultado = None
    return jsonify(ok=True)


@app.route("/testes/csv")
def testes_csv():
    colunas = ["data", "caso", "grupo", "participante", "tentativa",
               "esperado", "decisao", "nome_reconhecido", "classificacao",
               "tempo", "frames_com_rosto", "confianca_media", "confianca_min"]
    saida = io.StringIO()
    # ";" e BOM para o Excel em português abrir certinho
    escritor = csv.DictWriter(saida, fieldnames=colunas, delimiter=";",
                              extrasaction="ignore")
    escritor.writeheader()
    escritor.writerows(carregar_resultados())
    dados = ("﻿" + saida.getvalue()).encode("utf-8")
    return send_file(io.BytesIO(dados), mimetype="text/csv",
                     as_attachment=True, download_name="resultados_testes.csv")


def parametros_do_prototipo():
    return {
        "limiar": LIMIAR_CONFIANCA, "frames": FRAMES_PARA_CONFIRMAR,
        "amostras": NUM_AMOSTRAS, "timeout": TIMEOUT_TENTATIVA,
        "tentativas": TENTATIVAS_POR_CASO, "rotacao": ROTACAO,
    }


@app.route("/testes/relatorio", methods=["POST"])
def testes_relatorio():
    # python-docx e matplotlib só são exigidos aqui
    from relatorio import gerar_docx, gerar_latex

    config = {k: request.form.get(k, "").strip() for k in
              ("titulo", "autor", "curso", "instituicao", "cidade", "camera")}
    config["anonimizar"] = request.form.get("anonimizar") == "on"
    with open(RELATORIO_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

    gerar = gerar_latex if request.form.get("formato") == "latex" else gerar_docx
    arquivo = gerar(config, parametros_do_prototipo(), carregar_resultados(),
                    carregar_pessoas())
    return send_file(arquivo, as_attachment=True,
                     download_name=os.path.basename(arquivo))


# ---------------------------------------------------------------- vídeo

@app.route("/video/cadastro")
def video_cadastro():
    return Response(gerar_video_cadastro(),
                    mimetype="multipart/x-mixed-replace; boundary=frame")


def gerar_video_cadastro():
    if not captura["ativo"]:
        return
    with trava_camera:
        cascade = carregar_cascade()
        try:
            camera = abrir_camera()
        except RuntimeError as e:
            captura.update(ativo=False, erro=str(e))
            return

        nome = captura["nome"]
        pasta = os.path.join(DATASET_DIR, nome)
        os.makedirs(pasta, exist_ok=True)
        falhas = 0
        try:
            while captura["ativo"] and captura["capturadas"] < NUM_AMOSTRAS:
                camera, frame, falhas = ler_frame(camera, falhas)
                if frame is None:
                    yield frame_para_jpeg(frame_sem_sinal())
                    continue
                cinza = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                rosto = detectar_rosto(cascade, cinza)

                if rosto is not None:
                    x, y, w, h = rosto
                    recorte = preprocessar_rosto(cinza[y:y + h, x:x + w])
                    n = captura["capturadas"]
                    cv2.imwrite(os.path.join(pasta, f"{n:03d}.png"), recorte)
                    captura["capturadas"] = n + 1
                    cv2.rectangle(frame, (x, y), (x + w, y + h),
                                  (0, 200, 0), 2)

                yield frame_para_jpeg(frame)
                time.sleep(0.05)  # dá tempo de variar a pose entre amostras

            if captura["capturadas"] >= NUM_AMOSTRAS:
                pessoas = carregar_pessoas()
                pessoas[nome] = captura["papel"]
                salvar_pessoas(pessoas)
                treinar_modelo()
                captura["concluido"] = True
        finally:
            captura["ativo"] = False
            camera.release()


@app.route("/video/reconhecimento")
def video_reconhecimento():
    marcar_presenca = request.args.get("modo") != "testes"
    return Response(gerar_video_reconhecimento(marcar_presenca),
                    mimetype="multipart/x-mixed-replace; boundary=frame")


def gerar_video_reconhecimento(marcar_presenca=True):
    """Reconhece o maior rosto do frame e decide se registra a presença.

    São precisos FRAMES_PARA_CONFIRMAR frames seguidos com a mesma pessoa
    reconhecida para liberar, ou com rosto desconhecido para negar. Depois
    de uma decisão a porta fica TEMPO_PORTA_ABERTA segundos sem decidir de
    novo (porta aberta ou mensagem de não reconhecido na tela).
    """
    if not os.path.exists(MODELO_PATH):
        return
    with trava_camera:
        with open(LABELS_PATH, encoding="utf-8") as f:
            labels = {int(k): v for k, v in json.load(f).items()}
        pessoas = carregar_pessoas()

        reconhecedor = cv2.face.LBPHFaceRecognizer_create()
        reconhecedor.read(MODELO_PATH)
        cascade = carregar_cascade()
        try:
            camera = abrir_camera()
        except RuntimeError:
            return

        ultimo_id = None      # id da pessoa, ou -1 para desconhecido
        sequencia = []        # confianças dos frames seguidos de ultimo_id
        falhas = 0
        try:
            while True:
                camera, frame, falhas = ler_frame(camera, falhas)
                verificar_timeout()
                if frame is None:
                    yield frame_para_jpeg(frame_sem_sinal())
                    continue
                cinza = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                rosto = detectar_rosto(cascade, cinza)

                with trava_estado:
                    if porta["reiniciar"]:
                        porta["reiniciar"] = False
                        ultimo_id, sequencia = None, []
                    bloqueado = time.time() < porta["bloqueado_ate"]
                    if not bloqueado and porta["estado"] in ("liberado", "negado"):
                        porta.update(estado="aguardando", progresso=0)

                if rosto is None:
                    ultimo_id, sequencia = None, []
                    if not bloqueado:
                        porta.update(estado="aguardando", progresso=0)
                    yield frame_para_jpeg(frame)
                    continue

                x, y, w, h = rosto
                recorte = preprocessar_rosto(cinza[y:y + h, x:x + w])
                id_pessoa, confianca = reconhecedor.predict(recorte)
                reconhecido = confianca <= LIMIAR_CONFIANCA
                nome = labels.get(id_pessoa, "?") if reconhecido else None

                with trava_estado:
                    if tentativa is not None:
                        tentativa["confiancas"].append(confianca)
                        if nome:
                            tentativa["previstos"].append(nome)

                if bloqueado:
                    # porta já respondeu: só desenha o resultado
                    if porta["estado"] == "liberado":
                        texto, cor = f"PRESENTE: {porta['nome']}", (0, 200, 0)
                    else:
                        texto, cor = "NAO RECONHECIDO", (0, 0, 255)
                else:
                    chave = id_pessoa if reconhecido else -1
                    if chave != ultimo_id:
                        ultimo_id, sequencia = chave, []
                    sequencia.append(confianca)
                    porta.update(estado="verificando",
                                 progresso=len(sequencia))

                    if len(sequencia) >= FRAMES_PARA_CONFIRMAR:
                        media = round(sum(sequencia) / len(sequencia), 1)
                        if reconhecido:
                            registrar_decisao("liberado", nome,
                                              pessoas.get(nome, "?"), media,
                                              marcar_presenca)
                            texto, cor = f"PRESENTE: {nome}", (0, 200, 0)
                        else:
                            registrar_decisao("negado", None, None, media,
                                              marcar_presenca)
                            texto, cor = "NAO RECONHECIDO", (0, 0, 255)
                        ultimo_id, sequencia = None, []
                    else:
                        texto = (f"Verificando... "
                                 f"{len(sequencia)}/{FRAMES_PARA_CONFIRMAR}")
                        cor = (0, 220, 220)

                cv2.rectangle(frame, (x, y), (x + w, y + h), cor, 2)
                cv2.putText(frame, texto, (x, y - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, cor, 2)
                cv2.putText(frame, f"conf: {confianca:.1f}", (x, y + h + 22),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, cor, 2)
                yield frame_para_jpeg(frame)
        finally:
            camera.release()


if __name__ == "__main__":
    print(f"Fonte de vídeo: {FONTE!r} | Rotação: {ROTACAO}°")
    print("Abra http://localhost:5000 no navegador")
    app.run(host="0.0.0.0", port=5000, threaded=True)

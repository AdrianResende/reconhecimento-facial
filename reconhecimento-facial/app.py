# -*- coding: utf-8 -*-
"""
Dashboard web de reconhecimento facial para universidade.

Cadastra pessoas com nome e papel (Professor/Estudante) e reconhece
mostrando quem é e qual o papel.

Uso:
    python app.py                                   # webcam do notebook
    python app.py http://192.168.10.140:4747/video 90   # iPhone (com rotação)

Depois abra http://localhost:5000 no navegador.
"""

import os
import sys
import json
import time
import shutil
import threading

import cv2

from haar import carregar_cascade, parse_fonte_e_rotacao, girar_frame
from cadastrar import (
    BASE_DIR, DATASET_DIR, MODELO_PATH, LABELS_PATH,
    NUM_AMOSTRAS, detectar_rosto, preprocessar_rosto, treinar_modelo,
)

try:
    from flask import (
        Flask, Response, jsonify, redirect, render_template, request, url_for,
    )
except ImportError:
    sys.exit("Flask não instalado. Rode: pip install -r requirements.txt")

PESSOAS_PATH = os.path.join(BASE_DIR, "pessoas.json")  # nome -> papel
PAPEIS = ["Professor", "Estudante"]

LIMIAR_CONFIANCA = 50.0
FRAMES_PARA_CONFIRMAR = 10

app = Flask(__name__)

# Fonte de vídeo e rotação vêm da linha de comando (iguais aos outros scripts)
FONTE, ROTACAO = parse_fonte_e_rotacao(sys.argv)

# Só um stream pode usar a câmera por vez
trava_camera = threading.Lock()

# Estado do cadastro em andamento (lido pela página via /cadastro/status)
captura = {
    "ativo": False, "nome": None, "papel": None,
    "capturadas": 0, "concluido": False, "erro": None,
}

# Última pessoa confirmada pelo reconhecimento (mostrada na página)
ultimo_confirmado = {"nome": None, "papel": None, "hora": None}


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


def abrir_camera():
    camera = cv2.VideoCapture(FONTE)
    if not camera.isOpened():
        raise RuntimeError(f"Não foi possível abrir a fonte de vídeo: {FONTE!r}")
    return camera


def frame_para_jpeg(frame):
    ok, jpeg = cv2.imencode(".jpg", frame)
    return (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n"
            + jpeg.tobytes() + b"\r\n") if ok else b""


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


@app.route("/reconhecer")
def reconhecer():
    if not os.path.exists(MODELO_PATH):
        return redirect(url_for("index"))
    return render_template("reconhecer.html")


@app.route("/reconhecer/status")
def reconhecer_status():
    return jsonify(**ultimo_confirmado)


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
        try:
            while captura["ativo"] and captura["capturadas"] < NUM_AMOSTRAS:
                ok, frame = camera.read()
                if not ok:
                    continue
                frame = girar_frame(frame, ROTACAO)
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


@app.route("/video/reconhecer")
def video_reconhecer():
    return Response(gerar_video_reconhecer(),
                    mimetype="multipart/x-mixed-replace; boundary=frame")


def gerar_video_reconhecer():
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

        ultimo_id = None
        frames_seguidos = 0
        try:
            while True:
                ok, frame = camera.read()
                if not ok:
                    continue
                frame = girar_frame(frame, ROTACAO)
                cinza = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                rostos = cascade.detectMultiScale(
                    cinza, scaleFactor=1.2, minNeighbors=5, minSize=(80, 80))

                if len(rostos) == 0:
                    ultimo_id = None
                    frames_seguidos = 0

                for (x, y, w, h) in rostos:
                    recorte = preprocessar_rosto(cinza[y:y + h, x:x + w])
                    id_pessoa, confianca = reconhecedor.predict(recorte)

                    if confianca <= LIMIAR_CONFIANCA:
                        if id_pessoa == ultimo_id:
                            frames_seguidos += 1
                        else:
                            ultimo_id = id_pessoa
                            frames_seguidos = 1

                        nome = labels.get(id_pessoa, "?")
                        papel = pessoas.get(nome, "?")
                        if frames_seguidos >= FRAMES_PARA_CONFIRMAR:
                            texto = f"{nome} - {papel}"
                            # professor em azul, estudante em verde
                            cor = ((255, 140, 0) if papel == "Professor"
                                   else (0, 200, 0))
                            ultimo_confirmado.update(
                                nome=nome, papel=papel,
                                hora=time.strftime("%H:%M:%S"))
                        else:
                            texto = (f"Verificando... "
                                     f"{frames_seguidos}/{FRAMES_PARA_CONFIRMAR}")
                            cor = (0, 220, 220)
                    else:
                        ultimo_id = None
                        frames_seguidos = 0
                        texto = "Desconhecido"
                        cor = (0, 0, 255)

                    cv2.rectangle(frame, (x, y), (x + w, y + h), cor, 2)
                    cv2.putText(frame, texto, (x, y - 10),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, cor, 2)

                yield frame_para_jpeg(frame)
        finally:
            camera.release()


if __name__ == "__main__":
    print(f"Fonte de vídeo: {FONTE!r} | Rotação: {ROTACAO}°")
    print("Abra http://localhost:5000 no navegador")
    app.run(host="0.0.0.0", port=5000, threaded=True)

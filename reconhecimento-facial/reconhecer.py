# -*- coding: utf-8 -*-
"""
Reconhecimento facial ("login").

Abre a câmera e verifica se o rosto é de uma pessoa cadastrada. Quando a
identidade é confirmada por vários frames seguidos, executa uma ação
(por padrão, abre o Relógio no navegador — personalize em executar_acao).

Uso:
    python reconhecer.py                                # webcam do notebook
    python reconhecer.py http://192.168.0.15:4747/video # câmera do iPhone
"""

import os
import sys
import json
import time
import webbrowser

import cv2

from haar import carregar_cascade

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODELO_PATH = os.path.join(BASE_DIR, "modelo_lbph.yml")
LABELS_PATH = os.path.join(BASE_DIR, "labels.json")

# Limiar de decisão do LBPH: abaixo disso consideramos "mesma pessoa".
# Quanto MENOR, mais rigoroso. Se estiver rejeitando você mesmo, suba aos
# poucos (55, 60...); se aceitar outras pessoas, desça (45, 40...).
LIMIAR_CONFIANCA = 50.0

# Quantos frames seguidos precisam reconhecer a MESMA pessoa para confirmar.
# Evita que um único frame "sortudo" identifique a pessoa errada.
FRAMES_PARA_CONFIRMAR = 10

# Depois de executar a ação, espera esse tempo antes de poder disparar de
# novo (senão a ação repetiria a cada frame enquanto você olha para a câmera)
COOLDOWN_ACAO_SEGUNDOS = 30


def executar_acao(nome):
    """Ação executada quando a identidade é confirmada.

    Troque o conteúdo desta função pelo que você quiser: abrir um programa,
    tocar um som, chamar uma API, acender uma luz...
    """
    print(f"\n>>> Identidade confirmada: {nome}! Abrindo o Relógio... <<<\n")
    pagina = os.path.join(os.path.dirname(BASE_DIR), "index.html")
    webbrowser.open(f"file://{pagina}")


def abrir_camera(fonte):
    """Abre a webcam (índice numérico) ou um stream de vídeo (URL)."""
    camera = cv2.VideoCapture(fonte)
    if not camera.isOpened():
        raise RuntimeError(
            f"Não foi possível abrir a fonte de vídeo: {fonte!r}. "
            "Se for a câmera do iPhone, confira se o app está transmitindo "
            "e se o celular está na mesma rede Wi-Fi."
        )
    return camera


def main():
    if not (os.path.exists(MODELO_PATH) and os.path.exists(LABELS_PATH)):
        print("Modelo não encontrado. Cadastre alguém primeiro: python cadastrar.py")
        return

    with open(LABELS_PATH, encoding="utf-8") as f:
        labels = {int(k): v for k, v in json.load(f).items()}

    reconhecedor = cv2.face.LBPHFaceRecognizer_create()
    reconhecedor.read(MODELO_PATH)

    cascade = carregar_cascade()

    # Fonte de vídeo: webcam (0) ou URL passada na linha de comando
    fonte = 0
    if len(sys.argv) > 1:
        fonte = sys.argv[1]
        if fonte.isdigit():
            fonte = int(fonte)
    camera = abrir_camera(fonte)

    print("Reconhecendo... Pressione 'q' para sair.")

    # Contagem de frames consecutivos reconhecendo a mesma pessoa
    ultimo_id = None
    frames_seguidos = 0
    ultima_acao = 0.0  # quando a ação foi executada pela última vez

    while True:
        ok, frame = camera.read()
        if not ok:
            continue

        cinza = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        rostos = cascade.detectMultiScale(
            cinza, scaleFactor=1.2, minNeighbors=5, minSize=(80, 80)
        )

        if len(rostos) == 0:
            # ninguém na frente da câmera: zera a contagem
            ultimo_id = None
            frames_seguidos = 0

        for (x, y, w, h) in rostos:
            recorte = cv2.resize(cinza[y:y + h, x:x + w], (200, 200))
            recorte = cv2.equalizeHist(recorte)
            id_pessoa, confianca = reconhecedor.predict(recorte)

            if confianca <= LIMIAR_CONFIANCA:
                # frame reconheceu; só confirma após vários frames seguidos
                if id_pessoa == ultimo_id:
                    frames_seguidos += 1
                else:
                    ultimo_id = id_pessoa
                    frames_seguidos = 1

                nome = labels.get(id_pessoa, "?")
                if frames_seguidos >= FRAMES_PARA_CONFIRMAR:
                    texto = f"{nome} confirmado ({confianca:.0f})"
                    cor = (0, 255, 0)   # verde: identidade confirmada

                    # dispara a ação (respeitando o cooldown)
                    if time.time() - ultima_acao >= COOLDOWN_ACAO_SEGUNDOS:
                        ultima_acao = time.time()
                        executar_acao(nome)
                else:
                    texto = (f"Verificando {nome}... "
                             f"{frames_seguidos}/{FRAMES_PARA_CONFIRMAR}")
                    cor = (0, 255, 255)  # amarelo: ainda verificando
            else:
                ultimo_id = None
                frames_seguidos = 0
                texto = f"Desconhecido ({confianca:.0f})"
                cor = (0, 0, 255)  # vermelho: não reconhecido

            cv2.rectangle(frame, (x, y), (x + w, y + h), cor, 2)
            cv2.putText(frame, texto, (x, y - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, cor, 2)

        cv2.imshow("Reconhecimento - pressione 'q' para sair", frame)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    camera.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()

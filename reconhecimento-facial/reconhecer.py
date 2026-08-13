# -*- coding: utf-8 -*-
"""
Reconhecimento facial ("login").

Abre a webcam e verifica se o rosto na frente da câmera é de uma pessoa
cadastrada. Quanto MENOR a confiança do LBPH, mais parecido é o rosto.
Uso: python reconhecer.py
"""

import os
import json

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


def main():
    if not (os.path.exists(MODELO_PATH) and os.path.exists(LABELS_PATH)):
        print("Modelo não encontrado. Cadastre alguém primeiro: python cadastrar.py")
        return

    with open(LABELS_PATH, encoding="utf-8") as f:
        labels = {int(k): v for k, v in json.load(f).items()}

    reconhecedor = cv2.face.LBPHFaceRecognizer_create()
    reconhecedor.read(MODELO_PATH)

    cascade = carregar_cascade()
    camera = cv2.VideoCapture(0)
    if not camera.isOpened():
        raise RuntimeError("Não foi possível abrir a webcam (índice 0).")

    print("Reconhecendo... Pressione 'q' para sair.")

    # Contagem de frames consecutivos reconhecendo a mesma pessoa
    ultimo_id = None
    frames_seguidos = 0

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

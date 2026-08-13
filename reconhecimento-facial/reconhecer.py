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

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODELO_PATH = os.path.join(BASE_DIR, "modelo_lbph.yml")
LABELS_PATH = os.path.join(BASE_DIR, "labels.json")

# Limiar de decisão do LBPH: abaixo disso consideramos "mesma pessoa".
# Ajuste se necessário (valores típicos entre 50 e 80).
LIMIAR_CONFIANCA = 70.0


def main():
    if not (os.path.exists(MODELO_PATH) and os.path.exists(LABELS_PATH)):
        print("Modelo não encontrado. Cadastre alguém primeiro: python cadastrar.py")
        return

    with open(LABELS_PATH, encoding="utf-8") as f:
        labels = {int(k): v for k, v in json.load(f).items()}

    reconhecedor = cv2.face.LBPHFaceRecognizer_create()
    reconhecedor.read(MODELO_PATH)

    cascade = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    )
    camera = cv2.VideoCapture(0)
    if not camera.isOpened():
        raise RuntimeError("Não foi possível abrir a webcam (índice 0).")

    print("Reconhecendo... Pressione 'q' para sair.")

    while True:
        ok, frame = camera.read()
        if not ok:
            continue

        cinza = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        rostos = cascade.detectMultiScale(
            cinza, scaleFactor=1.2, minNeighbors=5, minSize=(80, 80)
        )

        for (x, y, w, h) in rostos:
            recorte = cv2.resize(cinza[y:y + h, x:x + w], (200, 200))
            id_pessoa, confianca = reconhecedor.predict(recorte)

            if confianca <= LIMIAR_CONFIANCA:
                nome = labels.get(id_pessoa, "?")
                texto = f"{nome} ({confianca:.0f})"
                cor = (0, 255, 0)  # verde: reconhecido
            else:
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

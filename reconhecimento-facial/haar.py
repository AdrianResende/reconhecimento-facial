# -*- coding: utf-8 -*-
"""Carrega o Haar cascade de rosto, baixando o XML se necessário.

A partir do OpenCV 5 o arquivo haarcascade_frontalface_default.xml não vem
mais junto com o pacote pip, então baixamos direto do repositório do OpenCV.
"""

import os
import urllib.request

import cv2

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CASCADE_NOME = "haarcascade_frontalface_default.xml"
CASCADE_LOCAL = os.path.join(BASE_DIR, CASCADE_NOME)
CASCADE_URL = (
    "https://raw.githubusercontent.com/opencv/opencv/4.x/data/haarcascades/"
    + CASCADE_NOME
)


def carregar_cascade():
    """Retorna um CascadeClassifier de rosto pronto para uso."""
    # 1) tenta o arquivo que vem com o OpenCV (existe até a versão 4.x)
    caminho_pacote = os.path.join(cv2.data.haarcascades, CASCADE_NOME)
    if os.path.exists(caminho_pacote):
        cascade = cv2.CascadeClassifier(caminho_pacote)
        if not cascade.empty():
            return cascade

    # 2) usa a cópia local, baixando na primeira execução
    if not os.path.exists(CASCADE_LOCAL):
        print("Baixando detector de rosto (haarcascade)...")
        urllib.request.urlretrieve(CASCADE_URL, CASCADE_LOCAL)

    cascade = cv2.CascadeClassifier(CASCADE_LOCAL)
    if cascade.empty():
        raise RuntimeError(
            f"Não foi possível carregar o detector de rosto ({CASCADE_LOCAL}). "
            "Apague o arquivo e rode de novo para baixá-lo novamente."
        )
    return cascade

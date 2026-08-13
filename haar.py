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


def parse_fonte_e_rotacao(argv):
    """Lê a fonte de vídeo e a rotação da linha de comando.

    Uso: script.py [fonte] [rotacao]
    fonte: índice da webcam (0, 1...) ou URL de stream. Padrão: 0.
    rotacao: 90, 180 ou 270 graus, para corrigir vídeo deitado. Padrão: 0.
    """
    fonte = 0
    rotacao = 0
    if len(argv) > 1:
        fonte = argv[1]
        if fonte.isdigit():
            fonte = int(fonte)
    if len(argv) > 2:
        rotacao = int(argv[2])
    return fonte, rotacao


def girar_frame(frame, rotacao):
    """Gira o frame em 90/180/270 graus no sentido horário."""
    if rotacao == 90:
        return cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
    if rotacao == 180:
        return cv2.rotate(frame, cv2.ROTATE_180)
    if rotacao == 270:
        return cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)
    return frame


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

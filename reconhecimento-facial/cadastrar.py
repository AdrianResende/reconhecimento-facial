# -*- coding: utf-8 -*-
"""
Cadastro de pessoa para reconhecimento facial.

Abre a webcam, captura várias amostras do rosto e treina o modelo LBPH.
Uso: python cadastrar.py
"""

import os
import json

import cv2
import numpy as np

from haar import carregar_cascade

# Diretórios/arquivos usados pelo sistema
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATASET_DIR = os.path.join(BASE_DIR, "dataset")
MODELO_PATH = os.path.join(BASE_DIR, "modelo_lbph.yml")
LABELS_PATH = os.path.join(BASE_DIR, "labels.json")

NUM_AMOSTRAS = 50          # quantas fotos do rosto capturar
TAMANHO_ROSTO = (200, 200)  # tamanho padronizado das imagens de rosto


def preprocessar_rosto(recorte_cinza):
    """Padroniza o rosto: redimensiona e equaliza a iluminação.

    A equalização deixa o modelo menos sensível à luz do ambiente, o que
    reduz falsos positivos. Deve ser usada igualmente no cadastro e no
    reconhecimento.
    """
    rosto = cv2.resize(recorte_cinza, TAMANHO_ROSTO)
    return cv2.equalizeHist(rosto)


def detectar_rosto(cascade, frame_cinza):
    """Retorna o maior rosto encontrado no frame (x, y, w, h) ou None."""
    rostos = cascade.detectMultiScale(
        frame_cinza, scaleFactor=1.2, minNeighbors=5, minSize=(80, 80)
    )
    if len(rostos) == 0:
        return None
    # pega o maior rosto (mais próximo da câmera)
    return max(rostos, key=lambda r: r[2] * r[3])


def capturar_amostras(nome):
    """Captura NUM_AMOSTRAS imagens do rosto pela webcam."""
    cascade = carregar_cascade()
    camera = cv2.VideoCapture(0)
    if not camera.isOpened():
        raise RuntimeError("Não foi possível abrir a webcam (índice 0).")

    pasta_pessoa = os.path.join(DATASET_DIR, nome)
    os.makedirs(pasta_pessoa, exist_ok=True)

    print(f"\nOlhe para a câmera. Capturando {NUM_AMOSTRAS} amostras...")
    print("Pressione 'q' para cancelar.\n")

    capturadas = 0
    while capturadas < NUM_AMOSTRAS:
        ok, frame = camera.read()
        if not ok:
            continue

        cinza = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        rosto = detectar_rosto(cascade, cinza)

        if rosto is not None:
            x, y, w, h = rosto
            recorte = preprocessar_rosto(cinza[y:y + h, x:x + w])
            cv2.imwrite(os.path.join(pasta_pessoa, f"{capturadas:03d}.png"), recorte)
            capturadas += 1

            cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
            cv2.putText(frame, f"Amostra {capturadas}/{NUM_AMOSTRAS}", (x, y - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

        cv2.imshow("Cadastro - pressione 'q' para cancelar", frame)
        if cv2.waitKey(100) & 0xFF == ord("q"):
            break

    camera.release()
    cv2.destroyAllWindows()

    if capturadas < NUM_AMOSTRAS:
        print(f"Cadastro cancelado ({capturadas} amostras capturadas).")
        return False

    print(f"{capturadas} amostras salvas em {pasta_pessoa}")
    return True


def treinar_modelo():
    """Treina o LBPH com todas as pessoas do dataset e salva o modelo."""
    imagens, ids = [], []
    labels = {}  # id numérico -> nome

    pessoas = sorted(os.listdir(DATASET_DIR))
    for id_pessoa, nome in enumerate(pessoas):
        pasta = os.path.join(DATASET_DIR, nome)
        if not os.path.isdir(pasta):
            continue
        labels[id_pessoa] = nome
        for arquivo in os.listdir(pasta):
            img = cv2.imread(os.path.join(pasta, arquivo), cv2.IMREAD_GRAYSCALE)
            if img is not None:
                imagens.append(img)
                ids.append(id_pessoa)

    if not imagens:
        raise RuntimeError("Nenhuma imagem no dataset para treinar.")

    reconhecedor = cv2.face.LBPHFaceRecognizer_create()
    reconhecedor.train(imagens, np.array(ids))
    reconhecedor.write(MODELO_PATH)

    with open(LABELS_PATH, "w", encoding="utf-8") as f:
        json.dump(labels, f, ensure_ascii=False, indent=2)

    print(f"Modelo treinado com {len(imagens)} imagens de {len(labels)} pessoa(s).")
    print(f"Modelo salvo em: {MODELO_PATH}")


def main():
    nome = input("Digite o nome da pessoa a cadastrar: ").strip()
    if not nome:
        print("Nome vazio. Abortando.")
        return

    if capturar_amostras(nome):
        treinar_modelo()
        print("\nCadastro concluído! Agora rode: python reconhecer.py")


if __name__ == "__main__":
    main()

# Reconhecimento Facial com Python + OpenCV

Sistema básico de reconhecimento facial usando o algoritmo **LBPH**
(Local Binary Patterns Histograms) do OpenCV.

## Instalação

```bash
cd reconhecimento-facial
pip install -r requirements.txt
```

> É necessário o pacote `opencv-contrib-python` (não o `opencv-python` comum),
> pois o módulo `cv2.face` só existe na versão contrib.

## Como usar

### 1. Cadastrar uma pessoa

```bash
python cadastrar.py
```

- Digite o nome da pessoa.
- Olhe para a webcam: o script captura 30 fotos do seu rosto e treina o modelo.
- As fotos ficam em `dataset/<nome>/` e o modelo em `modelo_lbph.yml`.

### 2. Entrar / testar reconhecimento

```bash
python reconhecer.py
```

- A webcam abre e o sistema verifica se o rosto é de uma pessoa cadastrada.
- **Verde** = mesma pessoa reconhecida (mostra o nome).
- **Vermelho** = "Desconhecido" (não é uma pessoa cadastrada).
- Pressione `q` para sair.

## Ajustes

- `LIMIAR_CONFIANCA` em `reconhecer.py` (padrão 70): no LBPH, quanto **menor**
  o valor da confiança, mais parecido é o rosto. Diminua o limiar para deixar
  o sistema mais rigoroso, aumente para mais tolerante.
- `NUM_AMOSTRAS` em `cadastrar.py` (padrão 30): mais amostras = modelo melhor.

## Estrutura

```
reconhecimento-facial/
├── cadastrar.py       # cadastra pessoa (captura fotos + treina modelo)
├── reconhecer.py      # reconhece pela webcam ("login")
├── requirements.txt
├── dataset/           # gerado automaticamente (fotos dos rostos)
├── modelo_lbph.yml    # gerado automaticamente (modelo treinado)
└── labels.json        # gerado automaticamente (id -> nome)
```

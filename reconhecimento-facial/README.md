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

## Usando a câmera do iPhone

1. Instale no iPhone um app que transmita a câmera pela rede, como o
   **DroidCam** (grátis na App Store).
2. Abra o app: ele mostra um endereço tipo `http://192.168.0.15:4747/video`.
3. Com o iPhone e o computador na **mesma rede Wi-Fi**, passe esse endereço
   para os scripts:

```bash
python cadastrar.py http://192.168.0.15:4747/video
python reconhecer.py http://192.168.0.15:4747/video
```

Sem argumento, os scripts usam a webcam do notebook (índice 0).

## Ação ao confirmar a identidade

Quando a mesma pessoa é reconhecida por vários frames seguidos (retângulo
verde), o `reconhecer.py` executa uma ação — por padrão, abre o Relógio
(`index.html`) no navegador. Para trocar, edite a função `executar_acao()`
em `reconhecer.py`. Há um cooldown de 30s para a ação não repetir enquanto
você continua na frente da câmera (`COOLDOWN_ACAO_SEGUNDOS`).

## Ajustes

- `LIMIAR_CONFIANCA` em `reconhecer.py` (padrão 50): no LBPH, quanto **menor**
  o valor da confiança, mais parecido é o rosto. Diminua o limiar para deixar
  o sistema mais rigoroso, aumente para mais tolerante.
- `FRAMES_PARA_CONFIRMAR` em `reconhecer.py` (padrão 10): quantos frames
  seguidos precisam reconhecer a mesma pessoa antes de confirmar (verde).
- `NUM_AMOSTRAS` em `cadastrar.py` (padrão 50): mais amostras = modelo melhor.

> Se mudar o cadastro (ou atualizar o código de pré-processamento), apague a
> pasta `dataset/` e cadastre de novo — as fotos antigas ficam incompatíveis.

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

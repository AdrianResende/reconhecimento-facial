# Reconhecimento Facial — Universidade

Sistema de reconhecimento facial com Python + OpenCV (algoritmo **LBPH**) e
dashboard web em Flask para cadastrar **professores e estudantes** e
reconhecê-los pela câmera, mostrando o nome e o papel de cada pessoa.

## Instalação

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

> É necessário o pacote `opencv-contrib-python` (não o `opencv-python` comum),
> pois o módulo `cv2.face` só existe na versão contrib.

## Dashboard web

```bash
python app.py                                     # webcam do notebook
python app.py http://192.168.10.140:4747/video 90 # câmera do iPhone (com rotação)
```

Depois abra **http://localhost:5000** no navegador:

- **Painel**: totais e lista de cadastrados, com botão de remover.
- **Cadastrar**: informe nome + papel (Professor/Estudante); a câmera abre na
  própria página e captura as 50 fotos sozinha, com barra de progresso; o
  modelo é treinado ao final.
- **Reconhecer**: vídeo ao vivo; professor aparece em azul, estudante em
  verde, desconhecido em vermelho. Abaixo do vídeo fica o último confirmado.

Os dados ficam em `pessoas.json` (nome → papel) + `dataset/` + `modelo_lbph.yml`.

## Usando a câmera do iPhone

1. Instale no iPhone um app que transmita a câmera pela rede, como o
   **DroidCam** (grátis na App Store).
2. Abra o app: ele mostra um endereço tipo `http://192.168.10.140:4747/video`.
3. Com o iPhone e o computador na **mesma rede Wi-Fi**, passe esse endereço
   como primeiro argumento dos scripts.
4. Se o vídeo aparecer **deitado** (celular em pé), passe a rotação em graus
   como segundo argumento: `90`, `180` ou `270`.

```bash
python app.py http://192.168.10.140:4747/video 90
```

Sem argumentos, usa a webcam do notebook (índice 0).

## Scripts de linha de comando (alternativa sem dashboard)

- `python cadastrar.py [fonte] [rotacao]` — cadastra uma pessoa (sem papel).
- `python reconhecer.py [fonte] [rotacao]` — reconhece pela câmera; ao
  confirmar a identidade, executa a função `executar_acao()` (personalizável),
  com cooldown de 30s (`COOLDOWN_ACAO_SEGUNDOS`).

## Ajustes

- `LIMIAR_CONFIANCA` (padrão 50): no LBPH, quanto **menor** a confiança, mais
  parecido é o rosto. Diminua para mais rigoroso, aumente para mais tolerante.
- `FRAMES_PARA_CONFIRMAR` (padrão 10): quantos frames seguidos precisam
  reconhecer a mesma pessoa antes de confirmar (verde).
- `NUM_AMOSTRAS` em `cadastrar.py` (padrão 50): mais amostras = modelo melhor.

> Se mudar o código de pré-processamento, apague a pasta `dataset/` e cadastre
> de novo — as fotos antigas ficam incompatíveis.

## Estrutura

```
├── app.py             # dashboard web (Flask)
├── templates/         # páginas do dashboard
├── cadastrar.py       # cadastro por linha de comando
├── reconhecer.py      # reconhecimento por linha de comando
├── haar.py            # detector de rosto (compartilhado)
├── requirements.txt
├── dataset/           # gerado automaticamente (fotos dos rostos)
├── modelo_lbph.yml    # gerado automaticamente (modelo treinado)
├── labels.json        # gerado automaticamente (id -> nome)
└── pessoas.json       # gerado automaticamente (nome -> papel)
```

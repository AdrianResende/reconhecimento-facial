# Reconhecimento Facial — Registro de Presença

Protótipo do TCC *Sistema de Reconhecimento Facial para Automatização do
Registro de Presença em Aulas Universitárias* (UNIPAC). Python + OpenCV
(algoritmo **LBPH**) e dashboard web em Flask: cadastra **professores e
estudantes**, simula uma câmera na porta da sala que registra a presença de
quem entra e tem um módulo de testes que gera o relatório para o TCC.

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
- **Presença**: simula a câmera na porta da sala. Pessoa cadastrada
  reconhecida em 10 frames seguidos → porta abre e a presença é registrada na
  lista do dia (sem duplicar: se entrar de novo aparece "presença já
  registrada"); rosto desconhecido em 10 frames → "rosto não reconhecido".
  A lista (presentes e ausentes de cada dia) exporta para CSV.
- **Testes**: escolha o caso de teste e o participante, clique em *Iniciar
  tentativa* (ou barra de espaço) e o sistema registra sozinho a decisão,
  quem foi reconhecido, o tempo e a confiança, classificando como
  VP/FN/FP/VN. As tentativas **não** entram na lista de presença. Mostra o
  progresso, as métricas (acurácia, TAR, FRR, FAR), exporta CSV e gera o
  relatório para o TCC em **.docx (ABNT)** ou como **seção LaTeX para o
  artigo no template da SBC** (.zip com o .tex e as figuras).

Os dados ficam em `pessoas.json` (nome → papel) + `dataset/` + `modelo_lbph.yml`;
a lista de presença em `presencas.json` e as tentativas de teste em
`testes.json`.

## Roteiro dos testes

1. Cadastre os 5 participantes (Adrian, Pedro, Breno, Gustavo, Taagny) com o
   iPhone **já na posição fixa** em que vai ficar nos testes (altura do rosto).
2. Abra **Testes**. A página já seleciona o próximo participante pendente;
   cada participante faz **5 tentativas** em cada caso:

| Caso | Grupo | Condição | Presença esperada |
|------|-------|----------|----------|
| CT01 | Distância | Frontal a 50 cm (referência) | Registrada |
| CT02 | Distância | Muito perto, 25 cm | Registrada |
| CT03 | Distância | 1 m | Registrada |
| CT04 | Distância | 2 m | Registrada |
| CT05 | Ângulo | Rosto girado ~30° | Registrada |
| CT06 | Ângulo | Quase de perfil ~60° | Registrada |
| CT07 | Ângulo | Cabeça inclinada ~20° cima/baixo | Registrada |
| CT08 | Fraude | Foto do participante na tela de outro celular | Não registrada |
| CT09 | Fraude | Vídeo do participante na tela de outro celular | Não registrada |
| CT10 | Fraude | Pessoa não cadastrada (opcional, qualquer visitante) | Não registrada |

3. Antes do CT08/CT09, tire uma foto e grave um vídeo curto de cada um.
4. Se uma tentativa sair errada por falha do procedimento (pessoa saiu do
   lugar, alguém passou na frente), use **Descartar** e refaça.
5. No fim, confira título/autor/curso/instituição e gere:
   - **Relatório .docx (ABNT)**: metodologia, casos de teste, tabelas,
     gráficos, análise e apêndice com todas as tentativas;
   - **Seção LaTeX (SBC)**: `secao_testes.tex` + `figuras/`; no artigo basta
     `\input{secao_testes}` (instruções no `LEIAME.txt` dentro do .zip).

   Pela linha de comando: `python relatorio.py` (docx) ou
   `python relatorio.py latex`.

São 9 casos × 5 pessoas × 5 tentativas = 225 tentativas (+5 do visitante);
cada uma leva ~5–10 s, então reserve cerca de 1h30.

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
- `TIMEOUT_TENTATIVA` em `app.py` (padrão 15 s): tempo máximo de uma
  tentativa de teste; sem decisão nesse tempo conta como rejeição.
- `NUM_AMOSTRAS` em `cadastrar.py` (padrão 50): mais amostras = modelo melhor.

> Se mudar o código de pré-processamento, apague a pasta `dataset/` e cadastre
> de novo — as fotos antigas ficam incompatíveis.

## Estrutura

```
├── app.py             # dashboard web (Flask): cadastro, presença e testes
├── casos_teste.py     # casos de teste e cálculo das métricas
├── relatorio.py       # gera o relatório dos testes (.docx ABNT e LaTeX SBC)
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

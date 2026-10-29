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
- **Porta**: simulação de porta. Pessoa cadastrada reconhecida em 10 frames
  seguidos → porta abre (ACESSO LIBERADO); rosto desconhecido em 10 frames
  seguidos → ACESSO NEGADO. Mostra o histórico dos últimos acessos.
- **Testes**: escolha o caso de teste e o participante, clique em *Iniciar
  tentativa* (ou barra de espaço) e o sistema registra sozinho a decisão da
  porta, quem foi reconhecido, o tempo e a confiança, classificando como
  VP/FN/FP/VN. Mostra o progresso, as métricas (acurácia, TAR, FRR, FAR),
  exporta CSV e gera o **relatório .docx (ABNT) para o TCC**.

Os dados ficam em `pessoas.json` (nome → papel) + `dataset/` + `modelo_lbph.yml`;
as tentativas de teste ficam em `testes.json`.

## Roteiro dos testes

1. Cadastre os 5 participantes (Adrian, Pedro, Breno, Gustavo, Taagny) com o
   iPhone **já na posição fixa** em que vai ficar nos testes (altura do rosto).
2. Abra **Testes**. A página já seleciona o próximo participante pendente;
   cada participante faz **5 tentativas** em cada caso:

| Caso | Grupo | Condição | Esperado |
|------|-------|----------|----------|
| CT01 | Distância | Frontal a 50 cm (referência) | Liberado |
| CT02 | Distância | Muito perto, 25 cm | Liberado |
| CT03 | Distância | 1 m | Liberado |
| CT04 | Distância | 2 m | Liberado |
| CT05 | Ângulo | Rosto girado ~30° | Liberado |
| CT06 | Ângulo | Quase de perfil ~60° | Liberado |
| CT07 | Ângulo | Cabeça inclinada ~20° cima/baixo | Liberado |
| CT08 | Fraude | Foto do participante na tela de outro celular | Negado |
| CT09 | Fraude | Vídeo do participante na tela de outro celular | Negado |
| CT10 | Fraude | Pessoa não cadastrada (opcional, qualquer visitante) | Negado |

3. Antes do CT08/CT09, tire uma foto e grave um vídeo curto de cada um.
4. Se uma tentativa sair errada por falha do procedimento (pessoa saiu do
   lugar, alguém passou na frente), use **Descartar** e refaça.
5. No fim, preencha título/autor/curso/instituição e clique em
   **Gerar relatório .docx**. Ele traz metodologia, casos de teste, tabelas,
   gráficos, análise e o registro de todas as tentativas. Também dá para
   gerar pela linha de comando: `python relatorio.py`.

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
├── app.py             # dashboard web (Flask): cadastro, porta e testes
├── casos_teste.py     # casos de teste e cálculo das métricas
├── relatorio.py       # gera o relatório .docx (ABNT) dos testes
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

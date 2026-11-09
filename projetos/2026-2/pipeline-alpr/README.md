# Explorando Modelos Generativos para Aprimorar o Reconhecimento de Placas de Veículos em Cenários do Mundo Real

## Informações Gerais

| Item | Informação |
| :--- | :--- |
| **Curso** | Engenharia de Computação |
| **Instituição** | PUCPR — Escola Politécnica |
| **Ano / Semestre** | 2026/2 |
| **Disciplina** | IOPT (Implementação e Operação de Projeto Transformador) |
| **Estudante(s)** | Beatriz Perotto Muniz |
| **Orientador(a)** | Prof. Dr. Rayson Laroca |
| **Coorientador(a)** | — |
| **Área Técnica** | Inteligência Artificial / Visão Computacional |

> **Nota Institucional:** Este diretório armazena **exclusivamente os códigos-fonte e scripts de teste** do projeto. Os documentos formais do TCC (*Proposta, Plano de Projeto, Especificação Física Inicial/Revisada e Relatório Técnico Final*) e as *Apresentações das Defesas* encontram-se arquivados no **Canvas PUCPR**.

---

## Resumo Técnico do Software / Firmware

O reconhecimento automático de placas (ALPR) perde desempenho em imagens de baixa resolução, e há poucas bases rotuladas com esse tipo de degradação. Este projeto usa modelos generativos para degradar placas em alta resolução e acrescentar essas imagens ao treino de reconhecedores de caracteres (OCR). O fluxo tem quatro módulos, que se comunicam por diretórios (o rótulo da placa fica no nome de cada arquivo, então cada módulo roda separado):

1. **Módulo I — extração:** recorta e padroniza em 128×64 as placas da base RodoSol-ALPR, com detectores YOLO26 (placa e cantos).
2. **Módulo II — degradação sintética:** degrada as placas limpas com o CycleGAN-Turbo (gerador principal) ou com uma degradação paramétrica (OpenCV + Albumentations), usada como controle.
3. **Módulo III — dataset híbrido:** junta as imagens degradadas ao treino do LRLPR-26 e gera os índices `train.txt` e `val.txt`.
4. **Módulo IV — OCR:** implementa o treino e a avaliação dos reconhecedores PARSeq, SVTRv2 e IGTR (sendo o comitê final formado pelo PARSeq e pelo IGTR), combinando as leituras das cinco imagens de cada veículo por votação por posição de caractere (MVCP).

No teste oficial do LRLPR-26, a linha de base (só dados da competição) teve 74,17% de taxa de reconhecimento. Com as imagens degradadas pelo CycleGAN-Turbo o resultado foi 75,43%, e com a degradação paramétrica, 74,87%. A análise completa está no Relatório Técnico Final, no Canvas.

**O que este repositório não inclui:** datasets, pesos de modelos e os códigos originais de terceiros (DMT, TSIT, ADM, detectores YOLO, CycleGAN-Turbo e OpenOCR). Para a execução dos Módulos II e IV, é necessário clonar os repositórios correspondentes (`img2img-turbo` e `OpenOCR`), conforme detalhado nas instruções de execução. Os parâmetros de cada treino e os links dos códigos originais estão descritos em `data/modelos/MODELOS.md`.

---

## Tecnologias e Ferramentas Utilizadas

- **Linguagens de Programação:** Python 3.10
- **Frameworks e Bibliotecas:** PyTorch, PyTorch Lightning, OpenCV, NumPy, Albumentations, Ultralytics (YOLO26), `img2img-turbo` (CycleGAN-Turbo sobre o SD-Turbo: `diffusers`, `transformers`, `peft`), OpenOCR (SVTRv2 e IGTR), `timm`, `nltk`
- **Banco de Dados / Mensageria:** não se aplica
- **Plataforma Alvo / Hardware:** Linux com GPU NVIDIA (RTX 4090 de 24 GB nos Módulos II e IV; H100 de 80 GB no treino do comitê de reconhecedores)
- **Ferramentas de Compilação e Depuração:** conda, `unittest`

---

## Estrutura do Código

```text
.
├── data/
│   ├── datasets/       # DATASETS.md (como obter as bases)
│   └── modelos/        # MODELOS.md (como os modelos foram treinados)
├── src/
│   ├── modulo1/        # extração e retificação das placas
│   ├── modulo2/        # degradação: CycleGAN-Turbo e paramétrica
│   ├── modulo3/        # construção do dataset híbrido
│   └── modulo4/        # treino e avaliação do OCR (PARSeq, SVTRv2, IGTR, MVCP)
├── tests/
│   ├── integracao/     # testes de caixa preta (notebooks do Colab)
│   └── unitarios/      # testes de caixa branca (Módulos I e III)
├── requirements.txt
└── README.md
```

---

## Pré-requisitos e Instalação

### 1. Clonar o repositório
```bash
git clone https://github.com/CoordENGCOMPPUCPR/TCC-Engenharia-de-Computacao.git
cd TCC-Engenharia-de-Computacao/projetos/2026-2/pipeline-alpr
```

### 2. Repositórios Externos Necessários

Alguns módulos utilizam implementações oficiais de terceiros que devem ser clonadas à parte:
- **CycleGAN-Turbo (`img2img-turbo`):** Necessário para a geração generativa do Módulo II. Deve ser clonado a partir do repositório oficial:
  ```bash
  git clone https://github.com/GaParmar/img2img-turbo.git
  ```
- **OpenOCR:** Necessário caso deseje treinar ou avaliar os modelos **SVTRv2** e/ou **IGTR** no Módulo IV (requer a variável de ambiente `OPENOCR_ROOT` apontando para o caminho absoluto do repositório clonado):
  ```bash
  git clone https://github.com/Topdu/OpenOCR.git src/modulo4/OpenOCR
  export OPENOCR_ROOT=$(pwd)/src/modulo4/OpenOCR
  ```
  *(Para o modelo principal PARSeq, nenhuma clonagem é necessária — os pesos base são carregados diretamente via `torch.hub`).*

### 3. Configurar ambiente e executar cada módulo

Os datasets (LRLPR-26, RodoSol-ALPR) e os pesos não estão no repositório. A obtenção das bases está em `data/datasets/DATASETS.md`.

```bash
conda create -n tcc python=3.10 -y && conda activate tcc
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
pip install -r requirements.txt
```

**Módulo I** (extração e retificação das placas da RodoSol-ALPR; precisa dos pesos `yolo.pt` e `pose.pt`, não incluídos):

Primeiro, organize a base bruta da RodoSol com o script auxiliar:
```bash
python src/modulo1/auxiliar/organizar_rodosol.py \
    --rodosol /caminho/rodosol_bruta --saida rodosol_organizada
```

Em seguida, execute a extração das placas limpas:
- **Opção A (Sem retificação — padrão adotado no pipeline final / T6):**
  ```bash
  python src/modulo1/modulo1.py --entrada rodosol_organizada \
      --pesos_yolo yolo.pt --pesos_pose pose.pt \
      --saida dataset_limpas --sem_retificacao
  ```
- **Opção B (Com retificação de perspectiva via cantos — estudo comparativo / T7):**
  ```bash
  python src/modulo1/modulo1.py --entrada rodosol_organizada \
      --pesos_yolo yolo.pt --pesos_pose pose.pt \
      --saida dataset_limpas_retificadas
  ```

**Módulo II**, com uma das duas opções (somente o split de treino deve ser degradado):
```bash
# degradação paramétrica
python src/modulo2/modulo2_parametrica.py \
    --dir_limpas dataset_limpas/train --saida dir_sinteticas

# CycleGAN-Turbo (precisa do checkpoint treinado e do repositório img2img-turbo)
python src/modulo2/modulo2_cyclegan.py \
    --dir_limpas dataset_limpas/train --checkpoint model.pkl \
    --repo_cyclegan img2img-turbo --saida dir_sinteticas
```
O CycleGAN-Turbo foi treinado com `transformers==4.35.2`, `diffusers==0.25.1`, `peft==0.10.0` e `huggingface_hub==0.25.2`.

**Módulo III** (prepara o LRLPR-26 e monta o conjunto híbrido):
```bash
python src/modulo3/pre_modulo3_LRLPR.py \
    --lrlpr /caminho/LRLPR-26 --saida lrlpr_preparado
python src/modulo3/modulo3_LRLPR.py \
    --dir_lrlpr lrlpr_preparado --dir_sinteticas dir_sinteticas \
    --proporcao 1.0 --saida dataset_hibrido_lrlpr
```
Com `--proporcao 0.0` o conjunto fica só com imagens reais (linha de base).

**Módulo IV** (treino e avaliação dos reconhecedores OCR com fusão MVCP por veículo):

- **Opção A — Comitê Completo (PARSeq + SVTRv2 + IGTR com fusão MVCP por veículo):**
  ```bash
  python src/modulo4/modulo4.py --dataset dataset_hibrido_lrlpr \
      --test_dir /caminho/LRLPR-26/test --modelos parseq svtr igtr
  ```
- **Opção B — Somente Avaliação (utilizando checkpoints pré-treinados, sem retreinar):**
  ```bash
  python src/modulo4/modulo4.py --so_avaliar \
      --pesos parseq:checkpoints/parseq.ckpt,svtr:checkpoints/svtr.pth,igtr:checkpoints/igtr.pth \
      --test_dir /caminho/LRLPR-26/test --modelos parseq svtr igtr
  ```

O relatório com a taxa de reconhecimento (acurácia de placa completa) e CER (Character Error Rate) é gravado automaticamente em `modulo4_report.txt`.

---

## Procedimentos de Teste e Validação (Plano de Testes)

**Caixa branca** — testes unitários dos Módulos I e III (74 testes):

```bash
python3 -m unittest discover -s tests/unitarios -v
```

**Caixa preta** — notebooks do Colab em `tests/integracao/`, que treinam o PARSeq com cada fonte de imagens degradadas e avaliam no teste do LRLPR-26, por veículo:

- degradação paramétrica sobre a RodoSol
- modelos generativos sobre a RodoSol
- impacto da retificação de perspectiva
- avaliação por CER

Eles usam caminhos do Google Drive, que precisam ser ajustados para rodar.

---

## Histórico de Versões (Marcos IOPT)

| Versão | Etapa | Data | Descrição |
| :--- | :--- | :--- | :--- |
| `v1.0.0-final` | IOPT — 4º Bim (Implementação Final) | 08/11/2026 | Versão final completa dos quatro módulos, com testes de caixa branca e integração |

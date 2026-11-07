# Sistema Vestível de Telemetria Contínua por Termometria de Contato

## Informações Gerais

| Item | Informação |
| :--- | :--- |
| **Curso** | Engenharia de Computação |
| **Instituição** | PUCPR — Escola Politécnica |
| **Ano / Semestre** | 2026/2 |
| **Disciplina** | IOPT (Implementação e Operação de Projeto Transformador) |
| **Estudante(s)** | Eugênio Polistchuk Berendsen |
| **Orientador(a)** | Prof. Me. Marcelo do Carmo Camargo Gaiotto |
| **Coorientador(a)** | Prof. Dr. Rüdiger Daniel Ollhoff |
| **Área Técnica** | Sistemas Embarcados / IoT / Engenharia de Software |

> **Nota Institucional:** Este diretório armazena **exclusivamente os códigos-fonte e scripts de teste** do projeto. Os documentos formais do TCC (*Proposta, Plano de Projeto, Especificação Física Inicial/Revisada e Relatório Técnico Final*) e as *Apresentações das Defesas* encontram-se arquivados no **Canvas PUCPR**.

---

## Resumo Técnico do Software / Firmware

Plataforma de aquisição e telemetria térmica voltada à detecção precoce da
necrobacilose interdigital em bovinos leiteiros, por termometria de contato
nos membros pélvicos.

**Arquitetura em blocos:**

- **Nó sensor (`src/firmware/Tornozeleira`):** ESP32 com cinco termistores NTC por
  membro e transceptor LoRa RFM95W (915 MHz).
- **Gateway (`src/firmware/gateway`):** ESP32 com RFM95W; recebe os pacotes LoRa e
  envia as leituras à API por HTTP.
- **Backend (`src/backend`):** API em Flask com PostgreSQL. Inclui o detector, que
  combina o diferencial espacial entre sensores, o desvio em relação à linha de base
  individual por janela horária e, com os dois membros monitorados, o diferencial
  contralateral.
- **Frontend (`src/frontend`):** painel web com o estado dos animais, os alertas,
  os gráficos e a exportação das leituras em CSV.

---

## Tecnologias e Ferramentas Utilizadas
- **Linguagens de Programação:** Python, JavaScript, C/C++ (Arduino), SQL
- **Frameworks e Bibliotecas:** Flask, psycopg2, gunicorn, Vite, Chart.js, RadioLib, ArduinoJson
- **Banco de Dados / Mensageria:** PostgreSQL (Aiven); comunicação LoRa (915 MHz) e HTTP
- **Plataforma Alvo / Hardware:** ESP32, transceptor LoRa RFM95W, termistores NTC; Render (API) e Vercel (painel)
- **Ferramentas de Compilação e Depuração:** Arduino IDE, npm, Vite

---

## Estrutura do Código

```text
.
├── data/
│   └── exemplos/       # Arquivos de configuração de exemplo
├── src/
│   ├── backend/
│   │   ├── app.py               # Rotas da API
│   │   ├── servico_detector.py  # Liga o detector ao banco de dados
│   │   ├── detector/            # Lógica do detector
│   │   ├── migrations/          # Alterações do banco de dados
│   │   ├── schema.sql           # Esquema inicial do banco
│   │   ├── scripts/             # Migração e experimentos
│   │   └── sim/                 # Simulador de dados sintéticos
│   ├── firmware/
│   │   ├── Tornozeleira/        # Nó sensor
│   │   └── gateway/             # Gateway LoRa/Wi-Fi
│   └── frontend/
│       ├── src/                 # Código do painel
│       └── scripts/             # API falsa para testes locais
├── tests/
│   ├── integracao/
│   └── unitarios/
└── README.md
```

---

## Pré-requisitos e Instalação

### 1. Clonar o repositório
```bash
git clone https://github.com/CoordENGCOMPPUCPR/TCC-Engenharia-de-Computacao.git
cd TCC-Engenharia-de-Computacao/projetos/2026-2/vestivel-termometria-contato
```

### 2. Configurar e executar cada módulo

**Firmware (`src/firmware/`)**

1. Instale a Arduino IDE, o suporte a placas ESP32 e as bibliotecas RadioLib e ArduinoJson.
2. Em `gateway/gateway.ino`, preencha `WIFI_SSID`, `WIFI_PASSWORD` e `API_KEY`.
3. Selecione a placa e a porta, e grave `gateway/gateway.ino` no gateway e `Tornozeleira/Vaca.ino` no nó sensor.

**Backend (`src/backend/`)**

Requer Python 3.12 e um banco PostgreSQL. No Prompt de Comando do Windows:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
set DATABASE_URL=postgresql://usuario:senha@host:porta/banco
set API_KEY=uma_chave_de_sua_escolha
psql "%DATABASE_URL%" -f schema.sql
python scripts/migrar.py --aplicar
python app.py
```

A API fica em `http://localhost:5000`. Em um banco local sem SSL, defina também `set DB_SSLMODE=disable`. Em produção, o comando é `gunicorn app:app`.
Em um banco do Aiven, a migração também exige `--confirmo-producao`.

**Frontend (`src/frontend/`)**

Requer Node.js.

```bash
npm install
copy env.example .env
npm run dev
```

Em `.env`, `VITE_API_BASE_URL` define o endereço da API. Para testar sem backend, rode `npm run mock-api` em outro terminal e use `VITE_API_BASE_URL=http://localhost:5050`.

---

## Procedimentos de Teste e Validação (Plano de Testes)

### Testes automatizados

Cobrem o detector e o simulador, sem precisar de banco de dados nem de hardware. Na pasta do projeto:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install pytest tzdata==2026.5
pytest tests -q
```

- `tests/unitarios/`: validade dos sensores, cálculo dos componentes, montagem dos pacotes, linha de base e pacotes atrasados.
- `tests/integracao/`: abertura e fechamento de alertas, falha de sensor e retomada do estado salvo.

A API, o firmware e o painel web não têm testes automatizados.

### Experimentos com dados sintéticos

Executados a partir de `src/backend/`. Podem levar bastante tempo:

```bash
python scripts/fase1c.py cp05
python scripts/fase1c.py cp01
python scripts/fase1c.py e
python scripts/fase1c.py rampa
```

Os resultados são gravados em `docs/resultados/fase1c/`. Esses experimentos usam `sim/`, com premissas sintéticas, e não substituem a validação em animais.

---

## Histórico de Versões (Marcos CDPT / IOPT)

| Versão | Etapa | Data | Descrição |
| :--- | :--- | :--- | :--- |
| `v0.5.0` | IOPT — 3º Bim (Protótipo) | 06/10/2026 | Protótipo funcional da cadeia de telemetria e roteiro de testes |
| `v1.0.0` | IOPT — 4º Bim (Implementação Final) | 06/11/2026 | Versão final do código; telemetria validada em bancada e detector avaliado com dados sintéticos |

# Título do Projeto

## Informações Gerais

| Item | Informação |
| :--- | :--- |
| **Curso** | Engenharia de Computação |
| **Instituição** | PUCPR — Escola Politécnica |
| **Ano / Semestre** | 2026/1 |
| **Disciplina** | CDPT (Concepção e Design de Projeto Transformador) / IOPT (Implementação e Operação de Projeto Transformador) |
| **Estudante(s)** | Victor Romano Ribeiro Pizzato |
| **Orientador(a)** | Valter Klein Junior |
| **Área Técnica** | Sistemas Embarcados / IoT / Engenharia de Software |

> **Nota Institucional:** Este diretório armazena **exclusivamente os códigos-fonte e scripts de teste** do projeto. Os documentos formais do TCC (*Proposta, Plano de Projeto, Especificação Física Inicial/Revisada e Relatório Técnico Final*) e as *Apresentações das Defesas* encontram-se arquivados no **Canvas PUCPR**.

---

## Resumo Técnico do Software / Firmware
O projeto consiste em uma solução de IoT composta por dois ecossistemas principais:
1. **Módulo de Coleta/Sensoriamento (Raspberry Pi):** Executa serviços em segundo plano (producer/consumer) em Python para leitura e manipulação local dos dados de sensores.
2. **Aplicação Web (Servidor/Dashboard):** Desenvolvida em Elixir com Phoenix LiveView 1.2.0 e PostgreSQL para gerenciamento, persistência e visualização interativa em tempo real.

---

## Tecnologias e Ferramentas Utilizadas
- **Linguagens de Programação:** Elixir 1.20.4, Erlang/OTP 28.4.3, Python 3, JavaScript (Node.js 24.9.0)
- **Frameworks e Bibliotecas:** Phoenix LiveView 1.2.0, Ecto
- **Banco de Dados / Mensageria:** PostgreSQL
- **Plataforma Alvo / Hardware:** Raspberry Pi 3 Model B (Raspberry Pi OS), Servidor Linux
- **Ferramentas de Gerenciamento e Serviço:** `systemd`, `mix`, `npm`

---

## Estrutura do Código

```text
.
├── assets/             # Ativos do frontend web (JavaScript/CSS gerenciados via Node.js)
├── config/             # Configurações da aplicação Phoenix (dev.exs, prod.exs, etc.)
├── lib/                # Código-fonte principal Elixir (Phoenix LiveView e contexto de negócios)
├── priv/
│   └── repo/           # Migrações e scripts de seed do PostgreSQL
├── sensors/            # Scripts Python executados no Raspberry Pi (Producer / Consumer)
│   ├── consumer.py
│   └── producer.py
└── README.md           # Instruções de instalação, compilação e execução
```

---

## Pré-requisitos e Instalação

### Requisitos Prévios do Sistema
- **Elixir:** `1.20.4`
- **Erlang/OTP:** `28.4.3`
- **Node.js:** `24.9.0`
- **PostgreSQL** (rodando localmente)
- **Hardware Embarcado:** Raspberry Pi 3 Model B rodando Raspberry Pi OS com `python3`

---

### 1. Clonar o repositório
```bash
git clone https://github.com/CoordENGCOMPPUCPR/TCC-Engenharia-de-Computacao.git
cd TCC-Engenharia-de-Computacao
```

---

### 2. Configurar e executar a Aplicação Web (Phoenix LiveView)

#### Step 1: Instalar as dependências do Elixir
```bash
mix deps.get
```

#### Step 2: Configurar o Banco de Dados
Certifique-se de que o PostgreSQL está em execução e com as credenciais corretas configuradas em `config/dev.exs`. Para criar o banco, rodar as migrações e popular dados de teste (seeds):
```bash
mix ecto.setup
```

#### Step 3: Instalar as dependências de Assets (Node.js)
```bash
npm install --prefix assets
```

#### Step 4: Iniciar o Servidor Phoenix
Execute o servidor em modo de desenvolvimento:
```bash
mix phx.server
```
*Ou para rodar via shell interativo IEx:*
```bash
iex -S mix phx.server
```

Abra o seu navegador e acesse: 👉 [`http://localhost:4000`](http://localhost:4000)

---

### 3. Configurar os Serviços no Raspberry Pi 3B

#### Step 1: Dar permissões de execução aos scripts
No diretório `/home/raspberry/sensors`:
```bash
chmod +x /home/raspberry/sensors/producer.py
chmod +x /home/raspberry/sensors/consumer.py
```

#### Step 2: Criar os arquivos de serviço do `systemd` em `/etc/systemd/system/`

##### Arquivo `/etc/systemd/system/sensor-consumer.service`:
```ini
[Unit]
Description=Sensor Data Consumer Service
After=network.target

[Service]
Type=simple
User=raspberry
WorkingDirectory=/home/raspberry/sensors
ExecStart=/usr/bin/python3 /home/raspberry/sensors/consumer.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

##### Arquivo `/etc/systemd/system/sensor-producer.service`:
```ini
[Unit]
Description=Sensor Data Producer Service
After=network.target

[Service]
Type=simple
User=raspberry
WorkingDirectory=/home/raspberry/sensors
ExecStart=/usr/bin/python3 /home/raspberry/sensors/producer.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

#### Step 3: Ativar e inicializar os serviços no sistema
```bash
# Recarregar o daemon do systemd
sudo systemctl daemon-reload

# Habilitar a inicialização automática no boot
sudo systemctl enable sensor-consumer.service
sudo systemctl enable sensor-producer.service

# Iniciar os serviços imediatamente
sudo systemctl start sensor-consumer.service
sudo systemctl start sensor-producer.service
```

#### Monitoramento dos Serviços
```bash
# Verificar status
sudo systemctl status sensor-consumer.service
sudo systemctl status sensor-producer.service

# Visualizar logs em tempo real
journalctl -u sensor-consumer.service -f
journalctl -u sensor-producer.service -f
```

---

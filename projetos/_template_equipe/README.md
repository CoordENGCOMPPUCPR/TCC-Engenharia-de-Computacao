# Título do Projeto

## Informações Gerais

| Item | Informação |
| :--- | :--- |
| **Curso** | Engenharia de Computação |
| **Instituição** | PUCPR — Escola Politécnica |
| **Ano / Semestre** | 2026/1 |
| **Disciplina** | CDPT (Concepção e Design de Projeto Transformador) / IOPT (Implementação e Operação de Projeto Transformador) |
| **Estudante(s)** | Nome Completo do Estudante 1, Nome Completo do Estudante 2 |
| **Orientador(a)** | Prof(a). Nome Completo |
| **Coorientador(a)** | (Opcional) |
| **Área Técnica** | Sistemas Embarcados / IoT / Inteligência Artificial / Visão Computacional / Engenharia de Software |

> **Nota Institucional:** Este diretório armazena **exclusivamente os códigos-fonte e scripts de teste** do projeto. Os documentos formais do TCC (*Proposta, Plano de Projeto, Especificação Física Inicial/Revisada e Relatório Técnico Final*) e as *Apresentações das Defesas* encontram-se arquivados no **Canvas PUCPR**.

---

## Resumo Técnico do Software / Firmware
Descreva de forma objetiva o problema resolvido pelo software/firmware, a arquitetura em blocos implementada e os módulos que compõem a solução.

---

## Tecnologias e Ferramentas Utilizadas
- **Linguagens de Programação:** (ex.: Python 3.11, C/C++, TypeScript)
- **Frameworks e Bibliotecas:** (ex.: FastAPI, React, ESP-IDF, PyTorch, OpenCV)
- **Banco de Dados / Mensageria:** (ex.: PostgreSQL, MQTT, Redis)
- **Plataforma Alvo / Hardware:** (ex.: ESP32, STM32, Raspberry Pi 4, Linux Container)
- **Ferramentas de Compilação e Depuração:** (ex.: PlatformIO, GCC, Docker)

---

## Estrutura do Código

```text
.
├── data/
│   ├── datasets/       # Amostras leves de dados para validação
│   └── exemplos/       # Arquivos de configuração (.env.example) e entradas de teste
├── src/
│   ├── backend/        # Serviços, APIs e algoritmos de processamento
│   ├── firmware/       # Código embarcado e drivers de hardware
│   └── frontend/       # Interface com o usuário (Web / Mobile / Desktop)
├── tests/
│   ├── integracao/     # Testes de integração entre blocos funcionais
│   └── unitarios/      # Testes unitários dos módulos de software
└── README.md           # Instruções de instalação, compilação e execução
```

---

## Pré-requisitos e Instalação

### 1. Clonar o repositório
```bash
git clone https://github.com/CoordENGCOMPPUCPR/TCC-Engenharia-de-Computacao.git
```

### 2. Configurar e executar cada módulo
- **Firmware (`src/firmware/`):**
  ```bash
  # Exemplo de comando de compilação / gravação
  ```
- **Backend (`src/backend/`):**
  ```bash
  # Exemplo de criação de ambiente virtual, instalação de dependências e execução
  ```
- **Frontend (`src/frontend/`):**
  ```bash
  # Exemplo de instalação e inicialização da interface
  ```

---

## Procedimentos de Teste e Validação (Plano de Testes)
Comandos para executar os testes automatizados (Caixa Branca / Caixa Preta) referentes à validação dos blocos funcionais do projeto:

```bash
# Exemplo: pytest tests/ ou npm test
```

---

## Histórico de Versões (Marcos CDPT / IOPT)

| Versão | Etapa | Data | Descrição |
| :--- | :--- | :--- | :--- |
| `v0.1.0` | CDPT — 1º Bim (Plano de Projeto) | DD/MM/AAAA | Estrutura inicial do repositório e definição das tecnologias |
| `v0.2.0` | CDPT — 2º Bim (Especificação Física) | DD/MM/AAAA | Esqueleto modular e provas de conceito dos algoritmos principais |
| `v0.5.0` | IOPT — 3º Bim (Protótipo) | DD/MM/AAAA | Implementação funcional do protótipo e roteiro de testes |
| `v1.0.0` | IOPT — 4º Bim (Implementação Final) | DD/MM/AAAA | Versão final completa, validada e com ajustes de robustez/ergonomia |

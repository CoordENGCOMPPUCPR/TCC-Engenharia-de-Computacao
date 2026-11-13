# Retrofit de Túnel de Vento Subsônico (*Italia Didacta PN 20 DNT*)

## Informações Gerais

| Item | Informação |
| :--- | :--- |
| **Curso** | Engenharia de Computação |
| **Instituição** | PUCPR — Escola Politécnica |
| **Ano / Semestre** | 2026/2 |
| **Disciplina** | IOPT (Implementação e Operação de Projeto Transformador) |
| **Estudante(s)** | Vinícius Matheus Sary de Lima |
| **Orientador(a)** | Prof. Guilherme Nogueira |
| **Coorientador(a)** | Prof. César Neitzke |
| **Área Técnica** | Instrumentação Eletrônica / Aquisição de Dados (DAQ) / Sistemas Supervisórios (SCADA) |

> **Nota Institucional:** Este diretório armazena **exclusivamente os códigos-fonte** do projeto. Os documentos formais do TCC (*Proposta, Plano de Projeto, Especificação Física Inicial/Revisada e Relatório Técnico Final*) e as *Apresentações das Defesas* encontram-se arquivados no **Canvas PUCPR**.

---

## Resumo Técnico do Software

O software consiste em um sistema supervisório (SCADA) desenvolvido em **MATLAB App Designer** (`app_v10.m`) para modernização (*retrofit*) do túnel de vento subsônico didático **Italia Didacta PN 20 DNT** da Escola Politécnica da PUCPR.

O sistema realiza a leitura assíncrona em segundo plano (*background callback* a $1000\text{ Hz}$ por canal) da placa de aquisição **National Instruments NI USB-6211** acoplada à placa condicionadora dedicada (3× AD8226 para células de carga da balança DS Europe 514QD, 2× AD8210 para transdutores de pressão $4\text{ a }20\text{ mA}$ AutoTran 860, transmissor DY510 para torque e sensor indutivo NPN Sense C2D60K2412 no contador de bordas `ctr0`/`PFI0`). Toda a lógica de aquisição, filtragem digital Média Móvel Exponencial (EMA), rotinas de tara, visualização gráfica em **6 abas** (a $20\text{ FPS}$) e exportação de ensaios em formato **`.csv`** está consolidada em `src/frontend/app_v10.m`.

---

## Tecnologias e Ferramentas Utilizadas
- **Linguagens de Programação:** MATLAB (R2024a)
- **Frameworks e Bibliotecas:** MATLAB App Designer, Data Acquisition Toolbox, NI-DAQmx Support Package, MATLAB Compiler
- **Plataforma Alvo / Hardware:** Windows 10/11 (64 bits) + Placa de Aquisição National Instruments NI USB-6211 + Placa Condicionadora Analógica (KiCad 10.0)
- **Ferramentas de Compilação:** MATLAB Application Compiler (`compiler.build.standaloneApplication`)

---

## Estrutura do Código

```text
.
├── data/
│   ├── datasets/       # Diretório padrão do template
│   └── exemplos/       # Arquivo de persistência de parâmetros e taras (config_tunel.mat)
├── src/
│   ├── backend/        # Integrado diretamente à classe principal em src/frontend/app_v10.m
│   ├── firmware/       # Não aplicável (aquisição direta via hardware NI USB-6211 / NI-DAQmx)
│   └── frontend/       # Interface supervisória Desktop em MATLAB App Designer (app_v10.m e main.m)
├── tests/
│   ├── integracao/     # Diretório padrão do template
│   └── unitarios/      # Diretório padrão do template
└── README.md           # Instruções de instalação, compilação e execução
```

---

## Pré-requisitos e Instalação

### 1. Clonar o repositório
```bash
git clone https://github.com/CoordENGCOMPPUCPR/TCC-Engenharia-de-Computacao.git
```

### 2. Executar no MATLAB
Com o **MATLAB R2024a+** (e o driver **NI-DAQmx** instalado para operação com a placa física):
```matlab
cd('src/frontend');
main
```
*(Ou instancie diretamente `app = app_v10;` no Command Window do MATLAB).*

### 3. Compilar Executável Standalone (`.exe`)
```matlab
cd('src/frontend');
compiler.build.standaloneApplication('main.m', ...
    'ExecutableName', 'DAS_WindTunnel_v10', ...
    'AdditionalFiles', {'app_v10.m', '../../data/exemplos/config_tunel.mat'});
```

---

## Histórico de Versões (Marcos CDPT / IOPT)

| Versão | Etapa | Descrição |
| :--- | :--- | :--- |
| `v1.0.0` | IOPT — 4º Bim (Implementação Final) | Entrega final consolidada do sistema supervisório SCADA (`app_v10.m` e `main.m`) |

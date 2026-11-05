# Repositório de Códigos de TCC — Engenharia de Computação (PUCPR)

Bem-vindo ao repositório oficial da **Coordenação do Curso de Engenharia de Computação da PUCPR (Escola Politécnica)** destinado ao versionamento e compartilhamento dos **códigos-fonte** desenvolvidos nos **Trabalhos de Conclusão de Curso (Projeto Final de Curso)**.

---

## ⚠️ Diretriz Institucional Obrigatória: GitHub vs. Canvas

> **ATENÇÃO ESTUDANTES E ORIENTADORES:**
> Este repositório tem como finalidade **exclusiva** o versionamento dos **códigos dos softwares e firmwares** desenvolvidos ao longo do TCC.
>
> - **O que DEVE estar neste repositório (GitHub):**
>   - Código-fonte do sistema (`src/backend`, `src/frontend`, `src/firmware`, etc.);
>   - Scripts de testes automatizados e validação (`tests/unitarios`, `tests/integracao`);
>   - Amostras leves de dados de exemplo/configuração estritamente necessárias para execução (`data/`);
>   - Arquivo `README.md` técnico explicando como compilar, configurar, executar e testar o software.
>
> - **O que NÃO DEVE estar neste repositório (Arquivamento exclusivo no CANVAS):**
>   - Documentos formais das disciplinas **CDPT** e **IOPT** (*Proposta de Projeto, Plano de Projeto, Especificação Física Inicial, Especificação Física Revisada, Relatório Técnico Final, Artigos em PDF/DOCX*);
>   - Apresentações das bancas examinadoras (*Slides em PPTX/PDF*);
>   - Vídeos demonstrativos e gravações de defesas (*MP4, MKV, AVI, etc.*).
>   - **Todos os documentos escritos e apresentações devem ser submetidos exclusivamente no ambiente oficial da instituição: o Canvas PUCPR.**

---

## 📚 Alinhamento com as Fases do Projeto Final de Curso (CDPT e IOPT)

Conforme o **Manual do Projeto Final de Curso de Engenharia de Computação**, o desenvolvimento ocorre em dois semestres consecutivos (**CDPT** e **IOPT**). O versionamento do código neste repositório deve acompanhar as entregas bimestrais:

| Disciplina | Etapa / Bimestre | Entrega no Canvas (Documentação e Defesa) | Entrega no GitHub (Versionamento de Código) | Tag / Marco Sugerido |
| :--- | :--- | :--- | :--- | :--- |
| **CDPT** | **1º Bimestre** | Proposta + Plano de Projeto + Apresentação | Criação do diretório da equipe, `README.md` inicial e configuração de ambiente | `v0.1.0-plano` |
| **CDPT** | **2º Bimestre** | Especificação Física Inicial + Apresentação | Estrutura modular do projeto, provas de conceito (PoC) e interfaces definidas | `v0.2.0-especificacao` |
| **IOPT** | **3º Bimestre** | Especificação Física Revisada com Plano de Testes + Defesa do Protótipo | **Código do Protótipo funcional** + scripts de testes de validação | `v0.5.0-prototipo` |
| **IOPT** | **4º Bimestre** | Relatório Técnico Final + Defesa da Implementação Final | **Código da Implementação Final** completo, robusto, documentado e testado | `v1.0.0-final` |

---

## 📁 Estrutura de Organização do Repositório

O repositório é organizado por **Ano-Semestre** dentro do diretório [`projetos/`](./projetos/), onde cada equipe mantém sua pasta exclusiva seguindo o padrão da estrutura raiz:

```text
.
├── projetos/
│   ├── _template_equipe/                # Modelo padrão para copiar ao iniciar um novo TCC
│   │   ├── data/
│   │   │   ├── datasets/                # Amostras leves de dados para teste/execução
│   │   │   └── exemplos/                # Arquivos de entrada/configuração de exemplo
│   │   ├── src/
│   │   │   ├── backend/                 # APIs, microsserviços, processamento, modelos de IA
│   │   │   ├── firmware/                # Código de sistemas embarcados, IoT, microcontroladores
│   │   │   └── frontend/                # Interfaces web, mobile ou desktop
│   │   ├── tests/
│   │   │   ├── integracao/              # Testes de integração entre módulos (hardware/software)
│   │   │   └── unitarios/               # Testes unitários de funções e módulos isolados
│   │   └── README.md                    # Documentação técnica de instalação e execução do código
│   ├── 2026-1/                          # Projetos do 1º Semestre de 2026
│   └── 2026-2/                          # Projetos do 2º Semestre de 2026
├── src/                                 # Estrutura base de referência (backend, firmware, frontend)
├── tests/                               # Estrutura base de referência (integracao, unitarios)
├── data/                                # Estrutura base de referência (datasets, exemplos)
├── CONTRIBUTING.md                      # Guia passo a passo de uso do Git/GitHub para os estudantes
├── .gitignore                           # Filtro automático (bloqueia PDFs, DOCX, PPTX, vídeos e builds)
└── LICENSE                              # Termos de uso acadêmico PUCPR
```

---

## 🚀 Como Submeter o Código da sua Equipe (Resumo Rápido)

1. Faça um **Fork** (ou crie uma **Branch** caso já faça parte da equipe no GitHub) deste repositório.
2. Crie a pasta da sua equipe dentro do semestre correspondente usando o padrão `projetos/<ANO>-<SEMESTRE>/<slug-do-projeto>/` copiando o conteúdo de `projetos/_template_equipe/`.
3. Preencha o `README.md` da sua equipe com as instruções técnicas de compilação, dependências e execução do software.
4. Adicione **apenas códigos-fonte, scripts de teste e arquivos leves de configuração/dados de exemplo**.
5. Abra um **Pull Request** para a branch `main` descrevendo a etapa da entrega (ex.: *IOPT - Protótipo* ou *IOPT - Implementação Final*).

👉 Consulte o guia detalhado em **[CONTRIBUTING.md](./CONTRIBUTING.md)** para ver todos os comandos Git passo a passo.

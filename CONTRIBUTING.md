# Guia de Contribuição e Versionamento para Estudantes (TCC — Engenharia de Computação PUCPR)

Este documento descreve o fluxo de trabalho padrão para que as equipes de **CDPT** (*Concepção e Design de Projeto Transformador*) e **IOPT** (*Implementação e Operação de Projeto Transformador*) realizem o versionamento de seus códigos no repositório da Coordenação.

---

## 1. Regras Fundamentais antes do Commit

1. **Somente Código no GitHub:**
   - **Permitido:** Códigos-fonte (`.py`, `.c`, `.cpp`, `.h`, `.ino`, `.ts`, `.js`, `.java`, `.rs`, `.vhd`, `.v`, etc.), arquivos de manifesto/dependências (`requirements.txt`, `package.json`, `platformio.ini`, `CMakeLists.txt`, `Dockerfile`), testes automatizados e amostras leves de dados (`.csv`, `.json` pequenos de exemplo).
   - **Proibido (Arquivar no Canvas PUCPR):** Documentos do TCC (`Proposta`, `Plano de Projeto`, `Especificação Física`, `Relatório Técnico Final`, `Artigos` em `.pdf` ou `.docx`), apresentações (`.pptx`, `.pdf`) e vídeos (`.mp4`, `.mov`).
2. **Segurança e Credenciais:**
   - Nunca suba senhas, chaves de API ou arquivos `.env` reais. Crie um arquivo `.env.example` com valores fictícios explicando quais variáveis são necessárias.
3. ** Pastas Proibidas:**
   - Não crie pastas `docs/`, `presentation/`, `videos/` ou `releases/`. Uma verificação automática do GitHub Actions validará cada Pull Request para garantir o cumprimento desta regra.

---

## 2. Passo a Passo para Enviar o Código da Equipe

### Passo 1: Clonar o Repositório (ou seu Fork)
```bash
git clone https://github.com/CoordENGCOMPPUCPR/TCC-Engenharia-de-Computacao.git
cd TCC-Engenharia-de-Computacao
```

### Passo 2: Criar uma Branch para a Entrega da sua Equipe
Use o padrão `<semestre>/<nome-curto-do-projeto>-<etapa>`:
```bash
git checkout -b 2026-2/sistema-iot-monitoramento-prototipo
```

### Passo 3: Criar a Pasta do Projeto a partir do Template
Copie a pasta `projetos/_template_equipe` para dentro do semestre correspondente (ex.: `projetos/2026-2/sistema-iot-monitoramento`):

**No Windows (PowerShell):**
```powershell
Copy-Item -Path "projetos\_template_equipe" -Destination "projetos\2026-2\sistema-iot-monitoramento" -Recurse
```

**No Linux / macOS / Git Bash:**
```bash
cp -r projetos/_template_equipe projetos/2026-2/sistema-iot-monitoramento
```

### Passo 4: Organizar os Arquivos do Software
Distribua o código da equipe nas subpastas do seu projeto:
- `src/backend/` — Serviços, APIs, modelos de IA, scripts de processamento.
- `src/frontend/` — Aplicação Web, Mobile ou interface gráfica Desktop.
- `src/firmware/` — Código de microcontroladores (ESP32, STM32, Arduino, Raspberry Pi Pico, FPGA, etc.).
- `tests/unitarios/` e `tests/integracao/` — Scripts de teste (Caixa Branca e Caixa Preta conforme especificado no Plano de Testes).
- `data/exemplos/` e `data/datasets/` — Apenas dados de exemplo leves necessários para testar o código localmente.
- `README.md` — Atualize com os nomes completos dos integrantes, professor orientador, tecnologias, instruções de instalação e comandos de execução.

### Passo 5: Realizar Commits Semânticos
Utilize mensagens claras que registrem a evolução do desenvolvimento:
- `feat: implementa leitura dos sensores via MQTT no firmware`
- `fix: corrige calculo de filtragem no backend`
- `test: adiciona testes de integracao da API REST`
- `docs: atualiza instrucoes de compilacao no README da equipe`

```bash
git add .
git commit -m "feat: adiciona implementacao do prototipo (IOPT - 3o Bimestre)"
git push origin 2026-2/sistema-iot-monitoramento-prototipo
```

### Passo 6: Abrir o Pull Request (PR)
1. Acesse o repositório no GitHub (`https://github.com/CoordENGCOMPPUCPR`).
2. Clique em **Compare & pull request**.
3. Preencha o formulário automático do Pull Request informando:
   - Título do Projeto, Integrantes da Equipe e Professor Orientador;
   - Disciplina e Etapa (**CDPT 1º/2º Bim** ou **IOPT 3º/4º Bim**);
   - Confirmação no checklist de que a documentação escrita e a apresentação foram entregues no **Canvas**.

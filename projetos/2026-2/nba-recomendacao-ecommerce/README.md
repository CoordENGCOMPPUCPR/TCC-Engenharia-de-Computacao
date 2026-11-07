# Sistema de Recomendação de Next Best Action Adaptativo para eCommerce Baseado em Perfil Comportamental Dinâmico de Sessão

Relatório Técnico Final, Engenharia de Computação, PUCPR (2026)

- **Integrante:** Mariana Alves da Silva
- **Orientador:** Prof. Dr. Julio Cesar Nievola

Sistema que decide, durante uma sessão anônima de eCommerce e sem histórico do usuário, se uma
intervenção deve ser oferecida e qual produto pode acompanhá-la. O modelo é treinado com outubro de
2019 e avaliado em novembro de 2019.

## Tecnologias

- Python, pandas, NumPy e SciPy
- mlxtend (FP-Growth, regras de associação)
- LightGBM, scikit-learn, Optuna e SHAP (classificação e explicação)
- FastAPI e Uvicorn (API)
- HTML e JavaScript (demonstração)
- pytest e httpx (testes)

---

## 1. Antes de começar

- **Python 3.9 a 3.12.** O projeto foi validado no 3.9 (macOS) e no 3.11 (Windows). No 3.13 a
  instalação falha.
- **macOS:** instale a biblioteca OpenMP, usada pelo LightGBM: `brew install libomp`.
- **Não é preciso baixar os dados para rodar.** Os modelos treinados já estão em `dataset/`. Os CSVs
  só são necessários para treinar ou avaliar de novo (seção 5).

Todos os comandos abaixo são executados dentro desta pasta, a que contém este README.

---

## 2. Passo a passo

### Passo 1: criar e ativar o ambiente virtual

macOS ou Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Windows (PowerShell):

```powershell
py -m venv .venv
.venv\Scripts\activate
```

Se o PowerShell não permitir a ativação, use o Prompt de Comando: `.venv\Scripts\activate.bat`.

Com o ambiente ativo, o nome `(.venv)` aparece no início da linha. A partir daqui, use `python` em
qualquer sistema.

### Passo 2: instalar as dependências

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

No fim deve aparecer `Successfully installed …`. O `requirements.txt` traz as versões exatas em que os
modelos e os resultados foram gerados. As mesmas versões estão no `setup.py`, que também permite
instalar o projeto como pacote: `python -m pip install -e ".[test]"`.

### Passo 3: rodar os testes

```bash
python -m pytest -q
```

Resultado esperado: `193 passed`. Os avisos (`warnings`) do matplotlib e do SHAP vêm dessas
bibliotecas e não indicam erro.

Os testes de caixa branca estão marcados com `@pytest.mark.caixa_branca`. Os demais são de caixa
preta. Para rodar só uma parte da suíte:

```bash
python -m pytest -q -m caixa_branca            # só caixa branca: 20 passed, 173 deselected
python -m pytest -q -m "not caixa_branca"      # só caixa preta: 173 passed, 20 deselected
python -m pytest -q tests/test_m4_nba.py       # um arquivo
python -m pytest -q tests/test_m4_nba.py::TestDecideStrongIntervention   # uma classe de testes
python -m pytest -q -k "below_theta2"          # testes cujo nome contém o texto
python -m pytest -v                            # mostra o nome e o resultado de cada teste
```

"Deselected" são os testes que ficaram de fora da seleção, e não testes que falharam.

### Passo 4: subir a API

```bash
python -m uvicorn src.api:app --port 8000
```

Espere a mensagem `Application startup complete` e deixe este terminal aberto.

### Passo 5: abrir a demonstração

Abra o arquivo `demo/demo.html` no navegador, com dois cliques. No macOS também funciona
`open demo/demo.html`.

- O topo da página deve mostrar **"API no ar"**.
- Clique num dos quatro cenários. A sessão é reproduzida evento a evento, e o painel da direita
  mostra a decisão do sistema.
- A linha **"Sessão"** do painel é um link que consulta a mesma decisão na API.

### Passo 6: encerrar

`Ctrl + C` no terminal da API e, em seguida, `deactivate`.

---

## 3. Cenários da demonstração

| Cenário | O que acontece | Decisão esperada |
|---|---|---|
| Carrinho em smartwatch | risco 92,6% | intervenção forte (cupom) com produto recomendado |
| Comprou sozinho | compra 70 s após o carrinho | sessão não pontuada |
| Risco moderado, sem regra aplicável | risco 89,0% | intervenção moderada, sem produto |
| Navegação tranquila | risco 43,7% | sem intervenção |

São sessões reais de novembro de 2019, reproduzidas com os mesmos eventos.

---

## 4. Explorar a API pelo Swagger (opcional)

Com a API no ar (passo 4), abra <http://127.0.0.1:8000/docs>. Todas as rotas funcionam do mesmo
jeito: clique na rota para abri-la, clique em **Try it out**, preencha os campos e clique em
**Execute**. A resposta aparece logo abaixo, em **Response body**.

O `user_session` dos eventos identifica a sessão em todas as rotas. As sessões ficam na memória da
API e se perdem quando ela é reiniciada.

### Fluxo 1: avaliar uma sessão inteira

1. Abra `POST /session` e clique em **Try it out**.
2. Em **Examples**, escolha um cenário, por exemplo *Carrinho em smartwatch — cupom e produto*, e
   clique em **Execute**. A resposta traz a ação (`action`), o risco de abandono (`p_abandon`), o
   produto recomendado (`recommended_product_id`) e a mensagem ao usuário (`intervention_message`).
3. Copie o `user_session` dos eventos do exemplo. No cenário do smartwatch, ele é
   `09f52458-e452-4ae9-8f8f-75ee3b6f77da`.
4. Abra `GET /session/{session_id}`, clique em **Try it out**, cole o valor em `session_id` e clique
   em **Execute**. A decisão é a mesma do passo 2.

Reenviar a mesma sessão pelo `POST /session` a reavalia do zero.

### Fluxo 2: enviar evento a evento e forçar a decisão

O sistema só avalia uma sessão com **pelo menos 5 eventos até o primeiro `cart`** (inclusive) e
**pelo menos 1 evento depois dele, em até 120 s**.

1. Abra `POST /event` e clique em **Try it out**. Apague o conteúdo do campo e cole:

   ```json
   {
     "event_time": "2019-11-01T10:00:00",
     "event_type": "view",
     "product_id": 4804056,
     "category_id": "2053013554658804075",
     "category_code": "electronics.audio.headphone",
     "brand": "apple",
     "price": 160.55,
     "user_id": 513903572,
     "user_session": "minha-sessao-1"
   }
   ```

2. Clique em **Execute** seis vezes. Antes de cada envio, altere só o `event_time` e o `event_type`:

   | Envio | `event_time` | `event_type` |
   |---|---|---|
   | 1 | `2019-11-01T10:00:00` | `view` |
   | 2 | `2019-11-01T10:00:10` | `view` |
   | 3 | `2019-11-01T10:00:20` | `view` |
   | 4 | `2019-11-01T10:00:30` | `view` |
   | 5 | `2019-11-01T10:00:40` | `cart` |
   | 6 | `2019-11-01T10:01:00` | `view` |

   Cada envio responde `null`, porque a sessão ainda não foi avaliada.

3. Abra `POST /flush/{session_id}`, clique em **Try it out**, preencha `session_id` com
   `minha-sessao-1` e clique em **Execute**. A resposta é a decisão, sem esperar os 120 s.
4. Em `GET /session/{session_id}`, consulte `minha-sessao-1`. A decisão é a mesma do passo 3.

Cada sessão recebe uma única decisão: depois de avaliada, eventos novos com o mesmo `user_session`
não a reabrem. Para repetir o fluxo, troque o `user_session` (por exemplo, `minha-sessao-2`). O
relógio da API avança com o horário dos eventos recebidos, como num *replay*. Por isso, envie os
seis eventos em sequência, sem usar a demonstração no meio.

### Outras rotas

- `GET /metrics`: contagem das sessões processadas desde que a API subiu.
- `GET /demo/scenarios`: os cenários usados pelo `demo.html`.

### Checagem automática (macOS ou Linux)

Com a API no ar, `bash demo/check_demo.sh` testa os quatro cenários. Resultado esperado:
`Pronto para apresentar.` O `bash demo/incremental.sh` envia uma sessão evento a evento.

---

## 5. Treino e avaliação (opcional, requer os dados)

Baixe `2019-Oct.csv` e `2019-Nov.csv` em
<https://www.kaggle.com/datasets/mkechinov/ecommerce-behavior-data-from-multi-category-store> e
coloque-os em `dataset/`.

```bash
python -m src.train                 # treina os modelos (outubro)
python -m src.evaluate_segmented    # validação cruzada em outubro
python -m src.evaluate_november     # avaliação em novembro
python -m src.replay_november       # replay de novembro em streaming
```

Scripts de análise, em `src/analysis/`: `m2_significance`, `m2_aplicabilidade`, `explain_shap`,
`benchmark_latency`, `trigger_sweep_low_t`, `tune_m3` e `pipeline_demo`. Cada um roda com
`python -m src.analysis.<nome>`. O `trigger_sweep_low_t` recebe o valor de T em segundos (por
exemplo, `python -m src.analysis.trigger_sweep_low_t 120`), e o `explain_shap` aceita `oct` ou
`nov`.

---

## 6. Estrutura

```
src/            pipeline (M1 a M4), simulador de streaming e API
src/analysis/   scripts de análise
tests/          testes automatizados (pytest)
dataset/        modelos treinados e resultados
demo/           demonstração (demo.html) e scripts de apoio
requirements.txt  dependências, com as versões usadas
setup.py        dependências, para instalar o projeto como pacote
```

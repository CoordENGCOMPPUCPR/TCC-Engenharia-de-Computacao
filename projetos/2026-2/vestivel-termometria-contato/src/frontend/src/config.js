// Configurações do painel. Valores que podem mudar ficam aqui, não espalhados pelo código.

// URL da API. Pode ser trocada com VITE_API_BASE_URL (no .env ou no painel da hospedagem).
export const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL || 'https://tcc-mastite-backend.onrender.com'
).replace(/\/+$/, '');

// Sensores que sempre aparecem na tabela, mesmo sem leitura (com "—"). Outros que
// vierem da API também aparecem. Com [], mostra só os que estão nos dados.
export const QUARTOS_ESPERADOS = [1, 2, 3, 4, 5];

// Na tabela, leituras com o mesmo pacote_id ficam na mesma linha. Leituras antigas
// (sem pacote_id) são agrupadas quando estão a no máximo esta distância (s) umas das
// outras. Precisa ficar bem abaixo do intervalo entre pacotes (~5 s), senão um sensor
// que faltou numa rodada aparece com o valor da rodada anterior.
export const JANELA_AGRUPAMENTO_S = 2;

// Obs.: não há limiar de alerta no front. Estado, alertas e os λ dos gráficos vêm da API.

// Máximo de leituras e de ciclos buscados para o período. Se a resposta vier
// com esse tamanho, a tela avisa que pode faltar dado. (O /deteccao aceita até 10000.)
export const LIMITE_LEITURAS_PERIODO = 50_000;
export const LIMITE_CICLOS_PERIODO = 10_000;

// O gráfico de temperatura usa a mediana de cada sensor por janela de tempo, calculada
// no backend (um dia a cada 5 s seriam ~86 mil leituras). No máximo
// PONTOS_GRAFICO_MAX pontos por sensor.
export const PONTOS_GRAFICO_MAX = 1500;
export const LIMITE_LEITURAS_GRAFICO = 30_000;

// Período padrão dos gráficos e da tabela.
export const PERIODO_PADRAO = '24h';

// Leituras e ciclos são recarregados com menos frequência que o estado,
// principalmente em períodos longos, para não baixar megabytes a cada 30 s.
export const INTERVALO_SERIES_CURTAS_MS = 60_000;   // períodos de até 24 h
export const INTERVALO_SERIES_LONGAS_MS = 600_000;  // períodos maiores

// Linhas mostradas na tabela de histórico (o CSV leva todas).
export const LINHAS_TABELA_MAX = 500;

// Nos gráficos, um intervalo sem leitura maior que este (min) interrompe a linha.
export const INTERVALO_QUEBRA_MIN = 10;

// Intervalo de atualização automática (ms).
export const INTERVALO_ATUALIZACAO_MS = 30_000;

// Tempo máximo de espera por uma resposta. É alto porque o plano gratuito do
// Render pode levar de 30 a 60 s para acordar.
export const TIMEOUT_REQUISICAO_MS = 75_000;

// Depois de quanto tempo de espera aparece o aviso de "servidor acordando".
export const AVISO_COLD_START_MS = 5_000;

// Depois de um erro, a espera até a próxima tentativa dobra a cada falha, entre estes limites.
export const RETRY_INICIAL_MS = 5_000;
export const RETRY_MAX_MS = 60_000;

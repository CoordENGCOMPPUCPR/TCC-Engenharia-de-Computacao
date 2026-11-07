import { API_BASE_URL, TIMEOUT_REQUISICAO_MS } from './config.js';
import { normalizarEstado, normalizarAlertas, mensagemHttp, FormatoInesperado } from './estado.js';
import { normalizarCiclos } from './series.js';
import { cortarPagina } from './dados.js';

export class ApiError extends Error {}

async function getJson(path, params = {}) {
  const url = new URL(API_BASE_URL + path, window.location.href);
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== null && v !== '') url.searchParams.set(k, v);
  }

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), TIMEOUT_REQUISICAO_MS);
  let resp;
  try {
    resp = await fetch(url, { signal: controller.signal, headers: { Accept: 'application/json' } });
  } catch (err) {
    if (err.name === 'AbortError') {
      throw new ApiError('A API demorou demais para responder.');
    }
    // fetch só falha assim por erro de rede ou bloqueio de CORS (o navegador não diferencia os dois).
    throw new ApiError('Não foi possível conectar à API.');
  } finally {
    clearTimeout(timer);
  }

  let corpo = null;
  try {
    corpo = await resp.json();
  } catch {
    if (resp.ok) throw new ApiError('A API retornou uma resposta em formato inesperado.');
  }
  if (!resp.ok) throw new ApiError(mensagemHttp(resp.status, corpo));
  return corpo;
}

// Converte erro de formato da resposta em ApiError, com a mesma mensagem.
function semFormato(fn) {
  return (json) => {
    try {
      return fn(json);
    } catch (err) {
      if (err instanceof FormatoInesperado || err instanceof Error) throw new ApiError(err.message);
      throw err;
    }
  };
}

export async function buscarEstado() {
  return semFormato(normalizarEstado)(await getJson('/estado'));
}

export async function buscarAlertas(vacaId) {
  return semFormato(normalizarAlertas)(await getJson('/alertas', { vaca_id: vacaId, limite: 1000 }));
}

export async function buscarDeteccao({ vacaId, de, ate, limite }) {
  return semFormato(normalizarCiclos)(await getJson('/deteccao', {
    vaca_id: vacaId, de: new Date(de).toISOString(), ate: new Date(ate).toISOString(), limite,
  }));
}

// Leituras de um período. Com agregarS, a API devolve a mediana de cada sensor por
// janela de agregarS segundos (n = leituras na janela). Se o backend não suportar
// agregar_s, ele ignora o parâmetro e devolve as leituras normais (sem n).
export async function buscarLeituras({ limite, vacaId, de, ate, agregarS } = {}) {
  const dados = await getJson('/leituras', {
    limite, vaca_id: vacaId, extra: 1, agregar_s: agregarS,
    de: de === undefined ? undefined : new Date(de).toISOString(),
    // se vier como string, é um instante com µs (paginação do CSV) e vai sem conversão
    ate: ate === undefined || typeof ate === 'string' ? ate : new Date(ate).toISOString(),
  });
  if (!Array.isArray(dados)) {
    throw new ApiError('A API retornou uma resposta em formato inesperado.');
  }
  return dados.map(normalizar).filter((l) => !Number.isNaN(l.ts));
}

// Todas as leituras do período, em páginas de `porPagina` (usado no CSV).
// aoProgredir(total) é chamado a cada página; maxPaginas evita laço infinito.
export async function buscarTodasLeituras({ vacaId, de, ate, porPagina, maxPaginas = 200, aoProgredir }) {
  const todas = [];
  let cursor = ate;
  for (let i = 0; i < maxPaginas; i++) {
    const pagina = await buscarLeituras({ vacaId, de, ate: cursor, limite: porPagina });
    const { manter, ate: proximo } = cortarPagina(pagina, porPagina);
    todas.push(...manter);
    aoProgredir?.(todas.length);
    if (proximo === null) return todas;
    cursor = proximo;
  }
  throw new ApiError(`Período grande demais para exportar (mais de ${maxPaginas} páginas).`);
}

// Timestamp ISO -> ms. Corta as frações em 3 dígitos, porque alguns navegadores
// não aceitam os microssegundos que a API manda.
function parseTimestamp(s) {
  if (typeof s !== 'string') return NaN;
  return Date.parse(s.replace(/(\.\d{3})\d+/, '$1'));
}

function num(v) {
  return v === null || v === undefined || v === '' ? null : Number(v);
}

function normalizar(l) {
  return {
    id: l.id,
    vaca_id: String(l.vaca_id ?? ''),
    quarto: num(l.quarto),
    temp_raw: num(l.temp_raw),
    temp_ambiente: num(l.temp_ambiente),
    delta_t: num(l.delta_t),
    rssi: num(l.rssi),
    snr: num(l.snr),
    membro: l.membro ?? null,
    pacote_id: l.pacote_id ?? null,
    n: num(l.n), // só nas linhas agregadas: quantas leituras havia na janela
    timestamp: l.timestamp,
    ts: parseTimestamp(l.timestamp),
  };
}

// Organiza as leituras do GET /leituras para a tabela, o período e a exportação.

// Sensores presentes nos dados, em ordem crescente.
export function listarQuartos(leituras) {
  const set = new Set();
  for (const l of leituras) if (Number.isFinite(l.quarto)) set.add(l.quarto);
  return [...set].sort((a, b) => a - b);
}

// Agrupa as leituras de uma vaca em linhas da tabela, uma por pacote LoRa (no máximo
// uma leitura por sensor). Usa o pacote_id quando existe. Nas leituras antigas, sem
// pacote_id, vai da mais recente para a mais antiga e abre uma linha nova quando muda
// o membro, quando o sensor já está na linha ou quando passa de `janelaMs`.
export function agruparEmLinhas(leituras, janelaMs) {
  const ordenadas = [...leituras].sort((a, b) => b.ts - a.ts);
  const linhas = [];
  const porPacote = new Map();
  let atual = null;
  for (const l of ordenadas) {
    const membro = l.membro ?? null;
    if (l.pacote_id !== null && l.pacote_id !== undefined) {
      let linha = porPacote.get(l.pacote_id);
      if (!linha) {
        linha = { ts: l.ts, membro, pacoteId: l.pacote_id, porQuarto: new Map() };
        porPacote.set(l.pacote_id, linha);
        linhas.push(linha);
      }
      if (!linha.porQuarto.has(l.quarto)) linha.porQuarto.set(l.quarto, l);
      continue;
    }
    if (!atual || atual.pacoteId !== null || atual.membro !== membro || atual.porQuarto.has(l.quarto) ||
        atual.ts - l.ts > janelaMs) {
      atual = { ts: l.ts, membro, pacoteId: null, porQuarto: new Map() };
      linhas.push(atual);
    }
    atual.porQuarto.set(l.quarto, l);
  }
  return linhas.sort((a, b) => b.ts - a.ts);
}

// Períodos prontos, em horas. 'personalizado' usa filtro.de e filtro.ate.
export const PERIODOS = { '6h': 6, '24h': 24, '3d': 72, '7d': 168 };

// Janela (s) da mediana do gráfico de temperatura: a menor da lista que deixa o
// período com até `pontosMax` pontos por sensor. Ex.: 1 h → 5 s, 24 h → 60 s, 7 dias → 600 s.
const JANELAS_S = [5, 10, 15, 30, 60, 120, 300, 600, 900, 1800, 3600];

export function janelaAgregacao(de, ate, pontosMax) {
  const s = (ate - de) / 1000 / pontosMax;
  return JANELAS_S.find((j) => j >= s) ?? JANELAS_S.at(-1);
}

// Intervalo { de, ate } em ms. Os atalhos contam a partir de agora.
export function intervaloDoFiltro(filtro, agora = Date.now()) {
  const horas = PERIODOS[filtro.tipo];
  if (horas) return { de: agora - horas * 3600_000, ate: agora };
  if (Number.isFinite(filtro.de) && Number.isFinite(filtro.ate)) return { de: filtro.de, ate: filtro.ate };
  return null;
}

// Paginação do GET /leituras para o CSV. A API ordena da mais recente para a mais
// antiga e `ate` é exclusivo. Como as leituras de um pacote têm o mesmo timestamp,
// uma página cheia pode cortar o último pacote ao meio. Por isso as leituras do
// timestamp mais antigo ficam para a próxima página, que começa em (esse instante + 1 µs).
// Retorna { manter, ate }; ate = null quando era a última página.
export function cortarPagina(pagina, porPagina) {
  if (pagina.length < porPagina) return { manter: pagina, ate: null };
  const maisAntigo = microssegundos(pagina.at(-1).timestamp);
  const manter = pagina.filter((l) => microssegundos(l.timestamp) > maisAntigo);
  if (!manter.length) throw new Error('Página inteira com o mesmo instante: aumente o tamanho da página.');
  return { manter, ate: isoDeMicrossegundos(maisAntigo + 1) };
}

// Timestamp ISO da API (até 6 casas nas frações, com fuso) -> µs desde a época.
export function microssegundos(iso) {
  const m = /^(.*T\d\d:\d\d:\d\d)(?:\.(\d+))?(.*)$/.exec(iso);
  if (!m) return NaN;
  return Date.parse(m[1] + (m[3] || 'Z')) * 1000 + Number((m[2] ?? '').padEnd(6, '0').slice(0, 6));
}

export function isoDeMicrossegundos(us) {
  const ms = Math.floor(us / 1000);
  return new Date(ms).toISOString().replace('Z', `${String(us - ms * 1000).padStart(3, '0')}Z`);
}

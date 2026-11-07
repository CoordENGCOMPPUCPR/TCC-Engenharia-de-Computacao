// Monta as séries dos gráficos a partir do /deteccao, /leituras e /alertas.
// Não calcula ΔT nem alerta, só reorganiza o que a API mandou.

// Ordena os pontos e, onde a distância entre dois passa de `quebraMs`, insere um
// ponto nulo para a linha não ligar trechos sem medição.
export function comQuebras(pontos, quebraMs) {
  const ordenados = pontos.filter((p) => p.y !== null && p.y !== undefined && Number.isFinite(p.x))
    .sort((a, b) => a.x - b.x);
  const saida = [];
  for (const p of ordenados) {
    const ant = saida[saida.length - 1];
    if (ant && p.x - ant.x > quebraMs) saida.push({ x: (ant.x + p.x) / 2, y: null });
    saida.push(p);
  }
  return saida;
}

function ms(v) {
  if (typeof v !== 'string') return NaN;
  return Date.parse(v.replace(/(\.\d{3})\d+/, '$1'));
}

const num = (v) => (typeof v === 'number' && Number.isFinite(v) ? v : null);

// Linhas do /deteccao -> ciclos, em ordem de tempo.
export function normalizarCiclos(json) {
  if (!Array.isArray(json)) throw new Error('A API retornou os ciclos em formato inesperado.');
  return json
    .map((c) => ({
      membro: String(c.membro ?? 'U'),
      ts: ms(c.ciclo_ts),
      estado: c.estado ?? null,
      tMedia: num(c.t_media),
      dtB: num(c.dt_b),
      dtC: num(c.dt_c),
      dtIMax: num(c.dt_i_max),
      dtI: Array.isArray(c.dt_i) ? c.dt_i.map(num) : [],
      nValidos: num(c.n_validos),
      congelado: c.congelado === true,
    }))
    .filter((c) => Number.isFinite(c.ts))
    .sort((a, b) => a.ts - b.ts);
}

export function membrosPresentes(ciclos, leituras = []) {
  const s = new Set([...ciclos.map((c) => c.membro), ...leituras.map((l) => l.membro ?? 'U')]);
  return ['E', 'D', 'U'].filter((m) => s.has(m)).concat([...s].filter((m) => !['E', 'D', 'U'].includes(m)).sort());
}

// ΔT_i de um membro: uma série por sensor.
export function seriesDtI(ciclos, membro, quebraMs) {
  const doMembro = ciclos.filter((c) => c.membro === membro);
  const nSens = Math.max(0, ...doMembro.map((c) => c.dtI.length));
  return Array.from({ length: nSens }, (_, i) => ({
    sensor: i + 1,
    pontos: comQuebras(doMembro.map((c) => ({ x: c.ts, y: c.dtI[i] ?? null })), quebraMs),
  }));
}

export function serieCampo(ciclos, membro, campo, quebraMs) {
  return comQuebras(ciclos.filter((c) => c.membro === membro).map((c) => ({ x: c.ts, y: c[campo] })), quebraMs);
}

// ΔT_c vem repetido nos ciclos de E e de D (sempre E − D); usa um por instante.
export function serieDtC(ciclos, quebraMs) {
  const porTs = new Map();
  for (const c of ciclos) if (c.dtC !== null && !porTs.has(c.ts)) porTs.set(c.ts, c.dtC);
  return comQuebras([...porTs].map(([x, y]) => ({ x, y })), quebraMs);
}

// Temperatura de um membro: uma série por sensor.
export function seriesTemperatura(leituras, membro, quebraMs) {
  const doMembro = leituras.filter((l) => (l.membro ?? 'U') === membro && Number.isFinite(l.quarto));
  const quartos = [...new Set(doMembro.map((l) => l.quarto))].sort((a, b) => a - b);
  return quartos.map((q) => ({
    sensor: q,
    pontos: comQuebras(doMembro.filter((l) => l.quarto === q).map((l) => ({ x: l.ts, y: l.temp_raw })), quebraMs),
  }));
}

// Faixas de alerta para marcar no gráfico: do início da elevação até o fim (ou até
// `agora`, se ainda aberto). Com `componente`, só os alertas que têm esse componente.
export function intervalosAlerta(alertas, membro, agora, componente = null) {
  return alertas
    .filter((a) => (membro === null || a.membro === membro) && (!componente || a.componentes.includes(componente)))
    .map((a) => ({ de: a.inicioElevacao ?? a.inicio, ate: a.fim ?? agora, aberto: a.aberto }))
    .filter((i) => Number.isFinite(i.de) && Number.isFinite(i.ate) && i.ate > i.de)
    .sort((x, y) => x.de - y.de);
}

// Ciclos congelados (fora da linha de base) de um membro, juntos em intervalos.
export function intervalosCongelados(ciclos, membro, cicloMs) {
  const saida = [];
  for (const c of ciclos) {
    if (c.membro !== membro || !c.congelado) continue;
    const ult = saida[saida.length - 1];
    if (ult && c.ts <= ult.ate) ult.ate = c.ts + cicloMs;
    else saida.push({ de: c.ts, ate: c.ts + cicloMs });
  }
  return saida;
}

// Função que devolve o estado do ciclo (bin) de uma leitura, para a tabela e o CSV.
export function indiceEstadoCiclo(ciclos, cicloMs) {
  const idx = new Map();
  for (const c of ciclos) idx.set(`${c.membro}|${c.ts}`, c.estado);
  return (membro, ts) => {
    if (!cicloMs) return null;
    const bin = Math.floor(ts / cicloMs) * cicloMs;
    return idx.get(`${membro ?? 'U'}|${bin}`) ?? null;
  };
}

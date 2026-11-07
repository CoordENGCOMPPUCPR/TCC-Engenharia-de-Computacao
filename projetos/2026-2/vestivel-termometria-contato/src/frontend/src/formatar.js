const fmtDataHora = new Intl.DateTimeFormat('pt-BR', { dateStyle: 'short', timeStyle: 'medium' });
const fmtHora = new Intl.DateTimeFormat('pt-BR', { hour: '2-digit', minute: '2-digit' });
const fmtDiaHora = new Intl.DateTimeFormat('pt-BR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' });

export function dataHora(ts) {
  return fmtDataHora.format(ts);
}

// Sem o ano, para caber melhor na tabela: "29/09 20:06:46".
const fmtCurta = new Intl.DateTimeFormat('pt-BR', {
  day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit',
});
export function dataHoraCurta(ts) {
  return fmtCurta.format(ts).replace(',', '');
}

const fmtHoraSeg = new Intl.DateTimeFormat('pt-BR', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
const fmtDia = new Intl.DateTimeFormat('pt-BR', { day: '2-digit', month: '2-digit' });

export function dia(ts) {
  return fmtDia.format(ts);
}

const p2 = (n) => String(n).padStart(2, '0');

// Valor para <input type="datetime-local"> no fuso local: "2026-10-03T14:05".
export function paraInputDataHora(ts) {
  const d = new Date(ts);
  return `${d.getFullYear()}-${p2(d.getMonth() + 1)}-${p2(d.getDate())}T${p2(d.getHours())}:${p2(d.getMinutes())}`;
}

// Para nomes de arquivo: "2026-10-03_1405".
export function paraArquivo(ts) {
  return paraInputDataHora(ts).replace('T', '_').replace(':', '');
}

export function eixoTempo(ts, spanMs) {
  if (spanMs > 20 * 3600_000) return fmtDiaHora.format(ts);
  if (spanMs < 15 * 60_000) return fmtHoraSeg.format(ts);
  return fmtHora.format(ts);
}

export function relativo(ts, agora = Date.now()) {
  const s = Math.round((agora - ts) / 1000);
  if (s < 0) return 'agora'; // relógio do cliente atrasado
  if (s < 60) return 'há poucos segundos';
  const m = Math.floor(s / 60);
  if (m < 60) return m === 1 ? 'há 1 minuto' : `há ${m} minutos`;
  const h = Math.floor(m / 60);
  if (h < 24) return h === 1 ? 'há 1 hora' : `há ${h} horas`;
  const d = Math.floor(h / 24);
  return d === 1 ? 'há 1 dia' : `há ${d} dias`;
}

// Vírgula decimal, como no resto do painel ("1,5 °C").
const decimal = (v, casas) => v.toFixed(casas).replace('.', ',');

export function temp(v, casas = 1) {
  return v === null || v === undefined ? '—' : `${decimal(v, casas)} °C`;
}

export function delta(v) {
  if (v === null || v === undefined) return '—';
  return `${v > 0 ? '+' : ''}${decimal(v, 2)} °C`;
}

export function numero(v, sufixo = '') {
  return v === null || v === undefined ? '—' : `${v}${sufixo}`;
}

export function esc(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
}

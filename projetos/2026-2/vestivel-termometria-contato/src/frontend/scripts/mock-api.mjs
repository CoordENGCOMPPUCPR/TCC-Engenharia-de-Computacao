// API falsa para testar o front localmente, no mesmo formato da API real.
// Os dados são inventados e servem só para ver a tela em cada estado.
//
//   npm run mock-api                       # http://localhost:5050, um animal em cada estado
//   MOCK_DELAY_MS=20000 npm run mock-api   # simula cold start na 1ª requisição
//   MOCK_FALHA=1 npm run mock-api          # responde sempre HTTP 503
//   MOCK_VAZIO=1 npm run mock-api          # nenhum animal
//   MOCK_SEM_DETECTOR=1 npm run mock-api   # backend antigo: /estado inexistente (404)
//   MOCK_FALHA_APOS=2 npm run mock-api     # responde 2 vezes e depois passa a falhar
//
// Depois rode o front apontando para ela:
//   VITE_API_BASE_URL=http://localhost:5050 npm run dev
//
// Cenários (vaca_id):
//   vaca-alerta    E em ALERTA (espacial, sensor 3), D OK; um alerta aberto e um encerrado
//   vaca-ok        E e D OK
//   vaca-armando   E e D aprendendo a linha de base (dois dias de dados)
//   vaca-falha     E em FALHA_SENSOR (2 sensores válidos), D OK
//   vaca-sem-dados último pacote há 3 h, com alerta aberto em D
//   vaca-antiga    só leituras antigas, sem estado do detector
//   vaca-unica     membro nulo nas leituras (U, membro único, sem contralateral): o formato
//                  real dos dados até o firmware novo, que identifica E/D
import http from 'node:http';

const PORTA = Number(process.env.PORT || 5050);
const ATRASO_INICIAL = Number(process.env.MOCK_DELAY_MS || 0);
const FALHA = process.env.MOCK_FALHA === '1';
const VAZIO = process.env.MOCK_VAZIO === '1';
const SEM_DETECTOR = process.env.MOCK_SEM_DETECTOR === '1';
const FALHA_APOS = Number(process.env.MOCK_FALHA_APOS || 0);

const CICLO_MS = 300_000;
const AGORA = Math.floor(Date.now() / CICLO_MS) * CICLO_MS;
const PARAMETROS = {
  lambda_s: 1.5, lambda_b: 2.0, lambda_c: 2.0, n_persist: 24, ciclo_s: 300, histerese: 0.7,
  sem_dados_min: 30.0, congela_max_h: 168.0,
};
const CONFIG_COMPLETA = { ...PARAMETROS, arm_dias: 3, arm_min_amostras: 10, baseline_dias: 14, g_ausentes: 3 };

const iso = (ms) => new Date(ms).toISOString().replace('Z', '+00:00');
const r = (v, c = 3) => (v === null ? null : +v.toFixed(c));
// pseudoaleatório determinístico (as capturas não mudam entre execuções)
let semente = 42;
const rnd = () => ((semente = (semente * 1103515245 + 12345) % 2 ** 31) / 2 ** 31);
const ruido = (a) => (rnd() - 0.5) * 2 * a;

const leituras = [];
const ciclos = [];
const alertas = [];
let idLeitura = 1;
let pacote = 1;

// Gera `horas` de dados de um membro: 1 pacote por minuto (5 leituras) e 1 ciclo por 5 min.
//   perfil(ts) -> { elev: [5 °C], estado, congelado, armando, falha: [sensores inválidos] }
// Membro 'U' (membro único): leituras com membro null e sem seq, como as do firmware atual;
// o detector do backend trata essas leituras como membro "U".
function gerarMembro(vaca, membro, inicio, fim, perfil) {
  const membroLeitura = membro === 'U' ? null : membro;
  const base = [32.1, 32.6, 31.8, 32.9, 32.3].map((b) => b + (membro === 'D' ? 0.2 : 0));
  for (let t0 = inicio; t0 < fim; t0 += CICLO_MS) {
    const p = perfil(t0);
    const temps = [];
    const doBin = [];
    for (let k = 0; k < 5; k++) {
      const ts = t0 + k * 60_000 + 7_000;
      const tsS = base.map((b, i) => {
        if (p.falha?.includes(i + 1)) return i === 0 ? null : 22 + ruido(0.3); // erro ou perda de contato
        return b + 0.4 * Math.sin((ts / 3600_000 / 24) * 2 * Math.PI) + (p.elev?.[i] ?? 0) + ruido(0.05);
      });
      temps.push(tsS);
      const pid = pacote++;
      const rssi = -72 - Math.round(rnd() * 10); // do pacote: igual para os 5 sensores
      const snr = r(8 + rnd() * 2, 1);
      tsS.forEach((t, i) => {
        const l = {
          id: idLeitura++, vaca_id: vaca, quarto: i + 1, temp_raw: t === null ? null : r(t, 2),
          temp_ambiente: null, delta_t: null, rssi, snr,
          timestamp: iso(ts), membro: membroLeitura, pacote_id: pid, seq: membroLeitura ? pid % 256 : null,
        };
        leituras.push(l);
        doBin.push(l);
      });
    }
    if (t0 + CICLO_MS > AGORA) continue; // bin ainda aberto: sem ciclo
    const elev = p.elev ?? [0, 0, 0, 0, 0];
    const validos = 5 - (p.falha?.length ?? 0);
    let dtI = [null, null, null, null, null];
    let dtB = null;
    if (!p.armando && validos >= 3) {
      const res = elev.map((e, i) => (p.falha?.includes(i + 1) ? null : e + ruido(0.08)));
      const v = res.filter((x) => x !== null);
      dtB = v.reduce((a, b) => a + b, 0) / v.length + (p.dtBExtra ?? 0);
      dtI = res.map((x) => (x === null ? null : x - (v.reduce((a, b) => a + b, 0) - x) / (v.length - 1)));
    }
    // como o backend: ao fechar o bin, delta_t de cada leitura = ΔT_i do seu sensor (null se inválido)
    for (const l of doBin) l.delta_t = r(dtI[l.quarto - 1]);
    const tm = temps.flat().filter((x) => x !== null);
    ciclos.push({
      vaca_id: vaca, membro, ciclo_ts: iso(t0), t_media: r(tm.reduce((a, b) => a + b, 0) / tm.length),
      dt_b: r(dtB), dt_c: null, dt_i_max: dtI.some((x) => x !== null) ? r(Math.max(...dtI.filter((x) => x !== null))) : null,
      n_validos: validos, estado: p.estado, congelado: Boolean(p.congelado), dt_i: dtI.map((x) => r(x)),
      // só para o /estado do mock (o backend calcula a partir das leituras do bin)
      _invalidos: (p.falha ?? []).map((s) => ({ sensor: s, motivo: s === 1 ? 'ausente' : 'frio' })),
      _armando: Boolean(p.armando),
    });
  }
}

// ΔT_c = ΔT_b(E) − ΔT_b(D) nos ciclos em que os dois membros têm ΔT_b
function preencherDtC(vaca) {
  const porTs = new Map();
  for (const c of ciclos.filter((x) => x.vaca_id === vaca)) {
    if (!porTs.has(c.ciclo_ts)) porTs.set(c.ciclo_ts, {});
    porTs.get(c.ciclo_ts)[c.membro] = c;
  }
  for (const { E, D } of porTs.values()) {
    if (E && D && E.dt_b !== null && D.dt_b !== null) E.dt_c = D.dt_c = r(E.dt_b - D.dt_b);
  }
}

const H = 3600_000;
if (!VAZIO) {
  // vaca-alerta: elevação de 2,4 °C no sensor 3 do membro E há 5 h; um alerta encerrado há 2 dias
  const ini = AGORA - 3 * 24 * H;
  const elevIni = AGORA - 5 * H;
  const abertura = elevIni + 24 * CICLO_MS;
  const antigoIni = AGORA - 50 * H;
  const antigoFim = antigoIni + 6 * H;
  gerarMembro('vaca-alerta', 'E', ini, AGORA, (t) => {
    if (t >= elevIni) return { elev: [0, 0, 2.4, 0, 0], estado: t >= abertura ? 'ALERTA' : 'OK', congelado: t >= abertura };
    if (t >= antigoIni && t < antigoFim) return { elev: [1.9, 1.9, 1.9, 2.3, 2.1], estado: t >= antigoIni + 2 * H ? 'ALERTA' : 'OK', congelado: true };
    return { estado: 'OK' };
  });
  gerarMembro('vaca-alerta', 'D', ini, AGORA, () => ({ estado: 'OK' }));
  preencherDtC('vaca-alerta');
  alertas.push({
    id: 2, vaca_id: 'vaca-alerta', membro: 'E', componentes: ['S'], primeiro: 'S', inicio: iso(abertura),
    inicio_elevacao: iso(elevIni), fim: null, picos: null, parametros: CONFIG_COMPLETA,
  }, {
    id: 1, vaca_id: 'vaca-alerta', membro: 'E', componentes: ['B', 'C'], primeiro: 'B', inicio: iso(antigoIni + 2 * H),
    inicio_elevacao: iso(antigoIni), fim: iso(antigoFim + 2 * H), picos: { S: null, B: 2.31, C: 2.18 },
    parametros: CONFIG_COMPLETA,
  });

  gerarMembro('vaca-ok', 'E', AGORA - 3 * 24 * H, AGORA, () => ({ estado: 'OK' }));
  gerarMembro('vaca-ok', 'D', AGORA - 3 * 24 * H, AGORA, () => ({ estado: 'OK' }));

  // membro nulo nas leituras (firmware atual): um só membro "U", sem contralateral
  gerarMembro('vaca-unica', 'U', AGORA - 3 * 24 * H, AGORA, () => ({ estado: 'OK' }));
  preencherDtC('vaca-ok');

  gerarMembro('vaca-armando', 'E', AGORA - 2 * 24 * H, AGORA, () => ({ estado: 'ARMANDO', armando: true }));
  gerarMembro('vaca-armando', 'D', AGORA - 2 * 24 * H, AGORA, () => ({ estado: 'ARMANDO', armando: true }));

  const falhaIni = AGORA - 40 * 60_000;
  gerarMembro('vaca-falha', 'E', AGORA - 3 * 24 * H, AGORA, (t) => (t >= falhaIni
    ? { estado: 'FALHA_SENSOR', falha: [1, 2, 4] } : { estado: 'OK' }));
  gerarMembro('vaca-falha', 'D', AGORA - 3 * 24 * H, AGORA, () => ({ estado: 'OK' }));
  preencherDtC('vaca-falha');

  const fimSD = AGORA - 3 * H;
  const elevSD = fimSD - 4 * H;
  gerarMembro('vaca-sem-dados', 'E', AGORA - 3 * 24 * H, fimSD, () => ({ estado: 'OK' }));
  gerarMembro('vaca-sem-dados', 'D', AGORA - 3 * 24 * H, fimSD, (t) => (t >= elevSD
    ? { elev: [2.5, 2.4, 2.6, 2.5, 2.4], estado: t >= elevSD + 2 * H ? 'ALERTA' : 'OK', congelado: true }
    : { estado: 'OK' }));
  preencherDtC('vaca-sem-dados');
  alertas.push({
    id: 3, vaca_id: 'vaca-sem-dados', membro: 'D', componentes: ['B', 'C'], primeiro: 'B', inicio: iso(elevSD + 2 * H),
    inicio_elevacao: iso(elevSD), fim: null, picos: null, parametros: CONFIG_COMPLETA,
  });

  // leituras antigas, sem membro nem pacote_id (anteriores ao detector)
  for (let k = 0; k < 20; k++) {
    for (let q = 1; q <= 5; q++) {
      leituras.push({
        id: idLeitura++, vaca_id: 'vaca-antiga', quarto: q, temp_raw: r(38.5 + ruido(0.2), 2), temp_ambiente: null,
        delta_t: null, rssi: null, snr: null, timestamp: iso(AGORA - 30 * 24 * H + k * 30_000),
        membro: null, pacote_id: null, seq: null,
      });
    }
  }
}

function ultimoCiclo(vaca, membro) {
  const cs = ciclos.filter((c) => c.vaca_id === vaca && c.membro === membro);
  const c = cs[cs.length - 1];
  return c ? { ts: c.ciclo_ts, estado: c.estado, t_media: c.t_media, dt_b: c.dt_b, dt_c: c.dt_c,
    dt_i_max: c.dt_i_max, n_validos: c.n_validos } : null;
}

function ultimaLeitura(vaca, membro) {
  const ls = leituras.filter((l) => l.vaca_id === vaca && (membro === undefined || l.membro === membro));
  return ls.length ? ls.reduce((a, b) => (Date.parse(a.timestamp) > Date.parse(b.timestamp) ? a : b)).timestamp : null;
}

const PRIORIDADE = ['ALERTA', 'FALHA_SENSOR', 'SEM_DADOS', 'ARMANDO', 'OK'];

function estadoGeral() {
  const agoraReal = Date.now();
  const vacas = [...new Set(leituras.map((l) => l.vaca_id))].sort();
  const animais = vacas.map((v) => {
    const membros = v === 'vaca-antiga' ? [] : ['D', 'E', 'U']
      .filter((m) => leituras.some((l) => l.vaca_id === v && (l.membro ?? 'U') === m))
      .map((m) => {
        const uc = ultimoCiclo(v, m);
        const ult = ultimaLeitura(v, m === 'U' ? null : m);
        const cs = ciclos.filter((c) => c.vaca_id === v && c.membro === m);
        const ultimo = cs[cs.length - 1];
        const dias = cs.length ? Math.floor((Date.parse(cs[cs.length - 1].ciclo_ts) - Date.parse(cs[0].ciclo_ts)) / 86400000) + 1 : 0;
        const aberto = alertas.find((a) => a.vaca_id === v && a.membro === m && a.fim === null);
        const semDados = agoraReal - Date.parse(ult) > PARAMETROS.sem_dados_min * 60_000;
        return {
          membro: m, estado: semDados ? 'SEM_DADOS' : (uc?.estado ?? 'ARMANDO'), alerta_aberto: Boolean(aberto),
          componentes: aberto ? aberto.componentes : [], ultima_leitura: ult, ultimo_ciclo: uc,
          sensores_invalidos: ultimo ? ultimo._invalidos : null,
          progresso_armamento: {
            dias: Math.min(dias, 14), dias_necessarios: 3,
            celulas_armadas: ultimo?._armando ? 0 : 24, celulas_total: 24,
          },
        };
      });
    let est = membros.length ? membros.map((m) => m.estado).sort((a, b) => PRIORIDADE.indexOf(a) - PRIORIDADE.indexOf(b))[0] : 'SEM_DADOS';
    if (membros.some((m) => m.alerta_aberto)) est = 'ALERTA';
    return { vaca_id: v, estado: est, ultima_leitura: ultimaLeitura(v), membros };
  });
  return { agora: iso(agoraReal), parametros: PARAMETROS, animais };
}

function entre(lista, campo, de, ate) {
  return lista.filter((x) => (!de || Date.parse(x[campo]) >= Date.parse(de)) && (!ate || Date.parse(x[campo]) < Date.parse(ate)));
}

const CAMPOS_ANTIGOS = ['id', 'vaca_id', 'quarto', 'temp_raw', 'temp_ambiente', 'delta_t', 'rssi', 'snr', 'timestamp'];
let primeira = true;
let respondidas = 0;

http.createServer((req, res) => {
  const url = new URL(req.url, `http://${req.headers.host}`);
  const q = (k) => url.searchParams.get(k);
  const responder = (status, corpo) => {
    res.writeHead(status, { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' });
    res.end(JSON.stringify(corpo));
  };
  const atraso = primeira ? ATRASO_INICIAL : 0;
  primeira = false;
  setTimeout(() => {
    if (FALHA || (FALHA_APOS && respondidas >= FALHA_APOS && url.pathname === '/estado')) {
      return responder(503, { erro: 'indisponível' });
    }
    if (url.pathname === '/estado') respondidas++;
    if (url.pathname === '/health') return responder(200, { status: 'ok' });
    if (SEM_DETECTOR && url.pathname !== '/leituras') return responder(404, { erro: 'não encontrado' });
    if (url.pathname === '/estado') return responder(200, estadoGeral());
    if (url.pathname === '/alertas') {
      let lista = alertas.filter((a) => !q('vaca_id') || a.vaca_id === q('vaca_id'));
      if (q('abertos') === 'true') lista = lista.filter((a) => a.fim === null);
      if (q('abertos') === 'false') lista = lista.filter((a) => a.fim !== null);
      return responder(200, lista.map((a) => ({ ...a, aberto: a.fim === null })));
    }
    if (url.pathname === '/deteccao') {
      if (!q('vaca_id')) return responder(400, { erro: 'vaca_id é obrigatório' });
      const lista = entre(ciclos.filter((c) => c.vaca_id === q('vaca_id') && (!q('membro') || c.membro === q('membro'))),
        'ciclo_ts', q('de'), q('ate'));
      return responder(200, lista.reverse().slice(0, Number(q('limite') || 2000))
        .map(({ _invalidos, _armando, ...c }) => c));
    }
    if (url.pathname === '/leituras') {
      const limite = Number(q('limite') || 50);
      let lista = leituras.filter((l) => !q('vaca_id') || l.vaca_id === q('vaca_id'));
      lista = entre(lista, 'timestamp', q('de'), q('ate'))
        .sort((a, b) => Date.parse(b.timestamp) - Date.parse(a.timestamp)).slice(0, limite);
      const extra = q('extra') === '1';
      const agregarS = Number(q('agregar_s') || 0);
      if (agregarS) {
        // mediana por (vaca, membro, sensor, janela), como o backend
        const grupos = new Map();
        for (const l of entre(leituras.filter((x) => !q('vaca_id') || x.vaca_id === q('vaca_id')), 'timestamp', q('de'), q('ate'))) {
          const t0 = Math.floor(Date.parse(l.timestamp) / 1000 / agregarS) * agregarS * 1000;
          const k = [l.vaca_id, l.membro ?? '', l.quarto, t0].join('|');
          if (!grupos.has(k)) grupos.set(k, { vaca_id: l.vaca_id, membro: l.membro ?? null, quarto: l.quarto, t0, v: [] });
          if (l.temp_raw !== null) grupos.get(k).v.push(l.temp_raw);
        }
        const mediana = (v) => { const o = [...v].sort((x, y) => x - y), m = o.length >> 1; return o.length % 2 ? o[m] : (o[m - 1] + o[m]) / 2; };
        const linhas = [...grupos.values()].sort((x, y) => y.t0 - x.t0).slice(0, limite)
          .map((g) => ({ vaca_id: g.vaca_id, membro: g.membro, quarto: g.quarto, timestamp: new Date(g.t0).toISOString(),
            temp_raw: g.v.length ? mediana(g.v) : null, n: g.v.length }));
        return responder(200, linhas);
      }
      return responder(200, lista.map((l) => Object.fromEntries(Object.entries(l)
        .filter(([k]) => extra || CAMPOS_ANTIGOS.includes(k)))));
    }
    responder(404, { erro: 'não encontrado' });
  }, atraso);
}).listen(PORTA, () => console.log(`API mock em http://localhost:${PORTA}`));

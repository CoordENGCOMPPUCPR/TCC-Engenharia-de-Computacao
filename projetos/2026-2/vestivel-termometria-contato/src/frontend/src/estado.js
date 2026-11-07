// Interpreta o GET /estado e o GET /alertas e monta os textos da tela.
// Nada é calculado aqui: campo que a API não mandou aparece como "indisponível".

import { relativo, dataHora, delta } from './formatar.js';

export const INDISPONIVEL = 'indisponível';

// Texto, ícone e classe CSS de cada estado (ícone e texto para não depender só da cor).
export const ESTADOS = {
  ALERTA: { codigo: 'ALERTA', rotulo: 'Alerta', icone: '⚠', classe: 'est-alerta',
    descricao: 'Elevação de temperatura persistente detectada.' },
  // "Sem alerta" em vez de "Normal": o detector não vê elevações abaixo de λ, então
  // não ter alerta não quer dizer que o animal está saudável.
  OK: { codigo: 'OK', rotulo: 'Sem alerta', icone: '✓', classe: 'est-ok',
    descricao: 'Nenhum alerta ativo.' },
  ARMANDO: { codigo: 'ARMANDO', rotulo: 'Aprendendo a linha de base', icone: '⏳', classe: 'est-armando',
    descricao: 'O sistema ainda está aprendendo a temperatura de referência deste membro. Ainda não avalia alertas.' },
  FALHA_SENSOR: { codigo: 'FALHA_SENSOR', rotulo: 'Falha de sensor', icone: '✖', classe: 'est-falha',
    descricao: 'Sensores válidos insuficientes no último ciclo. Não avalia alertas até voltar.' },
  SEM_DADOS: { codigo: 'SEM_DADOS', rotulo: 'Sem dados', icone: '⊘', classe: 'est-sem-dados',
    descricao: 'Nenhum pacote recente deste membro.' },
};

// Ordem dos animais na tela: os que pedem atenção primeiro.
export const ORDEM_ESTADOS = ['ALERTA', 'FALHA_SENSOR', 'SEM_DADOS', 'ARMANDO', 'OK'];

export function infoEstado(codigo) {
  if (ESTADOS[codigo]) return ESTADOS[codigo];
  return {
    codigo: codigo ?? null, rotulo: codigo ? `Estado desconhecido (${codigo})` : 'Estado indisponível',
    icone: '?', classe: 'est-desconhecido', descricao: 'A API enviou um estado que o painel não conhece.',
  };
}

export const COMPONENTES = {
  S: { nome: 'Espacial', explicacao: 'um sensor mais quente que os outros do mesmo membro' },
  B: { nome: 'Temporal', explicacao: 'o membro todo acima da própria linha de base' },
  C: { nome: 'Contralateral', explicacao: 'um membro mais quente que o outro' },
};

export function rotuloComponente(c) {
  return COMPONENTES[c] ? `${COMPONENTES[c].nome} (${c})` : `Componente ${c}`;
}

export const MEMBROS = {
  E: 'Posterior esquerdo',
  D: 'Posterior direito',
  U: 'Membro único (sem identificação E/D)',
};

export function rotuloMembro(m) {
  return MEMBROS[m] ?? `Membro ${m}`;
}

// Motivos de sensor inválido no último ciclo (campo sensores_invalidos do /estado).
const MOTIVOS = {
  ausente: 'sem leitura no ciclo (erro do sensor ou pacotes incompletos)',
  frio: 'perda de contato (leitura muito abaixo dos outros sensores)',
  perda_contato: 'perda de contato (leitura muito abaixo dos outros sensores)',
  erro: 'erro do sensor (sem leitura)',
  faixa: 'fora da faixa válida',
  fora_da_faixa: 'fora da faixa válida',
};

export function motivoSensor(codigo) {
  return MOTIVOS[codigo] ?? (codigo ? String(codigo) : 'motivo não informado');
}

// ------------------------------------------------------------ normalização

function ms(v) {
  if (typeof v !== 'string' && typeof v !== 'number') return null;
  const t = typeof v === 'number' ? v * 1000 : Date.parse(v.replace(/(\.\d{3})\d+/, '$1'));
  return Number.isFinite(t) ? t : null;
}

function numOuNulo(v) {
  return typeof v === 'number' && Number.isFinite(v) ? v : null;
}

export class FormatoInesperado extends Error {}

function normalizarCiclo(c) {
  if (!c || typeof c !== 'object') return null;
  return {
    ts: ms(c.ts),
    estado: c.estado ?? null,
    tMedia: numOuNulo(c.t_media),
    dtB: numOuNulo(c.dt_b),
    dtC: numOuNulo(c.dt_c),
    dtIMax: numOuNulo(c.dt_i_max),
    nValidos: numOuNulo(c.n_validos),
  };
}

function normalizarMembro(m) {
  return {
    membro: String(m.membro ?? 'U'),
    estado: m.estado ?? null,
    alertaAberto: m.alerta_aberto === true,
    componentes: Array.isArray(m.componentes) ? m.componentes.map(String) : [],
    ultimaLeitura: ms(m.ultima_leitura),
    ultimoCiclo: normalizarCiclo(m.ultimo_ciclo),
    // só existem se a API mandar
    sensoresInvalidos: Array.isArray(m.sensores_invalidos) ? m.sensores_invalidos : null,
    progresso: m.progresso_armamento && typeof m.progresso_armamento === 'object' ? m.progresso_armamento : null,
  };
}

export function normalizarParametros(p) {
  const o = p && typeof p === 'object' ? p : {};
  return {
    lambdaS: numOuNulo(o.lambda_s),
    lambdaB: numOuNulo(o.lambda_b),
    lambdaC: numOuNulo(o.lambda_c),
    nPersist: numOuNulo(o.n_persist),
    cicloS: numOuNulo(o.ciclo_s),
    histerese: numOuNulo(o.histerese),
    semDadosMin: numOuNulo(o.sem_dados_min),
    congelaMaxH: numOuNulo(o.congela_max_h),
  };
}

export function normalizarEstado(json) {
  if (!json || typeof json !== 'object' || !Array.isArray(json.animais)) {
    throw new FormatoInesperado('A API retornou o estado em formato inesperado.');
  }
  const animais = json.animais
    .filter((a) => a && a.vaca_id !== undefined && a.vaca_id !== null)
    .map((a) => {
      const membros = (Array.isArray(a.membros) ? a.membros : []).map(normalizarMembro);
      return {
        vacaId: String(a.vaca_id),
        estado: a.estado ?? null,
        ultimaLeitura: ms(a.ultima_leitura),
        alertaAberto: membros.some((m) => m.alertaAberto),
        membros,
      };
    });
  return { agora: ms(json.agora), parametros: normalizarParametros(json.parametros), animais: ordenarAnimais(animais) };
}

export function ordenarAnimais(animais) {
  const pos = (a) => {
    if (a.alertaAberto) return -1; // alerta aberto sempre primeiro (inclusive em SEM_DADOS)
    const i = ORDEM_ESTADOS.indexOf(a.estado);
    return i < 0 ? ORDEM_ESTADOS.length : i;
  };
  return [...animais].sort((a, b) => pos(a) - pos(b) || a.vacaId.localeCompare(b.vacaId, 'pt-BR', { numeric: true }));
}

export function contarPorEstado(animais) {
  const c = { total: animais.length, alertaAberto: 0 };
  for (const e of ORDEM_ESTADOS) c[e] = 0;
  for (const a of animais) {
    if (a.alertaAberto) c.alertaAberto++;
    if (a.estado in c) c[a.estado]++;
  }
  return c;
}

// ------------------------------------------------------------ textos por membro

// Linhas {rotulo, valor} mostradas embaixo do estado de um membro. O conteúdo
// depende do estado: ARMANDO mostra o progresso (nunca ΔT), FALHA_SENSOR mostra os
// sensores inválidos e SEM_DADOS mostra quando chegou o último pacote.
export function detalhesMembro(m, agora = Date.now()) {
  const linhas = [];
  const ciclo = m.ultimoCiclo;
  const ultimo = () => ({
    rotulo: 'Último pacote',
    valor: m.ultimaLeitura === null ? INDISPONIVEL : relativo(m.ultimaLeitura, agora),
    ts: m.ultimaLeitura,
  });
  const deltas = () => [
    { rotulo: 'ΔT espacial máx. (último ciclo)', valor: ciclo && ciclo.dtIMax !== null ? delta(ciclo.dtIMax) : INDISPONIVEL },
    { rotulo: 'ΔT temporal (último ciclo)', valor: ciclo && ciclo.dtB !== null ? delta(ciclo.dtB) : INDISPONIVEL },
    ...(m.membro === 'U' ? [] : [{
      rotulo: 'ΔT contralateral E − D (último ciclo)',
      valor: ciclo && ciclo.dtC !== null ? delta(ciclo.dtC) : INDISPONIVEL,
    }]),
  ];
  const alerta = () => ({
    rotulo: 'Componentes do alerta',
    valor: m.componentes.length ? m.componentes.map(rotuloComponente).join(', ') : INDISPONIVEL,
    destaque: true,
  });

  switch (m.estado) {
    case 'ALERTA':
      linhas.push(alerta(), ...deltas(), ultimo());
      break;
    case 'OK':
      linhas.push(...deltas(), ultimo());
      break;
    case 'ARMANDO':
      linhas.push({ rotulo: 'Progresso', valor: textoProgresso(m.progresso) }, ultimo());
      break;
    case 'FALHA_SENSOR':
      linhas.push(
        { rotulo: 'Sensores inválidos', valor: textoSensoresInvalidos(m.sensoresInvalidos), destaque: true },
        { rotulo: 'Sensores válidos no último ciclo',
          valor: ciclo && ciclo.nValidos !== null ? String(ciclo.nValidos) : INDISPONIVEL },
        ultimo(),
      );
      break;
    case 'SEM_DADOS':
      linhas.push(ultimo());
      if (m.alertaAberto) linhas.push({ ...alerta(), rotulo: 'Alerta continua aberto' });
      break;
    default:
      linhas.push(ultimo());
  }
  return linhas;
}

export function textoProgresso(p) {
  if (!p) return `${INDISPONIVEL} (a API não informa dias nem células armadas)`;
  const partes = [];
  if (Number.isFinite(p.dias) && Number.isFinite(p.dias_necessarios)) partes.push(`${p.dias} de ${p.dias_necessarios} dias`);
  if (Number.isFinite(p.celulas_armadas) && Number.isFinite(p.celulas_total)) {
    partes.push(`${p.celulas_armadas} de ${p.celulas_total} células armadas`);
  }
  return partes.length ? partes.join(' · ') : INDISPONIVEL;
}

export function textoSensoresInvalidos(lista) {
  if (!lista) return `${INDISPONIVEL} (a API não informa quais sensores nem o motivo)`;
  if (!lista.length) return 'nenhum informado';
  return lista
    .map((s) => (typeof s === 'object' && s !== null
      ? `Sens ${s.sensor ?? '?'}: ${motivoSensor(s.motivo)}`
      : `Sens ${s}`))
    .join('; ');
}

// Texto do selo de estado. Se a última consulta falhou, deixa claro que é o último
// estado conhecido (com o horário), para não parecer que é o estado atual.
export function seloEstado(codigo, { desatualizadoDesde = null } = {}) {
  const info = infoEstado(codigo);
  if (desatualizadoDesde === null) return { ...info, texto: `${info.icone} ${info.rotulo}` };
  const hora = new Date(desatualizadoDesde).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' });
  return {
    ...info, classe: `${info.classe} est-desatualizado`,
    texto: `${info.icone} Último estado conhecido (${hora}): ${info.rotulo}`,
  };
}

// ------------------------------------------------------------ alertas

function normalizarParametrosAlerta(p) {
  if (!p || typeof p !== 'object') return null;
  return {
    nPersist: numOuNulo(p.n_persist),
    cicloS: numOuNulo(p.ciclo_s),
    lambdaS: numOuNulo(p.lambda_s),
    lambdaB: numOuNulo(p.lambda_b),
    lambdaC: numOuNulo(p.lambda_c),
  };
}

export function normalizarAlertas(json) {
  if (!Array.isArray(json)) throw new FormatoInesperado('A API retornou os alertas em formato inesperado.');
  return json.map((a) => ({
    id: a.id ?? null,
    vacaId: String(a.vaca_id ?? ''),
    membro: String(a.membro ?? 'U'),
    componentes: Array.isArray(a.componentes) ? a.componentes.map(String) : [],
    primeiro: a.primeiro ?? null,
    inicio: ms(a.inicio),
    inicioElevacao: ms(a.inicio_elevacao),
    fim: ms(a.fim),
    aberto: a.fim === null || a.fim === undefined,
    picos: a.picos && typeof a.picos === 'object' ? a.picos : null,
    parametros: normalizarParametrosAlerta(a.parametros),
  })).sort((x, y) => (y.aberto - x.aberto) || ((y.inicio ?? 0) - (x.inicio ?? 0)));
}

export function textoDuracaoCiclos(n, cicloS) {
  if (n === null) return INDISPONIVEL;
  if (cicloS === null) return `${n} ciclos`;
  const min = (n * cicloS) / 60;
  const dur = min >= 60 && min % 60 === 0 ? `${min / 60} h` : `${min} min`;
  return `${n} ciclos (${dur})`;
}

const lambdaTxt = (v) => (v === null ? INDISPONIVEL : `${v.toLocaleString('pt-BR')} °C`);

export function textoParametros(p) {
  if (!p) return INDISPONIVEL;
  return `N = ${textoDuracaoCiclos(p.nPersist, p.cicloS)} · λ_s = ${lambdaTxt(p.lambdaS)} · ` +
    `λ_b = ${lambdaTxt(p.lambdaB)} · λ_c = ${lambdaTxt(p.lambdaC)}`;
}

// Textos de um alerta. Os picos só são gravados quando o alerta fecha, então
// num alerta aberto aparecem como "indisponível".
export function descreverAlerta(a) {
  return {
    titulo: a.aberto ? 'Alerta aberto' : 'Alerta encerrado',
    membro: rotuloMembro(a.membro),
    disparo: a.primeiro ? `Disparou por: ${rotuloComponente(a.primeiro)}` : `Disparou por: ${INDISPONIVEL}`,
    componentes: a.componentes.length ? a.componentes.map(rotuloComponente) : [INDISPONIVEL],
    inicio: a.inicio === null ? INDISPONIVEL : dataHora(a.inicio),
    inicioElevacao: a.inicioElevacao === null ? INDISPONIVEL : dataHora(a.inicioElevacao),
    fim: a.aberto ? 'em aberto' : a.fim === null ? INDISPONIVEL : dataHora(a.fim),
    picos: ['S', 'B', 'C']
      .filter((c) => a.componentes.includes(c))
      .map((c) => ({
        componente: rotuloComponente(c),
        valor: a.picos && typeof a.picos[c] === 'number' ? delta(a.picos[c]) : INDISPONIVEL,
      })),
    parametros: textoParametros(a.parametros),
  };
}

// ------------------------------------------------------------ carregamento

// Espera até a próxima tentativa depois de uma falha: dobra a cada vez, até o máximo.
export function atrasoRetry(tentativa, inicialMs = 5_000, maxMs = 60_000) {
  const n = Math.max(1, tentativa);
  return Math.min(inicialMs * 2 ** (n - 1), maxMs);
}

// Decide o que mostrar conforme o carregamento: 'dados', 'carregando', 'acordando' ou 'erro'.
// Só devolve 'dados' se já houve uma resposta válida da API.
//   demorando: espera longa (provavelmente o servidor acordando)
export function telaDeCarga({ temDados, carregando, demorando, erro, tentativa = 0, proximaEmMs = null }) {
  if (temDados) {
    return { tipo: 'dados', desatualizado: Boolean(erro), aviso: erro
      ? `Sem resposta da API na última atualização: ${String(erro).replace(/\.$/, '')}. O que está na tela pode estar desatualizado.`
      : null };
  }
  if (carregando && demorando) {
    return { tipo: 'acordando', mensagem: 'O servidor estava em repouso e está acordando. Isso pode levar até cerca de 1 minuto.' };
  }
  if (carregando || (!erro && !temDados)) return { tipo: 'carregando', mensagem: 'Carregando dados do detector…' };
  return {
    tipo: 'erro',
    mensagem: erro,
    tentativa,
    proxima: proximaEmMs === null ? null : `Nova tentativa automática em ${Math.ceil(proximaEmMs / 1000)} s` +
      (tentativa > 1 ? ` (tentativa ${tentativa})` : ''),
  };
}

// Mensagem de erro para mostrar ao usuário, a partir da resposta HTTP.
export function mensagemHttp(status, corpo) {
  const msg = corpo && typeof corpo === 'object' && typeof corpo.erro === 'string' ? corpo.erro : null;
  if (status === 404) return 'A API não tem as rotas do detector (o backend da Fase 2 ainda não foi publicado?).';
  if (status === 503 && msg && /migra/i.test(msg)) return `A API está sem o detector: ${msg}.`;
  if (status === 503) return `A API está temporariamente indisponível (HTTP 503${msg ? `: ${msg}` : ''}).`;
  if (status >= 500) return `A API respondeu com erro interno (HTTP ${status}).`;
  return `A API respondeu com erro (HTTP ${status})${msg ? `: ${msg}` : ''}.`;
}

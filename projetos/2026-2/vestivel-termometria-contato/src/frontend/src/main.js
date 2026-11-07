import './style.css';
import { buscarEstado, buscarAlertas, buscarDeteccao, buscarLeituras, buscarTodasLeituras } from './api.js';
import {
  INTERVALO_ATUALIZACAO_MS,
  AVISO_COLD_START_MS,
  RETRY_INICIAL_MS,
  RETRY_MAX_MS,
  QUARTOS_ESPERADOS,
  JANELA_AGRUPAMENTO_S,
  INTERVALO_QUEBRA_MIN,
  LIMITE_LEITURAS_PERIODO,
  LIMITE_CICLOS_PERIODO,
  PONTOS_GRAFICO_MAX,
  LIMITE_LEITURAS_GRAFICO,
  LINHAS_TABELA_MAX,
  PERIODO_PADRAO,
  INTERVALO_SERIES_CURTAS_MS,
  INTERVALO_SERIES_LONGAS_MS,
} from './config.js';
import { rotuloMembro, textoParametros, telaDeCarga, atrasoRetry } from './estado.js';
import {
  seriesDtI, serieCampo, serieDtC, seriesTemperatura, intervalosAlerta, intervalosCongelados,
  membrosPresentes, indiceEstadoCiclo,
} from './series.js';
import { listarQuartos, agruparEmLinhas, intervaloDoFiltro, janelaAgregacao, PERIODOS } from './dados.js';
import { gerarCsv, nomeArquivo, baixar } from './exportar.js';
import * as fmt from './formatar.js';
import { criarGrafico, atualizarGrafico, corSerie, COR_MEMBRO, COR_LIMIAR, COR_ALERTA, COR_CONGELADO } from './graficos.js';
import { AVISO_FIXO, htmlAvisoDesatualizado, htmlCarga, htmlSelo } from './telas/comum.js';
import { htmlGeral } from './telas/geral.js';
import { htmlSobre } from './telas/sobre.js';
import {
  htmlEstruturaAnimal, htmlMembros, htmlAlertas, htmlSeletorMembro, htmlTabela, textoJanela, fmtLambda,
} from './telas/animal.js';

const $conteudo = document.getElementById('conteudo');
const $status = document.getElementById('status');
const $btnAtualizar = document.getElementById('btn-atualizar');
const $rodape = document.getElementById('rodape');

const QUEBRA_MS = INTERVALO_QUEBRA_MIN * 60_000;
const ID_GRAFICOS = ['g-temp', 'g-dti', 'g-dtb', 'g-dtc'];

const estado = {
  rota: lerRota(),

  // GET /estado
  painel: null,
  painelEm: null,
  carregando: false,
  demorando: false,   // espera longa: provavelmente o Render acordando
  erro: null,
  tentativa: 0,
  proximaEm: null,
  requisicao: 0,
  timerProxima: null,
  timerAviso: null,

  // tela de um animal
  alertas: null,
  erroAlertas: null,
  ciclos: null,
  leituras: null,
  grafico: null,      // { leituras (medianas por janela), janelaS, truncado, total }
  erroSeries: null,
  carregandoSeries: false,
  seriesEm: null,
  truncado: { leituras: false, ciclos: false },
  exportando: false,
  tokenSeries: 0,
  filtro: { tipo: PERIODO_PADRAO, de: null, ate: null },
  faixa: null,
  editandoIntervalo: false,
  membroSel: null,
  graficos: null,
};

// ---------------------------------------------------------------- rotas

function lerRota() {
  const h = window.location.hash;
  const m = h.match(/^#\/vaca\/(.+)$/);
  if (m) return { tipo: 'vaca', id: decodeURIComponent(m[1]) };
  if (h === '#/sobre') return { tipo: 'sobre' };
  return { tipo: 'geral' };
}

function limparTelaAnimal() {
  Object.assign(estado, {
    alertas: null,
    erroAlertas: null,
    ciclos: null,
    leituras: null,
    grafico: null,
    erroSeries: null,
    seriesEm: null,
    carregandoSeries: false,
    filtro: { tipo: PERIODO_PADRAO, de: null, ate: null },
    editandoIntervalo: false,
    membroSel: null,
  });
  estado.tokenSeries++;  // descarta respostas de séries ainda pendentes
}

window.addEventListener('hashchange', () => {
  estado.rota = lerRota();
  limparTelaAnimal();
  destruirGraficos();
  window.scrollTo(0, 0);
  carregar();
});

// ---------------------------------------------------------------- dados

async function carregar() {
  clearTimeout(estado.timerProxima);
  clearTimeout(estado.timerAviso);

  const id = ++estado.requisicao;
  const rota = estado.rota;
  estado.carregando = true;
  estado.demorando = false;
  estado.proximaEm = null;
  estado.timerAviso = setTimeout(() => {
    if (id === estado.requisicao) {
      estado.demorando = true;
      render();
    }
  }, AVISO_COLD_START_MS);
  render();

  let proximaEm = INTERVALO_ATUALIZACAO_MS;
  try {
    // Os alertas são opcionais: se falharem, o estado ainda aparece.
    const [painel, alertas] = await Promise.all([
      buscarEstado(),
      rota.tipo === 'vaca'
        ? buscarAlertas(rota.id).then((a) => ({ ok: a }), (e) => ({ erro: e.message || 'Erro desconhecido.' }))
        : null,
    ]);
    if (id !== estado.requisicao) return;
    estado.painel = painel;
    estado.painelEm = Date.now();
    estado.erro = null;
    estado.tentativa = 0;
    if (alertas?.ok) {
      estado.alertas = alertas.ok;
      estado.erroAlertas = null;
    } else if (alertas) {
      estado.erroAlertas = alertas.erro;
    }
  } catch (err) {
    if (id !== estado.requisicao) return;
    console.error(err);
    estado.erro = err.message || 'Erro desconhecido.';
    estado.tentativa++;
    proximaEm = atrasoRetry(estado.tentativa, RETRY_INICIAL_MS, RETRY_MAX_MS);
    estado.proximaEm = Date.now() + proximaEm;
  }

  clearTimeout(estado.timerAviso);
  estado.carregando = false;
  estado.demorando = false;
  render();
  if (rota.tipo === 'vaca' && estado.painel && !estado.erro && seriesVencidas()) carregarSeries();
  estado.timerProxima = setTimeout(carregar, proximaEm);
}

// As séries (leituras e ciclos) são mais pesadas e não precisam ser recarregadas a cada 30 s.
function seriesVencidas() {
  if (estado.carregandoSeries) return false;
  if (estado.seriesEm === null) return true;
  if (estado.filtro.tipo === 'personalizado') return false; // período fixo: só recarrega ao mudar
  const longo = (PERIODOS[estado.filtro.tipo] ?? 24) > 24;
  return Date.now() - estado.seriesEm > (longo ? INTERVALO_SERIES_LONGAS_MS : INTERVALO_SERIES_CURTAS_MS);
}

async function carregarSeries() {
  const faixa = intervaloDoFiltro(estado.filtro);
  if (!faixa || estado.rota.tipo !== 'vaca') return;
  const token = ++estado.tokenSeries;
  const vacaId = estado.rota.id;
  estado.carregandoSeries = true;
  renderPeriodo();
  try {
    const janelaS = janelaAgregacao(faixa.de, faixa.ate, PONTOS_GRAFICO_MAX);
    const [ciclos, leituras, medianas] = await Promise.all([
      buscarDeteccao({ vacaId, de: faixa.de, ate: faixa.ate, limite: LIMITE_CICLOS_PERIODO }),
      buscarLeituras({ vacaId, de: faixa.de, ate: faixa.ate, limite: LIMITE_LEITURAS_PERIODO }),
      buscarLeituras({ vacaId, de: faixa.de, ate: faixa.ate, limite: LIMITE_LEITURAS_GRAFICO, agregarS: janelaS }),
    ]);
    if (token !== estado.tokenSeries) return;
    // Backend sem agregar_s devolve leituras comuns (sem o campo n).
    const agregado = medianas.length > 0 && medianas.every((l) => l.n !== null);
    estado.ciclos = ciclos;
    estado.leituras = leituras;
    estado.grafico = {
      leituras: medianas,
      janelaS: agregado ? janelaS : null,
      truncado: medianas.length >= LIMITE_LEITURAS_GRAFICO,
      total: agregado ? medianas.reduce((s, l) => s + l.n, 0) : null,
    };
    estado.faixa = faixa;
    estado.truncado = {
      leituras: leituras.length >= LIMITE_LEITURAS_PERIODO,
      ciclos: ciclos.length >= LIMITE_CICLOS_PERIODO,
    };
    estado.erroSeries = null;
    estado.seriesEm = Date.now();
  } catch (err) {
    if (token !== estado.tokenSeries) return;
    console.error(err);
    estado.erroSeries = err.message || 'Erro desconhecido.';
    estado.seriesEm = Date.now(); // tenta de novo na próxima atualização
  }
  estado.carregandoSeries = false;
  renderPeriodo();
}

$btnAtualizar.addEventListener('click', () => {
  estado.seriesEm = null;
  carregar();
});

$conteudo.addEventListener('click', (ev) => {
  if (ev.target.closest('[data-acao="tentar"]')) carregar();
});

document.addEventListener('visibilitychange', () => {
  if (document.visibilityState === 'visible' && !estado.carregando &&
      (!estado.painelEm || Date.now() - estado.painelEm > INTERVALO_ATUALIZACAO_MS)) {
    carregar();
  }
});

// A cada segundo: textos "há X minutos" e contagem até a próxima tentativa.
setInterval(() => {
  document.querySelectorAll('[data-ts]').forEach((el) => {
    el.textContent = fmt.relativo(Number(el.dataset.ts));
  });
  const $cont = document.querySelector('[data-contagem]');
  if ($cont && estado.proximaEm) {
    const s = Math.max(0, Math.ceil((estado.proximaEm - Date.now()) / 1000));
    $cont.textContent = `Nova tentativa automática em ${s} s` +
      (estado.tentativa > 1 ? ` (tentativa ${estado.tentativa + 1})` : '');
  }
  renderStatus();
}, 1000);

// ---------------------------------------------------------------- render

function desatualizadoDesde() {
  return estado.erro && estado.painelEm ? estado.painelEm : null;
}

function telaAtual() {
  return telaDeCarga({
    temDados: estado.painel !== null,
    carregando: estado.carregando,
    demorando: estado.demorando,
    erro: estado.erro,
    tentativa: estado.tentativa,
    proximaEmMs: estado.proximaEm === null ? null : Math.max(0, estado.proximaEm - Date.now()),
  });
}

function render() {
  renderStatus();
  renderRodape();
  $btnAtualizar.disabled = estado.carregando;
  const tela = telaAtual();

  if (estado.rota.tipo === 'sobre') {
    destruirGraficos();
    document.title = 'Sobre a regra · Monitoramento da Pata';
    $conteudo.innerHTML = htmlSobre(estado.painel?.parametros ?? null, tela);
    return;
  }
  if (tela.tipo !== 'dados') {
    destruirGraficos();
    $conteudo.innerHTML = htmlCarga(tela);
    return;
  }
  const aviso = tela.desatualizado ? htmlAvisoDesatualizado(tela.aviso) : '';
  if (estado.rota.tipo === 'vaca') {
    renderAnimal(aviso);
  } else {
    destruirGraficos();
    document.title = 'Monitoramento da Pata';
    $conteudo.innerHTML = htmlGeral(estado.painel.animais, aviso, desatualizadoDesde());
  }
}

function renderStatus() {
  const partes = [];
  if (estado.carregando) {
    partes.push('<span class="pulso"></span> Atualizando…');
  } else if (estado.painelEm) {
    partes.push(`Atualizado às ${new Date(estado.painelEm).toLocaleTimeString('pt-BR')}`);
  }
  if (estado.erro && estado.painel !== null) {
    partes.push('<span class="status-erro">⚠ Sem resposta da API</span>');
  }
  $status.innerHTML = partes.join(' · ');
}

function renderRodape() {
  const parametros = estado.painel
    ? `Parâmetros em uso: ${textoParametros(estado.painel.parametros)}.`
    : 'Parâmetros: indisponíveis (a API ainda não respondeu).';
  $rodape.innerHTML = `
    <p class="rodape-aviso">⚠ ${AVISO_FIXO}</p>
    <p class="sutil">${fmt.esc(parametros)} <a href="#/sobre">Sobre a regra</a></p>`;
}

// ---------------------------------------------------------------- tela de um animal

function animalAtual() {
  return estado.painel.animais.find((a) => a.vacaId === estado.rota.id) ?? null;
}

function renderAnimal(aviso) {
  const vacaId = estado.rota.id;
  document.title = `${vacaId} · Monitoramento da Pata`;
  const animal = animalAtual();

  // A estrutura e os gráficos são criados uma vez; depois só os dados mudam.
  if (!estado.graficos) {
    $conteudo.innerHTML = htmlEstruturaAnimal(vacaId);
    estado.graficos = {
      temp: criarGrafico(document.getElementById('g-temp'), 'Temperatura (°C)'),
      dti: criarGrafico(document.getElementById('g-dti'), 'ΔT_i (°C)'),
      dtb: criarGrafico(document.getElementById('g-dtb'), 'ΔT_b (°C)'),
      dtc: criarGrafico(document.getElementById('g-dtc'), 'ΔT_c (°C)'),
    };
    ligarControlesPeriodo();
  }

  document.getElementById('det-aviso').innerHTML = aviso;
  document.getElementById('det-selo').innerHTML = animal ? htmlSelo(animal.estado, desatualizadoDesde()) : '';
  document.getElementById('det-membros').innerHTML = htmlMembros(animal, desatualizadoDesde());
  document.getElementById('det-alertas').innerHTML = htmlAlertas(estado.alertas, estado.erroAlertas, estado.painelEm);
  renderPeriodo();
}

function lerCampoDataHora($inp) {
  const ts = $inp.value ? new Date($inp.value).getTime() : NaN;
  return Number.isNaN(ts) ? null : ts;
}

function ligarControlesPeriodo() {
  const $sel = document.getElementById('sel-periodo');
  const $de = document.getElementById('inp-de');
  const $ate = document.getElementById('inp-ate');

  const novoPeriodo = (filtro) => {
    estado.filtro = filtro;
    estado.editandoIntervalo = false;
    estado.seriesEm = null;
    carregarSeries();
  };
  const aplicarPersonalizado = () => {
    const de = lerCampoDataHora($de);
    const ateMin = lerCampoDataHora($ate);
    const $aviso = document.getElementById('periodo-aviso');
    if (de === null || ateMin === null || ateMin < de) {
      $aviso.textContent = 'Preencha "De" e "Até" com uma data e hora válidas, com "Até" depois de "De".';
      $aviso.hidden = false;
      return;
    }
    $aviso.hidden = true;
    novoPeriodo({ tipo: 'personalizado', de, ate: ateMin + 59_999 }); // inclui o minuto final inteiro
  };

  $sel.addEventListener('change', () => {
    if ($sel.value === 'personalizado') {
      estado.editandoIntervalo = true;
      $de.focus();
      return;
    }
    novoPeriodo({ tipo: $sel.value, de: null, ate: null });
  });
  for (const $inp of [$de, $ate]) {
    $inp.addEventListener('input', () => {
      estado.editandoIntervalo = true;
      $sel.value = 'personalizado';
    });
    $inp.addEventListener('keydown', (ev) => { if (ev.key === 'Enter') aplicarPersonalizado(); });
  }
  document.getElementById('btn-aplicar').addEventListener('click', aplicarPersonalizado);

  document.getElementById('sel-membro').addEventListener('click', (ev) => {
    const b = ev.target.closest('[data-membro]');
    if (!b) return;
    estado.membroSel = b.dataset.membro;
    renderPeriodo();
  });

  document.getElementById('btn-exportar').addEventListener('click', exportarCsv);
}

function quartosDaTabela(leituras) {
  return [...new Set([...QUARTOS_ESPERADOS, ...listarQuartos(leituras)])].sort((a, b) => a - b);
}

// CSV do período inteiro. Se a tela já tem todas as leituras, usa elas; senão
// (passou do limite de carga), baixa o período em páginas.
async function exportarCsv() {
  if (!estado.leituras?.length || !estado.faixa || estado.exportando) return;
  const faixa = estado.faixa;
  const vacaId = estado.rota.id;
  const $btn = document.getElementById('btn-exportar');
  const rotulo = $btn.textContent;
  let leituras = estado.leituras;
  if (estado.truncado.leituras) {
    estado.exportando = true;
    $btn.disabled = true;
    try {
      leituras = await buscarTodasLeituras({
        vacaId, de: faixa.de, ate: faixa.ate, porPagina: LIMITE_LEITURAS_PERIODO,
        aoProgredir: (n) => { $btn.textContent = `Baixando… ${n.toLocaleString('pt-BR')} leituras`; },
      });
    } catch (err) {
      console.error(err);
      window.alert(`Não foi possível exportar o período inteiro: ${err.message || err}`);
      return;
    } finally {
      estado.exportando = false;
      $btn.textContent = rotulo;
      renderPeriodo();
    }
  }
  const cicloMs = (estado.painel?.parametros.cicloS ?? 0) * 1000;
  const csv = gerarCsv(leituras, quartosDaTabela(leituras), vacaId, JANELA_AGRUPAMENTO_S * 1000,
    indiceEstadoCiclo(estado.ciclos ?? [], cicloMs));
  baixar(nomeArquivo(vacaId, faixa.de, faixa.ate), csv);
}

function mensagemGrafico(id, texto) {
  const $p = document.querySelector(`#painel-${id} .grafico-vazio`);
  if (!$p) return;
  $p.textContent = texto ?? '';
  $p.hidden = !texto;
}

function textoPeriodo(faixa, semSeries) {
  if (estado.carregandoSeries) return 'Carregando o período…';
  if (estado.erroSeries && semSeries) return `⚠ Não foi possível carregar o período: ${estado.erroSeries}`;
  if (semSeries) return 'Carregando o período…';

  const g = estado.grafico;
  // O total exato vem da soma de n das medianas; sem agregação, é só o que foi baixado.
  const total = g.total !== null && !g.truncado ? g.total : estado.leituras.length;
  let info = `${fmt.dataHoraCurta(faixa.de)} – ${fmt.dataHoraCurta(faixa.ate)} · ${total.toLocaleString('pt-BR')} leituras · ${estado.ciclos.length} ciclos do detector`;
  if (g.janelaS) info += ` · gráfico de temperatura: mediana por ${textoJanela(g.janelaS)}`;
  if (g.truncado || estado.truncado.ciclos) info += ' · ⚠ período maior que o limite de carga dos gráficos: escolha um período menor para ver tudo.';
  if (estado.truncado.leituras) info += ` · a tabela mostra as ${LIMITE_LEITURAS_PERIODO.toLocaleString('pt-BR')} leituras mais recentes; o CSV baixa o período inteiro em partes.`;
  if (estado.erroSeries) info += ` · ⚠ última atualização falhou (${estado.erroSeries}).`;
  return info;
}

// Membros que aparecem nos gráficos; escolhe um se ainda não houver seleção válida.
function escolherMembros(animal) {
  const membros = membrosPresentes(estado.ciclos, [...estado.leituras, ...estado.grafico.leituras]);
  if (animal) for (const m of animal.membros) if (!membros.includes(m.membro)) membros.push(m.membro);
  if (!estado.membroSel || !membros.includes(estado.membroSel)) {
    // começa pelo membro com alerta aberto, se houver
    const comAlerta = animal?.membros.find((m) => m.alertaAberto && membros.includes(m.membro));
    estado.membroSel = comAlerta?.membro ?? membros[0] ?? null;
  }
  return membros;
}

// Aplica o período escolhido aos gráficos, à tabela e ao texto de resumo.
function renderPeriodo() {
  if (!estado.graficos) return;
  const faixa = estado.faixa ?? intervaloDoFiltro(estado.filtro);

  if (!estado.editandoIntervalo) {
    document.getElementById('sel-periodo').value = estado.filtro.tipo;
    if (faixa) {
      document.getElementById('inp-de').value = fmt.paraInputDataHora(faixa.de);
      document.getElementById('inp-ate').value = fmt.paraInputDataHora(faixa.ate);
    }
  }

  const { ciclos, leituras } = estado;
  const semSeries = ciclos === null || leituras === null || estado.grafico === null;
  const $info = document.getElementById('periodo-info');
  $info.textContent = textoPeriodo(faixa, semSeries);
  const truncou = estado.truncado.ciclos || Boolean(estado.grafico?.truncado);
  $info.classList.toggle('txt-alerta', Boolean(estado.erroSeries) || truncou);
  document.getElementById('btn-exportar').disabled =
    semSeries || !leituras.length || estado.carregandoSeries || estado.exportando;

  if (semSeries) {
    const msg = estado.erroSeries ? `Não foi possível carregar: ${estado.erroSeries}` : 'Carregando…';
    for (const id of ID_GRAFICOS) mensagemGrafico(id, msg);
    document.getElementById('det-tabela').innerHTML = `<p class="sutil tabela-vazia">${fmt.esc(msg)}</p>`;
    return;
  }

  const membros = escolherMembros(animalAtual());
  const membro = estado.membroSel;
  document.getElementById('sel-membro').innerHTML = htmlSeletorMembro(membros, membro);

  const p = estado.painel.parametros;
  const cicloMs = (p.cicloS ?? 300) * 1000;
  const agora = Date.now();
  const alertas = estado.alertas ?? [];
  const eixo = { xMin: faixa.de, xMax: faixa.ate };
  const faixasMembro = (comp = null) => [
    ...intervalosAlerta(alertas, membro, agora, comp).map((i) => ({ ...i, cor: COR_ALERTA })),
    ...intervalosCongelados(ciclos, membro, cicloMs).map((i) => ({ ...i, cor: COR_CONGELADO, rodape: true })),
  ];
  const nomeM = membro ? rotuloMembro(membro) : '';
  const porSensor = (series) => series.map((s, i) => ({ label: `Sens ${s.sensor}`, pontos: s.pontos, cor: corSerie(i) }));

  // Temperatura: usa as medianas por janela; se o backend não agregou, usa as leituras da tabela.
  const g = estado.grafico;
  const temp = g.janelaS
    ? seriesTemperatura(g.leituras, membro, Math.max(QUEBRA_MS, 2 * g.janelaS * 1000))
    : seriesTemperatura(leituras, membro, QUEBRA_MS);
  atualizarGrafico(estado.graficos.temp, { ...eixo, series: porSensor(temp), intervalos: faixasMembro() });
  mensagemGrafico('g-temp', temp.some((s) => s.pontos.length) ? null
    : `Nenhuma leitura de ${nomeM.toLowerCase() || 'este animal'} neste período.`);

  const dti = seriesDtI(ciclos, membro, QUEBRA_MS);
  atualizarGrafico(estado.graficos.dti, {
    ...eixo,
    series: porSensor(dti),
    limiares: [{ label: `λ_s = ${fmtLambda(p.lambdaS)}`, y: p.lambdaS }],
    intervalos: faixasMembro('S'),
  });
  mensagemGrafico('g-dti', dti.some((s) => s.pontos.length) ? null
    : 'Sem ΔT_i neste período (membro aprendendo a linha de base, em falha de sensor ou sem ciclos).');

  const membrosB = membros.filter((m) => m !== 'U' || membros.length === 1);
  const dtb = membrosB.map((m) => ({
    label: rotuloMembro(m), pontos: serieCampo(ciclos, m, 'dtB', QUEBRA_MS), cor: COR_MEMBRO[m] ?? corSerie(3),
  }));
  atualizarGrafico(estado.graficos.dtb, {
    ...eixo,
    series: dtb,
    limiares: [{ label: `λ_b = ${fmtLambda(p.lambdaB)}`, y: p.lambdaB }],
    intervalos: faixasMembro('B'),
  });
  mensagemGrafico('g-dtb', dtb.some((s) => s.pontos.length) ? null
    : 'Sem ΔT_b neste período (aprendendo a linha de base, falha de sensor ou sem ciclos).');

  const dtc = serieDtC(ciclos, QUEBRA_MS);
  document.getElementById('painel-g-dtc').hidden = !(membros.includes('E') && membros.includes('D'));
  atualizarGrafico(estado.graficos.dtc, {
    ...eixo,
    series: [{ label: 'ΔT_c (E − D)', pontos: dtc, cor: corSerie(2) }],
    limiares: [
      { label: `+λ_c = ${fmtLambda(p.lambdaC)}`, y: p.lambdaC },
      { label: `−λ_c`, y: p.lambdaC === null ? null : -p.lambdaC, cor: COR_LIMIAR },
    ],
    intervalos: intervalosAlerta(alertas, null, agora, 'C').map((i) => ({ ...i, cor: COR_ALERTA })),
  });
  mensagemGrafico('g-dtc', dtc.length ? null
    : 'Sem ΔT_c neste período (precisa dos dois membros com ΔT_b no mesmo ciclo).');

  renderTabela(leituras, ciclos, cicloMs);
}

// Tabela do período, mais recentes primeiro e limitada a LINHAS_TABELA_MAX (o CSV leva tudo).
function renderTabela(leituras, ciclos, cicloMs) {
  const linhas = agruparEmLinhas(leituras, JANELA_AGRUPAMENTO_S * 1000);
  const n = leituras.length;
  document.getElementById('det-contagem').textContent =
    (estado.truncado.leituras ? `(as ${n} leituras mais recentes do período`
      : `(${n} ${n === 1 ? 'leitura' : 'leituras'} no período`) +
    (linhas.length > LINHAS_TABELA_MAX ? ` · mostrando as ${LINHAS_TABELA_MAX} linhas mais recentes; o CSV leva todas)` : ')');

  const $tabela = document.getElementById('det-tabela');
  const rolagem = $tabela.scrollTop;
  $tabela.innerHTML = linhas.length
    ? htmlTabela(linhas.slice(0, LINHAS_TABELA_MAX), quartosDaTabela(leituras), indiceEstadoCiclo(ciclos, cicloMs))
    : `<p class="sutil tabela-vazia">Nenhuma leitura neste período.</p>`;
  $tabela.scrollTop = rolagem;
}

function destruirGraficos() {
  if (!estado.graficos) return;
  for (const g of Object.values(estado.graficos)) g.destroy();
  estado.graficos = null;
}

renderRodape();
carregar();

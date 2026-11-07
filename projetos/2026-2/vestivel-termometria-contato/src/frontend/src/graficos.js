import {
  Chart,
  LineController,
  LineElement,
  PointElement,
  LinearScale,
  Legend,
  Tooltip,
} from 'chart.js';
import { eixoTempo, dataHora } from './formatar.js';

Chart.register(LineController, LineElement, PointElement, LinearScale, Legend, Tooltip);

// Paleta Okabe-Ito (boa para daltônicos). O laranja-avermelhado fica para o limiar λ.
const PALETA = ['#0072B2', '#E69F00', '#009E73', '#CC79A7', '#56B4E9', '#000000', '#882255', '#999933'];
export const corSerie = (i) => PALETA[i % PALETA.length];
export const COR_MEMBRO = { E: '#0072B2', D: '#E69F00', U: '#009E73' };
export const COR_LIMIAR = '#D55E00';
export const COR_ALERTA = 'rgba(213, 94, 0, 0.16)';
export const COR_CONGELADO = 'rgba(86, 180, 233, 0.22)';

// Plugin que desenha faixas verticais atrás das linhas (alertas e ciclos congelados).
const marcacoes = {
  id: 'marcacoes',
  beforeDatasetsDraw(chart, _args, opts) {
    const intervalos = opts?.intervalos ?? [];
    if (!intervalos.length) return;
    const { ctx, chartArea: a, scales: { x } } = chart;
    ctx.save();
    for (const i of intervalos) {
      const x0 = Math.max(a.left, x.getPixelForValue(i.de));
      const x1 = Math.min(a.right, x.getPixelForValue(i.ate));
      if (x1 <= x0) continue;
      ctx.fillStyle = i.cor;
      // congelados: faixa fina no rodapé; alertas: altura toda
      const alto = i.rodape ? Math.min(14, a.bottom - a.top) : a.bottom - a.top;
      ctx.fillRect(x0, a.bottom - alto, x1 - x0, alto);
    }
    ctx.restore();
  },
};
Chart.register(marcacoes);

const raioPonto = (n) => (n > 150 ? 0 : 2);

export function criarGrafico(canvas, tituloY) {
  return new Chart(canvas, {
    type: 'line',
    data: { datasets: [] },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: false,
      parsing: false,
      spanGaps: false,
      interaction: { mode: 'nearest', axis: 'x', intersect: false },
      scales: {
        x: {
          type: 'linear',
          ticks: {
            maxTicksLimit: window.innerWidth < 600 ? 4 : 6,
            callback(v) {
              const { min, max } = this.chart.scales.x;
              return eixoTempo(v, max - min);
            },
          },
        },
        y: { title: { display: true, text: tituloY } },
      },
      plugins: {
        legend: { position: 'bottom', labels: { boxWidth: 12 } },
        tooltip: { callbacks: { title: (itens) => (itens.length ? dataHora(itens[0].parsed.x) : '') } },
        marcacoes: { intervalos: [] },
      },
    },
  });
}

// series: [{ label, pontos, cor }]
// limiares: [{ label, y, cor }], desenhados como linhas horizontais tracejadas
// intervalos: faixas de fundo [{ de, ate, cor, rodape }]
export function atualizarGrafico(grafico, { series, limiares = [], intervalos = [], xMin, xMax }) {
  const datasets = series.map((s) => ({
    label: s.label,
    data: s.pontos,
    borderColor: s.cor,
    backgroundColor: s.cor,
    borderWidth: 2,
    pointRadius: raioPonto(s.pontos.length),
    tension: 0.1,
  }));
  for (const l of limiares) {
    if (l.y === null || l.y === undefined) continue;
    datasets.push({
      label: l.label,
      data: [{ x: xMin, y: l.y }, { x: xMax, y: l.y }],
      borderColor: l.cor ?? COR_LIMIAR,
      backgroundColor: l.cor ?? COR_LIMIAR,
      borderDash: [6, 4],
      borderWidth: 2,
      pointRadius: 0,
      pointHitRadius: 0,
    });
  }
  grafico.data.datasets = datasets;
  grafico.options.plugins.marcacoes.intervalos = intervalos;
  grafico.options.scales.x.min = xMin;
  grafico.options.scales.x.max = xMax;
  // garante que o limiar aparece mesmo quando o ΔT é pequeno
  const ys = limiares.map((l) => l.y).filter((y) => Number.isFinite(y));
  grafico.options.scales.y.suggestedMax = ys.length ? Math.max(...ys) * 1.15 : undefined;
  grafico.options.scales.y.suggestedMin = ys.length ? Math.min(0, ...ys.map((y) => (y < 0 ? y * 1.15 : 0))) : undefined;
  grafico.update('none');
}

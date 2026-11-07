// Tela "Sobre a regra": parâmetros em uso, componentes e estados.

import { INDISPONIVEL, ESTADOS, COMPONENTES, rotuloComponente, textoDuracaoCiclos } from '../estado.js';
import { esc } from '../formatar.js';
import { AVISO_FIXO } from './comum.js';

// p: parâmetros normalizados do /estado, ou null se a API ainda não respondeu.
export function htmlSobre(p, tela) {
  const v = (x, suf = '') => (x === null || x === undefined ? INDISPONIVEL : `${x.toLocaleString('pt-BR')}${suf}`);
  const semApi = !p ? `<p class="txt-alerta">Os parâmetros vêm da API, que ainda não respondeu
    (${esc(tela.tipo === 'erro' ? tela.mensagem : 'carregando')}). Nenhum valor é mostrado sem ela.</p>` : '';
  const histerese = p?.histerese == null
    ? INDISPONIVEL : `abaixo de ${p.histerese.toLocaleString('pt-BR')} × λ por N ciclos`;

  return `
    <div class="det-cabecalho"><a href="#/" class="btn btn-voltar">← Voltar</a><h2>Sobre a regra de alerta</h2></div>
    <section class="painel">
      <p class="aviso-fixo">⚠ ${AVISO_FIXO}</p>
      <p>O estado e os alertas são calculados pelo servidor (detector do backend). Este painel só mostra o
      que a API informa: não recalcula nem estima nada.</p>
      ${semApi}
      <h3>Parâmetros em uso</h3>
      <dl class="tabela-params">
        <div><dt>N (persistência)</dt><dd>${p ? esc(textoDuracaoCiclos(p.nPersist, p.cicloS)) : INDISPONIVEL}</dd></div>
        <div><dt>λ_s (espacial)</dt><dd>${v(p?.lambdaS, ' °C')}</dd></div>
        <div><dt>λ_b (temporal)</dt><dd>${v(p?.lambdaB, ' °C')}</dd></div>
        <div><dt>λ_c (contralateral)</dt><dd>${v(p?.lambdaC, ' °C')}</dd></div>
        <div><dt>Histerese de fechamento</dt><dd>${histerese}</dd></div>
        <div><dt>Sem dados após</dt><dd>${v(p?.semDadosMin, ' min')}</dd></div>
        <div><dt>Tempo máximo de congelamento</dt><dd>${v(p?.congelaMaxH, ' h')}</dd></div>
      </dl>
      <h3>Componentes</h3>
      <ul>${Object.entries(COMPONENTES).map(([c, x]) => `<li><strong>${esc(rotuloComponente(c))}</strong>: ${esc(x.explicacao)}.</li>`).join('')}</ul>
      <p class="sutil">Um componente dispara quando passa do seu limiar λ por N ciclos válidos seguidos. O alerta
      fecha quando todos os componentes calculados ficam abaixo da histerese por N ciclos.</p>
      <h3>Estados</h3>
      <ul class="lista-estados">${Object.values(ESTADOS).map((e) => `<li><span class="selo ${e.classe}">${e.icone} ${esc(e.rotulo)}</span> ${esc(e.descricao)}</li>`).join('')}</ul>
    </section>`;
}

// Tela inicial: um card por animal.

import { INDISPONIVEL, ESTADOS, infoEstado, detalhesMembro, rotuloMembro, contarPorEstado } from '../estado.js';
import { dataHora, esc, relativo } from '../formatar.js';
import { htmlDadosMembro, htmlSelo } from './comum.js';

export function htmlGeral(animais, aviso, desatualizadoDesde) {
  if (animais.length === 0) {
    return `${aviso}
      <div class="aviso"><p><strong>Nenhum animal registrado ainda.</strong></p>
      <p class="sutil">Os animais aparecem aqui assim que a API receber as primeiras leituras.</p></div>`;
  }

  const c = contarPorEstado(animais);
  const chips = ['ALERTA', 'FALHA_SENSOR', 'SEM_DADOS', 'ARMANDO', 'OK']
    .filter((e) => c[e] > 0)
    .map((e) => `<span class="chip ${ESTADOS[e].classe}">${ESTADOS[e].icone} ${c[e]} ${esc(ESTADOS[e].rotulo.toLowerCase())}</span>`)
    .join('');
  const extraAlerta = c.alertaAberto > c.ALERTA
    ? `<span class="chip est-alerta">⚠ ${c.alertaAberto} com alerta aberto</span>` : '';

  return `${aviso}
    <div class="resumo-geral">
      <span><strong>${c.total}</strong> ${c.total === 1 ? 'animal monitorado' : 'animais monitorados'}</span>
      ${chips}${extraAlerta}
    </div>
    <div class="grade">${animais.map((a) => htmlCard(a, desatualizadoDesde)).join('')}</div>`;
}

function htmlCard(a, desatualizadoDesde) {
  const info = infoEstado(a.estado);
  return `
    <a class="card ${info.classe}" href="#/vaca/${encodeURIComponent(a.vacaId)}">
      <div class="card-topo">
        <h2>${esc(a.vacaId)}</h2>
        ${htmlSelo(a.estado, desatualizadoDesde)}
      </div>
      ${a.membros.length
        ? a.membros.map((m) => htmlMembroCompacto(m, desatualizadoDesde)).join('')
        : '<p class="sutil">Sem estado do detector para este animal (só leituras antigas).</p>'}
      <div class="card-rodape">
        Última leitura ${a.ultimaLeitura === null ? INDISPONIVEL
          : `<span title="${dataHora(a.ultimaLeitura)}" data-ts="${a.ultimaLeitura}">${relativo(a.ultimaLeitura)}</span>`}
      </div>
    </a>`;
}

// No card mostra só as duas primeiras informações do membro.
function htmlMembroCompacto(m, desatualizadoDesde) {
  const linhas = detalhesMembro(m).filter((l) => l.rotulo !== 'Último pacote').slice(0, 2);
  return `
    <div class="membro-linha">
      <div class="membro-topo"><span class="membro-nome">${esc(rotuloMembro(m.membro))}</span>${htmlSelo(m.estado, desatualizadoDesde, 'selo-pequeno')}</div>
      ${m.alertaAberto && m.estado !== 'ALERTA' && m.estado !== 'SEM_DADOS'
        ? '<div class="txt-alerta pequeno">⚠ Alerta aberto</div>' : ''}
      ${htmlDadosMembro(linhas)}
    </div>`;
}

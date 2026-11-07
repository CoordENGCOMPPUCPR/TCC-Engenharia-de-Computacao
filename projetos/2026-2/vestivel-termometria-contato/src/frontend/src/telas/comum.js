// Pedaços de HTML usados em mais de uma tela.

import { seloEstado } from '../estado.js';
import { API_BASE_URL } from '../config.js';
import { dataHora, esc } from '../formatar.js';

export const AVISO_FIXO = 'Limiares provisórios, calibrados em modelo sintético; sem validação em animais.';

// desatualizadoDesde: horário da última resposta boa, quando a última consulta falhou.
export function htmlSelo(codigo, desatualizadoDesde, extraClasse = '') {
  const s = seloEstado(codigo, { desatualizadoDesde });
  return `<span class="selo ${s.classe} ${extraClasse}">${esc(s.texto)}</span>`;
}

// Tela de carregamento, de servidor acordando ou de erro (sem dados ainda).
export function htmlCarga(tela) {
  if (tela.tipo === 'erro') {
    return `
      <div class="aviso aviso-erro" role="alert">
        <p class="aviso-icone" aria-hidden="true">⚠</p>
        <p><strong>Não foi possível obter o estado dos animais.</strong></p>
        <p>${esc(tela.mensagem)}</p>
        <p class="sutil" data-contagem>${esc(tela.proxima ?? '')}</p>
        <p class="sutil">Nenhum estado é mostrado enquanto a API não responder. Se o problema continuar,
        a API (<code>${esc(API_BASE_URL)}</code>) pode estar fora do ar.</p>
        <button type="button" class="btn" data-acao="tentar">Tentar agora</button>
      </div>`;
  }
  return `
    <div class="aviso" role="status">
      <div class="spinner" aria-hidden="true"></div>
      <p><strong>${tela.tipo === 'acordando' ? 'Servidor acordando…' : 'Carregando…'}</strong></p>
      <p class="sutil">${esc(tela.mensagem)}</p>
    </div>`;
}

// Faixa mostrada em cima dos dados quando a última atualização falhou.
export function htmlAvisoDesatualizado(texto) {
  return `<div class="faixa-aviso" role="alert">⚠ ${esc(texto)}
    <span class="sutil" data-contagem></span>
    <button type="button" class="btn btn-pequeno" data-acao="tentar">Tentar agora</button></div>`;
}

// Lista <dl> com as linhas {rotulo, valor, destaque, ts} de um membro.
export function htmlDadosMembro(linhas, { comTs = false } = {}) {
  return `<dl class="membro-dados">${linhas.map((l) => {
    const ts = comTs && l.ts ? ` title="${dataHora(l.ts)}" data-ts="${l.ts}"` : '';
    return `<div><dt>${esc(l.rotulo)}</dt><dd class="${l.destaque ? 'txt-forte' : ''}"${ts}>${esc(l.valor)}</dd></div>`;
  }).join('')}</dl>`;
}

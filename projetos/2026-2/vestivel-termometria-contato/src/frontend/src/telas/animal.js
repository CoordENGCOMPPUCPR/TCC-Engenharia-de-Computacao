// HTML da tela de um animal: membros, alertas, gráficos e tabela de leituras.

import {
  INDISPONIVEL, infoEstado, detalhesMembro, rotuloMembro, descreverAlerta,
} from '../estado.js';
import * as fmt from '../formatar.js';
import { COR_ALERTA, COR_CONGELADO } from '../graficos.js';
import { htmlDadosMembro, htmlSelo } from './comum.js';

// Estrutura fixa da tela. Os pedaços com id são preenchidos depois, a cada atualização.
export function htmlEstruturaAnimal(vacaId) {
  return `
      <div id="det-aviso"></div>
      <div class="det-cabecalho">
        <a href="#/" class="btn btn-voltar">← Voltar</a>
        <h2>Vaca ${fmt.esc(vacaId)}</h2>
        <span id="det-selo"></span>
      </div>
      <section id="det-membros"></section>
      <section class="painel">
        <h3>Alertas</h3>
        <div id="det-alertas"></div>
      </section>
      <section class="painel barra-periodo">
        <div class="filtro-linha">
          <label for="sel-periodo">Período</label>
          <select id="sel-periodo">
            <option value="6h">Últimas 6 h</option>
            <option value="24h">Últimas 24 h</option>
            <option value="3d">Últimos 3 dias</option>
            <option value="7d">Últimos 7 dias</option>
            <option value="personalizado">Escolher data e hora…</option>
          </select>
        </div>
        <div class="filtro-linha">
          <span class="campo"><label for="inp-de">De</label> <input type="datetime-local" id="inp-de" /></span>
          <span class="campo"><label for="inp-ate">Até</label> <input type="datetime-local" id="inp-ate" /></span>
          <button type="button" class="btn" id="btn-aplicar">Aplicar</button>
        </div>
        <div class="filtro-linha">
          <button type="button" class="btn btn-primario" id="btn-exportar">⬇ Exportar CSV do período</button>
          <span class="sutil" id="periodo-info" aria-live="polite"></span>
        </div>
        <p class="filtro-aviso" id="periodo-aviso" hidden></p>
        <div class="filtro-linha" id="sel-membro" role="group" aria-label="Membro mostrado nos gráficos por sensor"></div>
      </section>
      ${htmlPainelGrafico('g-temp', 'Temperatura na coroa do casco, por sensor', 'Temperatura (°C): mediana de cada sensor por janela de tempo (indicada acima), das leituras recebidas.')}
      ${htmlPainelGrafico('g-dti', 'ΔT espacial por sensor (ΔT_i)', 'Calculado pelo detector a cada ciclo de 5 min. Linha tracejada: λ_s.')}
      ${htmlPainelGrafico('g-dtb', 'ΔT temporal (ΔT_b) por membro', 'Temperatura do membro acima da própria linha de base. Linha tracejada: λ_b.')}
      ${htmlPainelGrafico('g-dtc', 'ΔT contralateral (ΔT_c = E − D)', 'Positivo: esquerdo mais quente. Linhas tracejadas: +λ_c e −λ_c.')}
      <section class="painel">
        <h3>Histórico de leituras <span class="sutil" id="det-contagem"></span></h3>
        <div class="tabela-wrap" id="det-tabela"></div>
      </section>`;
}

function htmlPainelGrafico(id, titulo, nota) {
  return `
    <section class="painel" id="painel-${id}">
      <h3>${titulo}</h3>
      <p class="sutil pequeno">${nota} <span class="legenda-faixa"><i style="background:${COR_ALERTA}"></i>alerta</span>
      <span class="legenda-faixa"><i style="background:${COR_CONGELADO}"></i>ciclo congelado (fora da linha de base)</span></p>
      <div class="grafico">
        <canvas id="${id}" aria-label="${titulo}"></canvas>
        <p class="grafico-vazio" hidden></p>
      </div>
    </section>`;
}

// ------------------------------------------------------------ membros

export function htmlMembros(animal, desatualizadoDesde) {
  if (!animal) {
    return `<div class="painel aviso-erro"><p><strong>Este animal não aparece no estado do detector (GET /estado).</strong></p>
       <p class="sutil">Confira o identificador. Os gráficos abaixo mostram o que a API tiver para ele.</p></div>`;
  }
  if (!animal.membros.length) {
    return '<div class="painel"><p>Sem estado do detector para este animal (só leituras antigas, anteriores ao detector).</p></div>';
  }
  return `<div class="grade-membros">${animal.membros.map((m) => htmlMembro(m, desatualizadoDesde)).join('')}</div>`;
}

function htmlMembro(m, desatualizadoDesde) {
  const info = infoEstado(m.estado);
  return `
    <div class="painel membro-painel ${info.classe}">
      <div class="membro-topo"><h3>${fmt.esc(rotuloMembro(m.membro))}</h3>${htmlSelo(m.estado, desatualizadoDesde)}</div>
      <p class="sutil">${fmt.esc(info.descricao)}</p>
      ${m.alertaAberto && m.estado !== 'ALERTA' && m.estado !== 'SEM_DADOS'
        ? '<p class="txt-alerta">⚠ Há um alerta aberto neste membro.</p>' : ''}
      ${htmlDadosMembro(detalhesMembro(m), { comTs: true })}
    </div>`;
}

// ------------------------------------------------------------ alertas

// alertas: lista normalizada, ou null se ainda não carregou.
export function htmlAlertas(alertas, erroAlertas, painelEm) {
  if (alertas === null) {
    return erroAlertas
      ? `<p class="txt-alerta">Não foi possível carregar os alertas: ${fmt.esc(erroAlertas)}</p>`
      : '<p class="sutil">Carregando alertas…</p>';
  }
  const falha = erroAlertas
    ? `<p class="txt-alerta">⚠ A última atualização dos alertas falhou (${fmt.esc(erroAlertas)}); lista de ${fmt.dataHora(painelEm)}.</p>` : '';
  if (!alertas.length) return `${falha}<p class="sutil">Nenhum alerta registrado para este animal.</p>`;
  return `${falha}<ul class="lista-alertas">${alertas.map(htmlAlerta).join('')}</ul>`;
}

function htmlAlerta(a) {
  const d = descreverAlerta(a);
  return `
      <li class="alerta-item ${a.aberto ? 'alerta-aberto' : 'alerta-fechado'}">
        <div class="alerta-topo">
          <strong>${a.aberto ? '⚠' : '✓'} ${fmt.esc(d.titulo)}</strong>
          <span class="sutil">${fmt.esc(d.membro)}</span>
        </div>
        <p class="alerta-disparo">${fmt.esc(d.disparo)}</p>
        <dl class="membro-dados">
          <div><dt>Componentes</dt><dd>${d.componentes.map((c) => fmt.esc(c)).join(', ')}</dd></div>
          <div><dt>Início da elevação</dt><dd>${fmt.esc(d.inicioElevacao)}</dd></div>
          <div><dt>Início do alerta</dt><dd>${fmt.esc(d.inicio)}</dd></div>
          <div><dt>Fim</dt><dd>${fmt.esc(d.fim)}</dd></div>
          ${d.picos.map((p) => `<div><dt>Pico ${fmt.esc(p.componente)}</dt><dd>${fmt.esc(p.valor)}</dd></div>`).join('')}
        </dl>
        <p class="sutil pequeno">Parâmetros na abertura: ${fmt.esc(d.parametros)}</p>
      </li>`;
}

// ------------------------------------------------------------ período

// Botões para escolher o membro dos gráficos por sensor (só se houver mais de um).
export function htmlSeletorMembro(membros, selecionado) {
  if (membros.length <= 1) return '';
  return `<span class="rotulo-campo">Gráficos por sensor:</span>${membros.map((m) => `<button type="button" class="btn ${m === selecionado ? 'btn-ativo' : ''}"
        data-membro="${fmt.esc(m)}" aria-pressed="${m === selecionado}">${fmt.esc(rotuloMembro(m))}</button>`).join('')}`;
}

export function textoJanela(s) {
  if (s < 60) return `${s} s`;
  if (s < 3600) return `${s / 60} min`;
  return `${s / 3600} h`;
}

export function fmtLambda(v) {
  return v === null ? INDISPONIVEL : `${v.toLocaleString('pt-BR')} °C`;
}

// ------------------------------------------------------------ tabela

// RSSI/SNR da linha. Os sensores chegam no mesmo pacote, então o valor costuma ser
// um só; se vierem diferentes, mostra a faixa.
function sinalDaLinha(leituras, campo, unidade) {
  const vals = leituras.map((l) => l[campo]).filter((v) => v !== null);
  if (!vals.length) return '—';
  const min = Math.min(...vals);
  const max = Math.max(...vals);
  return min === max ? `${min} ${unidade}` : `${min} a ${max} ${unidade}`;
}

function htmlCelulaEstado(estado) {
  if (!estado) return `<span class="sutil">${INDISPONIVEL}</span>`;
  const info = infoEstado(estado);
  return `<span class="${info.classe} txt-estado">${info.icone} ${fmt.esc(info.rotulo)}</span>`;
}

// Uma linha por pacote LoRa e uma coluna por sensor (temperatura e ΔT), mais
// membro, estado do ciclo e RSSI/SNR.
export function htmlTabela(linhas, quartos, estadoCiclo) {
  const corpo = linhas.map((linha) => {
    const celulas = quartos.map((q) => {
      const l = linha.porQuarto.get(q);
      if (!l) return '<td class="cel-vazia">—</td>';
      return `<td>
        <span class="cel-temp">${fmt.temp(l.temp_raw, 2)}</span>
        <span class="cel-delta">ΔT ${fmt.delta(l.delta_t)}</span>
      </td>`;
    }).join('');
    const doPacote = [...linha.porQuarto.values()];
    return `<tr>
      <td title="${fmt.dataHora(linha.ts)}">${fmt.dataHoraCurta(linha.ts)}</td>
      <td>${fmt.esc(linha.membro ?? 'U')}</td>${celulas}
      <td class="cel-estado">${htmlCelulaEstado(estadoCiclo(linha.membro, linha.ts))}</td>
      <td class="cel-sinal">${sinalDaLinha(doPacote, 'rssi', 'dBm')}</td>
      <td class="cel-sinal">${sinalDaLinha(doPacote, 'snr', 'dB')}</td>
    </tr>`;
  }).join('');
  return `
    <table class="tabela-sensores">
      <thead><tr>
        <th>Data/hora</th><th>Membro</th>${quartos.map((q) => `<th>Sens ${q}</th>`).join('')}<th>Estado do ciclo</th><th>RSSI</th><th>SNR</th>
      </tr></thead>
      <tbody>${corpo}</tbody>
    </table>`;
}

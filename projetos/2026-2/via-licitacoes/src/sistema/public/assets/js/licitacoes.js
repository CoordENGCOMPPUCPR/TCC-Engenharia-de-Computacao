const API = BASE_URL + '/api/licitacoes.php';

const lista          = document.getElementById('listaLicitacoes');
const contador       = document.getElementById('contadorResultados');
const paginacao      = document.getElementById('paginacao');
const formFiltros    = document.getElementById('formFiltros');
const filtroBusca    = document.getElementById('filtroBusca');
const filtroUf       = document.getElementById('filtroUf');
const filtroData     = document.getElementById('filtroData');
const filtroOrdem    = document.getElementById('filtroOrdem');
const filtroApenas   = document.getElementById('filtroApenasInteresses');
let selecaoPalavras = new Set();
let selecaoRegioes  = new Set();
let paginaAtual = 1;

const UFS = ['AC','AL','AP','AM','BA','CE','DF','ES','GO','MA','MT','MS','MG','PA','PB','PR','PE','PI','RJ','RN','RS','RO','RR','SC','SP','SE','TO'];
UFS.forEach(uf => {
  const opt = document.createElement('option');
  opt.value = uf; opt.textContent = uf;
  filtroUf.appendChild(opt);
});

/* ---------- HELPERS ---------- */
function escaparHTML(s) {
  if (s == null) return '';
  return String(s).replace(/[&<>"']/g, c => ({ '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;' }[c]));
}
function formatarValor(v) {
  if (!v || v == 0) return '—';
  return 'R$ ' + parseFloat(v).toLocaleString('pt-BR', { minimumFractionDigits: 2 });
}
function formatarDataCurta(dt) {
  if (!dt) return '—';
  const d = new Date(dt.replace(' ', 'T'));
  if (isNaN(d)) return dt;
  return d.toLocaleDateString('pt-BR');
}
function formatarDataHora(dt) {
  if (!dt) return '—';
  const d = new Date(dt.replace(' ', 'T'));
  if (isNaN(d)) return dt;
  return d.toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' });
}
function truncar(txt, max = 250) {
  if (!txt) return '';
  return txt.length > max ? txt.substring(0, max) + '…' : txt;
}
function diasRestantes(fimStr) {
  if (!fimStr) return null;
  const fim = new Date(fimStr.replace(' ', 'T'));
  if (isNaN(fim)) return null;
  const diff = fim - new Date();
  if (diff < 0) return { texto: 'Encerrado', encerrado: true };
  const dias  = Math.floor(diff / 86400000);
  const horas = Math.floor((diff % 86400000) / 3600000);
  if (dias > 0) return { texto: `Encerra em ${dias} dia${dias > 1 ? 's' : ''} e ${horas}h`, encerrado: false };
  return { texto: `Encerra em ${horas}h`, encerrado: false };
}

/* ---------- CARREGAR CHIPS DE INTERESSES ---------- */
async function carregarInteressesDisponiveis() {
  const res = await fetch(`${API}?action=interesses_disponiveis`);
  const data = await res.json();
  if (!data.success) return;

  const boxP = document.getElementById('ifbPalavras');
  const boxR = document.getElementById('ifbRegioes');

  if (!data.palavras.length) {
    boxP.innerHTML = '<p class="empty-msg">Nenhuma palavra cadastrada. <a href="' + BASE_URL + '/app/palavras.php" style="color:var(--azul-principal);">Cadastrar</a></p>';
  } else {
    boxP.innerHTML = data.palavras.map(p => `
      <button type="button" class="chip-filtro" data-tipo="palavra" data-valor="${escaparHTML(p.palavra)}">
        ${escaparHTML(p.palavra)}
      </button>
    `).join('');
  }

  if (!data.regioes.length) {
    boxR.innerHTML = '<p class="empty-msg">Nenhuma região cadastrada. <a href="' + BASE_URL + '/app/regioes.php" style="color:var(--azul-principal);">Cadastrar</a></p>';
  } else {
    boxR.innerHTML = data.regioes.map(r => {
      const valor = r.municipio ? `${r.uf}|${r.municipio}` : r.uf;
      const label = r.municipio ? `${r.uf} — ${r.municipio}` : `${r.uf} (todo o estado)`;
      return `<button type="button" class="chip-filtro" data-tipo="regiao" data-valor="${escaparHTML(valor)}">
        ${escaparHTML(label)}
      </button>`;
    }).join('');
  }

  // Listeners de chip
  document.querySelectorAll('.chip-filtro').forEach(chip => {
    chip.addEventListener('click', () => {
      const tipo  = chip.dataset.tipo;
      const valor = chip.dataset.valor;

      if (tipo === 'palavra') {
        if (selecaoPalavras.has(valor)) {
          selecaoPalavras.delete(valor);
          chip.classList.remove('active');
        } else {
          selecaoPalavras.add(valor);
          chip.classList.add('active');
        }
      } else {
        if (selecaoRegioes.has(valor)) {
          selecaoRegioes.delete(valor);
          chip.classList.remove('active');
        } else {
          selecaoRegioes.add(valor);
          chip.classList.add('active');
        }
      }

      atualizarResumoInteresses();
      carregar(1);
    });
  });
}

function atualizarResumoInteresses() {
  const resumo = document.getElementById('ifbResumo');
  const total = selecaoPalavras.size + selecaoRegioes.size;
  if (total === 0) { resumo.style.display = 'none'; return; }

  resumo.style.display = 'block';
  let txt = '<strong>Filtrando por:</strong> ';
  const partes = [];
  if (selecaoPalavras.size) partes.push(`${selecaoPalavras.size} palavra${selecaoPalavras.size > 1 ? 's' : ''}`);
  if (selecaoRegioes.size)  partes.push(`${selecaoRegioes.size} região${selecaoRegioes.size > 1 ? 'ões' : ''}`);
  txt += partes.join(' + ');

  if (selecaoPalavras.size && selecaoRegioes.size) {
    txt += ' <span class="ifb-hint">(palavras E regiões serão cruzadas)</span>';
  }

  resumo.innerHTML = txt;
}

function limparSelecaoInteresses() {
  selecaoPalavras.clear();
  selecaoRegioes.clear();
  document.querySelectorAll('.chip-filtro').forEach(c => c.classList.remove('active'));
  atualizarResumoInteresses();
  carregar(1);
}


/* ---------- CARREGAR ---------- */
async function carregar(pagina = 1) {
  paginaAtual = pagina;
  lista.innerHTML = '<p class="empty-msg">Carregando...</p>';

  const params = new URLSearchParams({
    action: 'listar',
    busca:  filtroBusca.value.trim(),
    uf:     filtroUf.value,
    data:   filtroData.value,
    ordem:  filtroOrdem.value,
    palavras: Array.from(selecaoPalavras).join(','),
    regioes:  Array.from(selecaoRegioes).join(','),
    pagina: pagina,
  });

  const res = await fetch(`${API}?${params}`);
  const data = await res.json();

  if (!data.items.length) {
    lista.innerHTML = `
      <div class="empty-state">
        <p>Nenhuma licitação encontrada com esses filtros.</p>
      </div>`;
    contador.textContent = '0';
    paginacao.innerHTML = '';
    return;
  }

  contador.textContent = data.total;

  lista.innerHTML = data.items.map(l => {
    const statusTexto = (l.situacao_pncp ?? l.status ?? 'ABERTA').toUpperCase();
    const statusCls   = statusTexto.includes('SUSPENS') ? 'status-amarelo'
                       : statusTexto.includes('REVOG') || statusTexto.includes('ANULAD') ? 'status-vermelho'
                       : 'status-verde';

    const localidade = l.localidade || [l.municipio, l.uf].filter(Boolean).join(' — ') || '—';
    const encerra    = diasRestantes(l.fim_propostas);
    const encerraCls = encerra?.encerrado ? 'encerrado' : '';

    // Destaque de match
    const matchCls = l.match ? 'licitacao-card-edital match' : 'licitacao-card-edital';

    const tagMatch = l.match ? `
      <div class="lc-match">
        <span class="lc-match-tag">✓ DE ACORDO COM SEUS INTERESSES</span>
        ${l.match_palavras.length ? `
          <span class="lc-match-detalhe">
            Palavras: <strong>${l.match_palavras.map(p => escaparHTML(p)).join(', ')}</strong>
          </span>` : ''}
        ${l.match_regiao ? `<span class="lc-match-detalhe regiao">📍 Região de interesse</span>` : ''}
      </div>
    ` : '';

    return `
      <div class="${matchCls} ${l.id_interesse ? 'marcada' : ''}">

        <div class="lc-top">
          <span class="lc-status ${statusCls}">${escaparHTML(statusTexto)}</span>
          ${l.id_interesse ? '<span class="lc-badge-interesse">★ Interesse</span>' : ''}
        </div>

        <h3 class="lc-titulo">${escaparHTML(l.numero_licitacao ?? 'Edital')}</h3>

        ${tagMatch}

        <div class="lc-info-grid">
          <div class="lc-info">
            <span class="lc-info-label">CIDADE</span>
            <span class="lc-info-value">${escaparHTML(localidade)}</span>
          </div>
          <div class="lc-info">
            <span class="lc-info-label">ÓRGÃO</span>
            <span class="lc-info-value">${escaparHTML(truncar(l.orgao ?? '—', 40))}</span>
          </div>
          <div class="lc-info">
            <span class="lc-info-label">VALOR ESTIMADO</span>
            <span class="lc-info-value">${formatarValor(l.valor_estimado)}</span>
          </div>
          <div class="lc-info lc-info-data ${encerraCls}">
            <span class="lc-info-label">ABERTURA</span>
            <span class="lc-info-value">${formatarDataHora(l.fim_propostas ?? l.data_abertura)}</span>
            ${encerra ? `<span class="lc-info-hint">${encerra.texto}</span>` : ''}
          </div>
        </div>

        <div class="lc-objeto-wrap">
          <span class="lc-info-label">OBJETO</span>
          <p class="lc-objeto-texto">${escaparHTML(truncar(l.objeto ?? 'Sem descrição', 320))}</p>
        </div>

        ${l.autores && l.autores.length
          ? `<div class="lc-autores">⭐ Interesse marcado por <strong>${l.autores.map(a => escaparHTML(a)).join(', ')}</strong></div>`
          : ''}

        <div class="lc-botoes">
          <button class="btn-edital-primary" onclick="abrirEdital(${l.id})">Acessar edital</button>
          ${l.id_interesse
            ? `<button class="btn-edital-secondary marcado" onclick="desmarcar(${l.id})">★ Salvo na lista</button>`
            : `<button class="btn-edital-secondary" onclick="marcar(${l.id})">Salvar na lista</button>`
          }
        </div>

      </div>
    `;
  }).join('');

  montarPaginacao(data.pagina, data.paginas);
}

function montarPaginacao(atual, total) {
  if (total <= 1) { paginacao.innerHTML = ''; return; }
  let html = '';
  if (atual > 1) html += `<button class="pg-btn" onclick="carregar(${atual - 1})">‹ Anterior</button>`;
  const inicio = Math.max(1, atual - 2);
  const fim = Math.min(total, atual + 2);
  for (let i = inicio; i <= fim; i++) {
    html += `<button class="pg-btn ${i === atual ? 'active' : ''}" onclick="carregar(${i})">${i}</button>`;
  }
  if (atual < total) html += `<button class="pg-btn" onclick="carregar(${atual + 1})">Próxima ›</button>`;
  paginacao.innerHTML = html;
}

async function marcar(id) {
  const fd = new FormData();
  fd.append('id_licitacao', id);
  const res = await fetch(`${API}?action=marcar`, { method: 'POST', body: fd });
  const data = await res.json();
  if (data.success) carregar(paginaAtual);
}

async function desmarcar(id) {
  const fd = new FormData();
  fd.append('id_licitacao', id);
  const res = await fetch(`${API}?action=desmarcar`, { method: 'POST', body: fd });
  const data = await res.json();
  if (data.success) carregar(paginaAtual);
}

/* ---------- MODAL ---------- */
async function abrirEdital(id) {
  const res = await fetch(`${API}?action=detalhes&id=${id}`);
  const data = await res.json();
  if (!data.success) return;

  const l = data.licitacao;
  const statusTexto = (l.situacao_pncp ?? l.status ?? 'ABERTA').toUpperCase();
  const statusCls   = statusTexto.includes('SUSPENS') ? 'status-amarelo'
                     : statusTexto.includes('REVOG') || statusTexto.includes('ANULAD') ? 'status-vermelho'
                     : 'status-verde';

  const localidade = l.localidade || [l.municipio, l.uf].filter(Boolean).join(' — ') || '—';
  const encerra = diasRestantes(l.fim_propostas);

  const matchBox = l.match ? `
    <div class="modal-match-box">
      <span class="lc-match-tag">✓ DE ACORDO COM SEUS INTERESSES</span>
      ${l.match_palavras.length ? `
        <p>Palavras encontradas: <strong>${l.match_palavras.map(p => escaparHTML(p)).join(', ')}</strong></p>
      ` : ''}
      ${l.match_regiao ? `<p>📍 A licitação é da sua região de interesse.</p>` : ''}
    </div>
  ` : '';

  const docs = (l.documentos || []).length
    ? `<div class="modal-secao">
         <h4 class="modal-secao-titulo">Documentos anexos</h4>
         <ul class="docs-list">
           ${l.documentos.map(d => `
             <li><a href="${escaparHTML(d.caminho_arquivo || d.url_origem || '#')}" target="_blank">
               📄 ${escaparHTML(d.nome_arquivo ?? 'Documento')}</a></li>
           `).join('')}
         </ul>
       </div>`
    : '';

  const autores = (l.autores || []).length
    ? `<div class="modal-secao">
         <h4 class="modal-secao-titulo">Interesse da equipe</h4>
         <ul class="docs-list">
           ${l.autores.map(a => `
             <li>⭐ <strong>${escaparHTML(a.nome)}</strong>
               <span class="cinza" style="font-size:12.5px;">— ${formatarDataCurta(a.data_marcacao)}</span>
             </li>
           `).join('')}
         </ul>
       </div>`
    : '';

  document.getElementById('modalLicitacaoBody').innerHTML = `
    <div class="modal-edital-header">
      <span class="lc-status ${statusCls}">${escaparHTML(statusTexto)}</span>
      <h2 class="modal-edital-titulo">${escaparHTML(l.numero_licitacao ?? 'Edital')}</h2>
      <p class="modal-edital-sub">${escaparHTML(l.id_contratacao_pncp ?? '')}</p>
    </div>

    ${matchBox}

    <div class="modal-edital-grid">
      <div class="modal-info-box"><span class="lc-info-label">CIDADE</span><span class="lc-info-value">${escaparHTML(localidade)}</span></div>
      <div class="modal-info-box"><span class="lc-info-label">ÓRGÃO</span><span class="lc-info-value">${escaparHTML(l.orgao ?? '—')}</span></div>
      <div class="modal-info-box"><span class="lc-info-label">UNIDADE</span><span class="lc-info-value">${escaparHTML(l.unidade ?? '—')}</span></div>
      <div class="modal-info-box destaque">
        <span class="lc-info-label">ABERTURA DAS PROPOSTAS</span>
        <span class="lc-info-value">${formatarDataHora(l.fim_propostas ?? l.data_abertura)}</span>
        ${encerra ? `<span class="lc-info-hint ${encerra.encerrado ? 'encerrado' : ''}">${encerra.texto}</span>` : ''}
      </div>
      <div class="modal-info-box"><span class="lc-info-label">INÍCIO DAS PROPOSTAS</span><span class="lc-info-value">${formatarDataHora(l.inicio_propostas)}</span></div>
      <div class="modal-info-box"><span class="lc-info-label">MODALIDADE</span><span class="lc-info-value">${escaparHTML(l.modalidade ?? '—')}</span></div>
      <div class="modal-info-box"><span class="lc-info-label">MODO DE DISPUTA</span><span class="lc-info-value">${escaparHTML(l.modo_disputa ?? '—')}</span></div>
      <div class="modal-info-box destaque-valor"><span class="lc-info-label">VALOR ESTIMADO</span><span class="lc-info-value">${formatarValor(l.valor_estimado)}</span></div>
      <div class="modal-info-box"><span class="lc-info-label">VALOR HOMOLOGADO</span><span class="lc-info-value">${formatarValor(l.valor_homologado)}</span></div>
      <div class="modal-info-box"><span class="lc-info-label">SRP</span><span class="lc-info-value">${l.srp == 1 ? 'Sim' : 'Não'}</span></div>
      <div class="modal-info-box"><span class="lc-info-label">AMPARO LEGAL</span><span class="lc-info-value">${escaparHTML(l.amparo_legal ?? '—')}</span></div>
      <div class="modal-info-box"><span class="lc-info-label">PLATAFORMA</span><span class="lc-info-value">${escaparHTML(l.plataforma ?? '—')}</span></div>
      <div class="modal-info-box"><span class="lc-info-label">FONTE ORÇAMENTÁRIA</span><span class="lc-info-value">${escaparHTML(l.fonte_orcamentaria ?? '—')}</span></div>
      <div class="modal-info-box"><span class="lc-info-label">DATA PUBLICAÇÃO</span><span class="lc-info-value">${formatarDataCurta(l.data_publicacao)}</span></div>
    </div>

    <div class="modal-secao">
      <h4 class="modal-secao-titulo">Objeto</h4>
      <p class="modal-objeto">${escaparHTML(l.objeto ?? 'Sem descrição')}</p>
    </div>

    ${docs}
    ${autores}

    <div class="modal-edital-acoes">
      ${l.link_detalhes ? `<a href="https://pncp.gov.br${escaparHTML(l.link_detalhes)}" target="_blank" class="btn-edital-primary">Abrir no PNCP</a>` : ''}
      ${l.id_interesse
        ? `<button class="btn-edital-secondary marcado" onclick="desmarcar(${l.id}); fecharModalLicitacao();">★ Salvo na lista</button>`
        : `<button class="btn-edital-secondary" onclick="marcar(${l.id}); fecharModalLicitacao();">Salvar na lista</button>`
      }
      <button class="btn-edital-ghost" onclick="fecharModalLicitacao()">Fechar</button>
    </div>
  `;

  document.getElementById('modalLicitacao').classList.add('active');
}

function fecharModalLicitacao() {
  document.getElementById('modalLicitacao').classList.remove('active');
}

formFiltros.addEventListener('submit', (e) => { e.preventDefault(); carregar(1); });

function limparFiltros() {
  filtroBusca.value = '';
  filtroUf.value = '';
  filtroData.value = '';
  filtroOrdem.value = 'recentes';
  selecaoPalavras.clear();
  selecaoRegioes.clear();
  document.querySelectorAll('.chip-filtro').forEach(c => c.classList.remove('active'));
  atualizarResumoInteresses();
  carregar(1);
}

document.getElementById('btnLimparInteresses').addEventListener('click', limparSelecaoInteresses);

carregarInteressesDisponiveis();
carregar(1);
const API = BASE_URL + '/api/admin/licitacoes.php';

const tbody          = document.getElementById('tbodyLicitacoes');
const contador       = document.getElementById('contadorLicitacoes');
const paginacao      = document.getElementById('paginacao');
const filtroBusca    = document.getElementById('filtroBusca');
const filtroUf       = document.getElementById('filtroUf');
const filtroSituacao = document.getElementById('filtroSituacao');
const filtroModalidade = document.getElementById('filtroModalidade');

const UFS = ['AC','AL','AP','AM','BA','CE','DF','ES','GO','MA','MT','MS','MG','PA','PB','PR','PE','PI','RJ','RN','RS','RO','RR','SC','SP','SE','TO'];
UFS.forEach(uf => {
  const o = document.createElement('option');
  o.value = uf; o.textContent = uf;
  filtroUf.appendChild(o);
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
function formatarDataHora(dt) {
  if (!dt) return '—';
  const d = new Date(dt.replace(' ', 'T'));
  if (isNaN(d)) return dt;
  return d.toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' });
}
function formatarDataCurta(dt) {
  if (!dt) return '—';
  const d = new Date(dt.replace(' ', 'T'));
  if (isNaN(d)) return dt;
  return d.toLocaleDateString('pt-BR');
}

const SITUACAO_CLS = {
  'Divulgada no PNCP': 'badge-azul',
  'Suspensa':          'badge-amarelo',
  'Revogada':          'badge-vermelho',
  'Anulada':           'badge-vermelho',
};

/* ---------- CARREGAR ---------- */
async function carregar(pagina = 1) {
  tbody.innerHTML = '<tr><td colspan="9" class="empty-msg">Carregando...</td></tr>';

  const params = new URLSearchParams({
    action:     'listar',
    busca:      filtroBusca.value.trim(),
    uf:         filtroUf.value,
    situacao:   filtroSituacao.value,
    modalidade: filtroModalidade.value,
    pagina:     pagina,
  });

  const res = await fetch(`${API}?${params}`);
  const data = await res.json();

  if (!data.items.length) {
    tbody.innerHTML = '<tr><td colspan="9" class="empty-msg">Nenhuma licitação encontrada.</td></tr>';
    contador.textContent = '0';
    paginacao.innerHTML = '';
    return;
  }

  contador.textContent = data.total;

  tbody.innerHTML = data.items.map(l => {
    const sitCls = SITUACAO_CLS[l.situacao_pncp] ?? 'badge-azul';
    const localidade = l.localidade ?? ((l.municipio ?? '') + (l.uf ? '/' + l.uf : ''));
    return `
      <tr>
        <td>
          <strong>${escaparHTML(l.numero_licitacao ?? '—')}</strong>
          <div class="cinza" style="font-size:12px;">${escaparHTML((l.id_contratacao_pncp ?? '').substring(0, 32))}</div>
        </td>
        <td style="max-width:200px;">${escaparHTML((l.orgao ?? '—').substring(0, 60))}</td>
        <td>${escaparHTML(localidade || '—')}</td>
        <td>${escaparHTML(l.modalidade ?? '—')}</td>
        <td><span class="badge ${sitCls}">${escaparHTML(l.situacao_pncp ?? l.status ?? '—')}</span></td>
        <td>${formatarDataCurta(l.inicio_propostas)}</td>
        <td>${formatarDataCurta(l.fim_propostas)}</td>
        <td>${formatarValor(l.valor_estimado)}</td>
        <td style="text-align:right;">
          <button class="btn-tabela" onclick="verDetalhes(${l.id})">Ver</button>
        </td>
      </tr>
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

/* ---------- MODAL DETALHES ---------- */
async function verDetalhes(id) {
  const res = await fetch(`${API}?action=detalhes&id=${id}`);
  const data = await res.json();
  if (!data.success) return;

  const l = data.licitacao;

  const docs = (l.documentos || []).length
    ? `<h4 style="margin-top:18px; font-size:14px;">Documentos</h4>
       <ul class="docs-list">
         ${l.documentos.map(d => `
           <li>
             <a href="${escaparHTML(d.caminho_arquivo || d.url_origem || '#')}" target="_blank">
               ${escaparHTML(d.nome_arquivo ?? 'Documento')}
             </a>
           </li>
         `).join('')}
       </ul>`
    : '';

  document.getElementById('modalLicitacaoBody').innerHTML = `
    <h2 style="font-size:20px; margin-bottom:6px;">${escaparHTML(l.numero_licitacao ?? '—')}</h2>
    <p class="modal-sub" style="font-size:13px;">
      ${escaparHTML(l.id_contratacao_pncp ?? '')}
    </p>

    <div class="detalhes-grid">
      <div><strong>Órgão</strong><span>${escaparHTML(l.orgao ?? '—')}</span></div>
      <div><strong>Unidade</strong><span>${escaparHTML(l.unidade ?? '—')}</span></div>
      <div><strong>Localidade</strong><span>${escaparHTML(l.localidade ?? '—')}</span></div>
      <div><strong>UF / Município</strong><span>${escaparHTML(l.uf ?? '—')} · ${escaparHTML(l.municipio ?? '—')}</span></div>
      <div><strong>Modalidade</strong><span>${escaparHTML(l.modalidade ?? '—')}</span></div>
      <div><strong>Modo de Disputa</strong><span>${escaparHTML(l.modo_disputa ?? '—')}</span></div>
      <div><strong>Situação</strong><span>${escaparHTML(l.situacao_pncp ?? '—')}</span></div>
      <div><strong>Amparo Legal</strong><span>${escaparHTML(l.amparo_legal ?? '—')}</span></div>
      <div><strong>SRP</strong><span>${l.srp == 1 ? 'Sim' : 'Não'}</span></div>
      <div><strong>Fonte Orçamentária</strong><span>${escaparHTML(l.fonte_orcamentaria ?? '—')}</span></div>
      <div><strong>Data Publicação</strong><span>${formatarDataCurta(l.data_publicacao)}</span></div>
      <div><strong>Início Propostas</strong><span>${formatarDataHora(l.inicio_propostas)}</span></div>
      <div><strong>Fim Propostas</strong><span>${formatarDataHora(l.fim_propostas)}</span></div>
      <div><strong>Data de Abertura</strong><span>${formatarDataHora(l.data_abertura)}</span></div>
      <div><strong>Valor Estimado</strong><span>${formatarValor(l.valor_estimado)}</span></div>
      <div><strong>Valor Homologado</strong><span>${formatarValor(l.valor_homologado)}</span></div>
      <div><strong>Plataforma</strong><span>${escaparHTML(l.plataforma ?? '—')}</span></div>
    </div>

    ${l.objeto ? `
      <div style="margin-top:16px;">
        <strong style="font-size:12px; color:#64748B; text-transform:uppercase; letter-spacing:.3px;">Objeto</strong>
        <p style="background:var(--cinza-claro); padding:14px; border-radius:8px; margin-top:6px; font-size:14px; line-height:1.6;">
          ${escaparHTML(l.objeto)}
        </p>
      </div>
    ` : ''}

    ${docs}

    <div class="form-actions" style="margin-top:20px; display:flex; justify-content:space-between; gap:10px; flex-wrap:wrap;">
      <button type="button" class="btn-remove-outline" onclick="excluirLicitacao(${l.id})">Excluir</button>
      <div style="display:flex; gap:10px;">
        ${l.link_detalhes ? `<a href="https://pncp.gov.br${escaparHTML(l.link_detalhes)}" target="_blank" class="btn btn-ghost">Abrir no PNCP</a>` : ''}  
        <button type="button" class="btn btn-primary" onclick="fecharModalLicitacao()">Fechar</button>
      </div>
    </div>
  `;

  document.getElementById('modalLicitacao').classList.add('active');
}

function fecharModalLicitacao() {
  document.getElementById('modalLicitacao').classList.remove('active');
}

async function excluirLicitacao(id) {
  if (!confirm('Excluir esta licitação? Esta ação não pode ser desfeita.')) return;
  const fd = new FormData();
  fd.append('id', id);
  await fetch(`${API}?action=excluir`, { method: 'POST', body: fd });
  fecharModalLicitacao();
  carregar();
}

function limparFiltros() {
  filtroBusca.value = '';
  filtroUf.value = '';
  filtroSituacao.value = '';
  filtroModalidade.value = '';
  carregar(1);
}

/* ---------- INIT ---------- */
carregar(1);
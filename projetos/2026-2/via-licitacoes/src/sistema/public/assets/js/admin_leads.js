const API = BASE_URL + '/api/admin/leads.php';

const tbody        = document.getElementById('tbodyLeads');
const contador     = document.getElementById('contadorLeads');
const paginacao    = document.getElementById('paginacao');
const filtroBusca  = document.getElementById('filtroBusca');
const filtroStatus = document.getElementById('filtroStatus');

const STATUS_LABELS = {
  'LEAD NOVO':      { txt: 'Lead Novo',      cls: 'badge-azul' },
  'EM NEGOCIACAO':  { txt: 'Em Negociação',  cls: 'badge-amarelo' },
  'CLIENTE ATIVO':  { txt: 'Cliente Ativo',  cls: 'badge-verde' },
  'DESISTENCIA':    { txt: 'Desistência',    cls: 'badge-vermelho' },
};

function formatarDataHora(dt) {
  if (!dt) return '—';
  const d = new Date(dt.replace(' ', 'T'));
  return d.toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' });
}
function escaparHTML(s) {
  if (s == null) return '';
  return String(s).replace(/[&<>"']/g, c => ({ '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;' }[c]));
}

/* ---------- RESUMO ---------- */
async function carregarResumo() {
  const res = await fetch(`${API}?action=resumo`);
  const data = await res.json();
  if (!data.success) return;

  document.getElementById('qtdLeadNovo').textContent      = data.resumo['LEAD NOVO']     ?? 0;
  document.getElementById('qtdEmNegociacao').textContent  = data.resumo['EM NEGOCIACAO'] ?? 0;
  document.getElementById('qtdClienteAtivo').textContent  = data.resumo['CLIENTE ATIVO'] ?? 0;
  document.getElementById('qtdDesistencia').textContent   = data.resumo['DESISTENCIA']   ?? 0;
}

/* ---------- LISTAGEM ---------- */
async function carregar(pagina = 1) {
  tbody.innerHTML = '<tr><td colspan="6" class="empty-msg">Carregando...</td></tr>';

  const params = new URLSearchParams({
    action: 'listar',
    busca:  filtroBusca.value.trim(),
    status: filtroStatus.value,
    pagina: pagina,
  });

  const res = await fetch(`${API}?${params}`);
  const data = await res.json();

  if (!data.items.length) {
    tbody.innerHTML = '<tr><td colspan="6" class="empty-msg">Nenhum lead encontrado.</td></tr>';
    contador.textContent = '0';
    paginacao.innerHTML = '';
    return;
  }

  contador.textContent = data.total;

  tbody.innerHTML = data.items.map(l => {
    const st = STATUS_LABELS[l.status_comercial] || { txt: l.status_comercial, cls: 'badge-azul' };
    return `
      <tr>
        <td><strong>${escaparHTML(l.nome)}</strong></td>
        <td>
          <div class="td-contato">
            <span>${escaparHTML(l.email)}</span>
            <span class="cinza">${escaparHTML(l.telefone ?? '')}</span>
          </div>
        </td>
        <td>${escaparHTML(l.cnpj ?? '—')}</td>
        <td>${formatarDataHora(l.data_envio)}</td>
        <td><span class="badge ${st.cls}">${st.txt}</span></td>
        <td style="text-align:right;">
          <button class="btn-tabela" onclick="abrirLead(${l.id})">Gerenciar</button>
        </td>
      </tr>`;
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

/* ---------- MODAL / GERENCIAR ---------- */
async function abrirLead(id) {
  const res = await fetch(`${API}?action=detalhes&id=${id}`);
  const data = await res.json();
  if (!data.success) return;

  const l = data.lead;
  const statusOpts = Object.entries(STATUS_LABELS).map(([k, v]) =>
    `<option value="${k}" ${k === l.status_comercial ? 'selected' : ''}>${v.txt}</option>`
  ).join('');

  document.getElementById('modalLeadBody').innerHTML = `
    <h2>Lead: ${escaparHTML(l.nome)}</h2>
    <p class="modal-sub">Recebido em ${formatarDataHora(l.data_envio)}</p>

    <div class="detalhes-grid">
      <div><strong>E-mail</strong><span>${escaparHTML(l.email)}</span></div>
      <div><strong>Telefone</strong><span>${escaparHTML(l.telefone ?? '—')}</span></div>
      <div><strong>CNPJ</strong><span>${escaparHTML(l.cnpj ?? '—')}</span></div>
      <div><strong>Última atualização</strong><span>${formatarDataHora(l.data_atualizacao)}</span></div>
    </div>

    <form id="formAtualizarLead" class="form-grid" style="margin-top:20px;">
      <input type="hidden" name="id" value="${l.id}">
      <div class="form-group">
        <label>Status comercial</label>
        <select name="status_comercial">${statusOpts}</select>
      </div>
      <div class="form-group" style="grid-column: 1 / -1;">
        <label>Observação interna</label>
        <textarea name="observacao" rows="4" placeholder="Anotações sobre o contato...">${escaparHTML(l.observacao ?? '')}</textarea>
      </div>
      <div class="form-actions" style="grid-column: 1 / -1; display:flex; justify-content:space-between; gap:10px; flex-wrap:wrap;">
        <div style="display:flex; gap:10px; flex-wrap:wrap;">
          <button type="button" class="btn-remove-outline" onclick="excluirLead(${l.id})">Excluir lead</button>
          <button type="button" class="btn-converter" onclick="converterLead(${l.id})">→ Converter em usuário</button>
        </div>
        <div style="display:flex; gap:10px;">
          <button type="button" class="btn btn-ghost" onclick="fecharModalLead()">Cancelar</button>
          <button type="submit" class="btn btn-primary">Salvar</button>
        </div>
      </div>
      <div id="feedbackLead" class="form-feedback" style="grid-column:1/-1;"></div>
    </form>
  `;

  document.getElementById('modalLead').classList.add('active');

  document.getElementById('formAtualizarLead').addEventListener('submit', async (e) => {
    e.preventDefault();
    const fb = document.getElementById('feedbackLead');
    fb.textContent = 'Salvando...';
    fb.className = 'form-feedback';

    const res = await fetch(`${API}?action=atualizar`, { method: 'POST', body: new FormData(e.target) });

    const data = await res.json();

    fb.textContent = data.message;
    fb.className = 'form-feedback ' + (data.success ? 'ok' : 'erro');

    if (data.success) {
      carregarResumo();
      carregar();
      setTimeout(fecharModalLead, 800);
    }
  });
}

function fecharModalLead() {
  document.getElementById('modalLead').classList.remove('active');
}

async function excluirLead(id) {
  if (!confirm('Tem certeza que deseja excluir este lead?')) return;
  const fd = new FormData(); fd.append('id', id);
  await fetch(`${API}?action=excluir`, { method: 'POST', body: fd });
  fecharModalLead();
  carregarResumo();
  carregar();
}

function limparFiltros() {
  filtroBusca.value = '';
  filtroStatus.value = '';
  carregar(1);
}

async function converterLead(id) {
  const criarEmpresa = confirm(
    'Converter este lead em usuário?\n\n' +
    'OK = Criar uma NOVA empresa para este lead (recomendado se ele é um cliente novo).\n' +
    'Cancelar = Criar usuário SEM empresa vinculada.'
  );

  const fd = new FormData();
  fd.append('id_lead', id);
  if (criarEmpresa) fd.append('criar_empresa', '1');

  const res = await fetch(BASE_URL + '/api/admin/usuarios.php?action=converter_lead', { method: 'POST', body: fd });
  const data = await res.json();

  if (data.success) {
    document.getElementById('modalLeadBody').innerHTML = `
      <h2>✅ Lead convertido com sucesso!</h2>
      <p class="modal-sub">
        O usuário foi criado ${data.empresa_criada ? 'e uma empresa provisória foi vinculada (o cliente deverá completar os dados no primeiro acesso).' : 'sem empresa vinculada.'}
      </p>
      <div class="feedback-senha">
        <strong>Senha temporária gerada:</strong>
        <div class="senha-box">
          <code>${data.senha_temporaria}</code>
          <button type="button" class="btn-copiar" onclick="navigator.clipboard.writeText('${data.senha_temporaria}')">Copiar</button>
        </div>
        <small>⚠️ Envie esta senha ao cliente e peça para ele alterar no primeiro acesso.</small>
      </div>
      <div class="form-actions" style="margin-top:20px; display:flex; justify-content:flex-end;">
        <button type="button" class="btn btn-primary" onclick="fecharModalLead(); carregar(); carregarResumo();">Fechar</button>
      </div>
    `;
  } else {
    alert('Erro: ' + data.message);
  }
}

/* ---------- INIT ---------- */
carregarResumo();
carregar(1);
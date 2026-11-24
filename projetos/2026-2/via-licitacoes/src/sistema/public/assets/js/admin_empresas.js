const API = BASE_URL + '/api/admin/empresas.php';

const tbody       = document.getElementById('tbodyEmpresas');
const contador    = document.getElementById('contadorEmpresas');
const paginacao   = document.getElementById('paginacao');
const filtroBusca = document.getElementById('filtroBusca');
const filtroUf    = document.getElementById('filtroUf');

const UFS = ['AC','AL','AP','AM','BA','CE','DF','ES','GO','MA','MT','MS','MG','PA','PB','PR','PE','PI','RJ','RN','RS','RO','RR','SC','SP','SE','TO'];
UFS.forEach(uf => {
  const opt = document.createElement('option');
  opt.value = uf; opt.textContent = uf;
  filtroUf.appendChild(opt);
});

function escaparHTML(s) {
  if (s == null) return '';
  return String(s).replace(/[&<>"']/g, c => ({ '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;' }[c]));
}

async function carregar(pagina = 1) {
  tbody.innerHTML = '<tr><td colspan="5" class="empty-msg">Carregando...</td></tr>';

  const params = new URLSearchParams({
    action: 'listar',
    busca:  filtroBusca.value.trim(),
    uf:     filtroUf.value,
    pagina: pagina,
  });

  const res = await fetch(`${API}?${params}`);
  const data = await res.json();

  if (!data.items.length) {
    tbody.innerHTML = '<tr><td colspan="5" class="empty-msg">Nenhuma empresa cadastrada.</td></tr>';
    contador.textContent = '0';
    paginacao.innerHTML = '';
    return;
  }

  contador.textContent = data.total;

    tbody.innerHTML = data.items.map(e => `
    <tr>
        <td>
        <strong>${escaparHTML(e.razao_social)}</strong>
        ${e.nome_fantasia ? `<div class="cinza" style="font-size:12.5px;">${escaparHTML(e.nome_fantasia)}</div>` : ''}
        </td>
        <td>${escaparHTML(e.cnpj)}</td>
        <td>
        <div class="td-contato">
            <span>${escaparHTML(e.responsavel ?? '—')}</span>
            <span class="cinza">${escaparHTML(e.email_responsavel ?? '')}</span>
        </div>
        </td>
        <td>
        <span class="badge badge-azul">${e.qtd_usuarios} usuário${e.qtd_usuarios > 1 ? 's' : ''}</span>
        </td>
        <td>${escaparHTML(e.uf ?? '—')} · ${escaparHTML(e.municipio ?? '—')}</td>
        <td style="text-align:right;">
        <button class="btn-tabela" onclick="abrirEmpresa(${e.id})">Ver detalhes</button>
        </td>
    </tr>
    `).join('');

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

async function abrirEmpresa(id) {
  const res = await fetch(`${API}?action=detalhes&id=${id}`);
  const data = await res.json();
  if (!data.success) return;

  const e = data.empresa;
  document.getElementById('modalEmpresaBody').innerHTML = `
    <h2>${escaparHTML(e.razao_social)}</h2>
    <p class="modal-sub">${e.nome_fantasia ? escaparHTML(e.nome_fantasia) : 'Sem nome fantasia'}</p>

    <div class="detalhes-grid">
      <div><strong>CNPJ</strong><span>${escaparHTML(e.cnpj)}</span></div>
      <div><strong>Responsável</strong><span>${escaparHTML(e.responsavel)}</span></div>
      <div><strong>E-mail do responsável</strong><span>${escaparHTML(e.email_responsavel)}</span></div>
      <div><strong>Telefone</strong><span>${escaparHTML(e.telefone ?? '—')}</span></div>
      <div><strong>E-mail de contato</strong><span>${escaparHTML(e.email_contato ?? '—')}</span></div>
      <div><strong>Localização</strong><span>${escaparHTML(e.uf ?? '—')} · ${escaparHTML(e.municipio ?? '—')}</span></div>
      <div style="grid-column: 1 / -1;"><strong>Endereço</strong><span>${escaparHTML(e.endereco ?? '—')}</span></div>
    </div>
    <div style="margin-top:20px;">
      <h3 style="font-size:16px; margin-bottom:10px;">Usuários vinculados (${e.qtd_usuarios})</h3>
      <div class="list-box">
        ${e.usuarios.map(u => `
          <div class="list-item">
            <div>
              <strong>${escaparHTML(u.nome)}</strong>
              <span>${escaparHTML(u.email)} · ${u.tipo_usuario} · ${u.status}</span>
            </div>
          </div>
        `).join('') || '<p class="empty-msg">Nenhum usuário vinculado.</p>'}
      </div>
    </div>


    <div class="form-actions" style="display:flex; justify-content:space-between; gap:10px; flex-wrap:wrap;">
      <button type="button" class="btn btn-remove-outline" onclick="excluirEmpresa(${e.id})">Excluir empresa</button>
      <button type="button" class="btn btn-ghost" onclick="fecharModalEmpresa()">Fechar</button>
    </div>
  `;
  document.getElementById('modalEmpresa').classList.add('active');
}

function fecharModalEmpresa() {
  document.getElementById('modalEmpresa').classList.remove('active');
}

async function excluirEmpresa(id) {
  if (!confirm('Tem certeza que deseja excluir esta empresa?')) return;
  const fd = new FormData(); fd.append('id', id);
  await fetch(`${API}?action=excluir`, { method: 'POST', body: fd });
  fecharModalEmpresa();
  carregar();
}

function limparFiltros() {
  filtroBusca.value = '';
  filtroUf.value = '';
  carregar(1);
}

carregar(1);
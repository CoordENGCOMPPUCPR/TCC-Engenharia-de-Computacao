const API = BASE_URL + '/api/admin/usuarios.php';

const tbody        = document.getElementById('tbodyUsuarios');
const contador     = document.getElementById('contadorUsuarios');
const paginacao    = document.getElementById('paginacao');
const filtroBusca  = document.getElementById('filtroBusca');
const filtroTipo   = document.getElementById('filtroTipo');
const filtroStatus = document.getElementById('filtroStatus');

const TIPO_CLS   = { 'admin': 'badge-roxo', 'comum': 'badge-azul' };
const STATUS_CLS = { 'ativo': 'badge-verde', 'inativo': 'badge-vermelho', 'pendente': 'badge-amarelo' };

function escaparHTML(s) {
  if (s == null) return '';
  return String(s).replace(/[&<>"']/g, c => ({ '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;' }[c]));
}
function formatarDataHora(dt) {
  if (!dt) return '—';
  const d = new Date(dt.replace(' ', 'T'));
  return d.toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' });
}

/* ---------- LISTAR ---------- */
async function carregar(pagina = 1) {
  tbody.innerHTML = '<tr><td colspan="7" class="empty-msg">Carregando...</td></tr>';

  const params = new URLSearchParams({
    action: 'listar',
    busca:  filtroBusca.value.trim(),
    tipo:   filtroTipo.value,
    status: filtroStatus.value,
    pagina: pagina,
  });

  const res = await fetch(`${API}?${params}`);
  const data = await res.json();

  if (!data.items.length) {
    tbody.innerHTML = '<tr><td colspan="7" class="empty-msg">Nenhum usuário encontrado.</td></tr>';
    contador.textContent = '0';
    paginacao.innerHTML = '';
    return;
  }

  contador.textContent = data.total;

  tbody.innerHTML = data.items.map(u => `
    <tr>
      <td><strong>${escaparHTML(u.nome)}</strong></td>
      <td>${escaparHTML(u.email)}</td>
      <td><span class="badge ${TIPO_CLS[u.tipo_usuario] ?? 'badge-azul'}">${u.tipo_usuario}</span></td>
      <td><span class="badge ${STATUS_CLS[u.status] ?? 'badge-azul'}">${u.status}</span></td>
      <td>${u.empresa_nome ? escaparHTML(u.empresa_nome) : '<span class="cinza">—</span>'}</td>
      <td>${formatarDataHora(u.ultimo_acesso)}</td>
      <td style="text-align:right;">
        <button class="btn-tabela" onclick="abrirUsuario(${u.id})">Gerenciar</button>
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

/* ---------- MODAL: NOVO USUÁRIO ---------- */
async function abrirModalNovoUsuario() {
  // Carrega empresas disponíveis
  const resEmp = await fetch(`${API}?action=empresas_disponiveis`);
  const dataEmp = await resEmp.json();
  const empresas = dataEmp.items || [];

  const opcoes = empresas.map(e =>
    `<option value="${e.id}">${e.razao_social} — ${e.cnpj}</option>`
  ).join('');

  document.getElementById('modalUsuarioBody').innerHTML = `
    <h2>Novo usuário</h2>
    <p class="modal-sub">Crie um acesso. Você pode vinculá-lo a uma empresa existente ou deixar sem vínculo.</p>

    <form id="formNovoUsuario" class="form-grid">
      <div class="form-group">
        <label>Nome completo *</label>
        <input type="text" name="nome" required maxlength="150">
      </div>
      <div class="form-group">
        <label>E-mail *</label>
        <input type="email" name="email" required maxlength="150">
      </div>
      <div class="form-group">
        <label>Telefone</label>
        <input type="text" name="telefone" maxlength="20">
      </div>
      <div class="form-group">
        <label>Senha inicial * (mín. 6 caracteres)</label>
        <input type="text" name="senha" required minlength="6" placeholder="Ficará visível para copiar">
      </div>
      <div class="form-group">
        <label>Tipo</label>
        <select name="tipo_usuario">
          <option value="comum">Comum</option>
          <option value="admin">Admin</option>
        </select>
      </div>
      <div class="form-group">
        <label>Status</label>
        <select name="status">
          <option value="ativo">Ativo</option>
          <option value="inativo">Inativo</option>
          <option value="pendente">Pendente</option>
        </select>
      </div>

      <div class="form-group" style="grid-column:1/-1;">
        <label>Vincular a uma empresa</label>
        <select name="id_empresa" id="selectEmpresa">
          <option value="">— Nenhuma empresa (ex: admin global) —</option>
          ${opcoes}
          <option value="__NOVA__">+ Criar nova empresa para este usuário</option>
        </select>
      </div>

      <div id="boxNovaEmpresa" style="grid-column:1/-1; display:none;">
        <div class="form-grid" style="grid-template-columns: 2fr 1fr; gap:14px;">
          <div class="form-group">
            <label>Razão social da nova empresa *</label>
            <input type="text" name="nova_empresa_razao" maxlength="200">
          </div>
          <div class="form-group">
            <label>CNPJ *</label>
            <input type="text" name="nova_empresa_cnpj" maxlength="18" placeholder="00.000.000/0000-00">
          </div>
        </div>
      </div>

      <div class="form-actions" style="grid-column:1/-1; display:flex; justify-content:flex-end; gap:10px;">
        <button type="button" class="btn btn-ghost" onclick="fecharModalUsuario()">Cancelar</button>
        <button type="submit" class="btn btn-primary">Criar usuário</button>
      </div>
      <div id="feedbackUsuario" class="form-feedback" style="grid-column:1/-1;"></div>
    </form>
  `;
  document.getElementById('modalUsuario').classList.add('active');

  // Mostra/esconde bloco de nova empresa
  document.getElementById('selectEmpresa').addEventListener('change', (e) => {
    document.getElementById('boxNovaEmpresa').style.display =
      e.target.value === '__NOVA__' ? 'block' : 'none';
    if (e.target.value === '__NOVA__') e.target.removeAttribute('name');
    else e.target.setAttribute('name', 'id_empresa');
  });

  // Máscara CNPJ
  document.querySelector('input[name="nova_empresa_cnpj"]')?.addEventListener('input', (ev) => {
    let v = ev.target.value.replace(/\D/g, '').slice(0, 14);
    v = v.replace(/^(\d{2})(\d)/, '$1.$2')
         .replace(/^(\d{2})\.(\d{3})(\d)/, '$1.$2.$3')
         .replace(/\.(\d{3})(\d)/, '.$1/$2')
         .replace(/(\d{4})(\d)/, '$1-$2');
    ev.target.value = v;
  });

  document.getElementById('formNovoUsuario').addEventListener('submit', async (e) => {
    e.preventDefault();
    const fb = document.getElementById('feedbackUsuario');
    fb.textContent = 'Criando...';
    fb.className = 'form-feedback';

    const res = await fetch(`${API}?action=criar`, { method: 'POST', body: new FormData(e.target) });
    const data = await res.json();

    fb.textContent = data.message;
    fb.className = 'form-feedback ' + (data.success ? 'ok' : 'erro');

    if (data.success) {
      carregar();
      setTimeout(fecharModalUsuario, 900);
    }
  });
}


/* ---------- MODAL: GERENCIAR USUÁRIO ---------- */
async function abrirUsuario(id) {
  const res = await fetch(`${API}?action=detalhes&id=${id}`);
  const data = await res.json();
  if (!data.success) return;
  const u = data.usuario;

  // Carrega empresas disponíveis
  const resEmp = await fetch(`${API}?action=empresas_disponiveis`);
  const dataEmp = await resEmp.json();
  const empresas = dataEmp.items || [];

  const opcoes = empresas.map(e =>
    `<option value="${e.id}" ${u.id_empresa == e.id ? 'selected' : ''}>${e.razao_social} — ${e.cnpj}</option>`
  ).join('');

  document.getElementById('modalUsuarioBody').innerHTML = `
    <h2>${escaparHTML(u.nome)}</h2>
    <p class="modal-sub">Cadastrado em ${formatarDataHora(u.data_cadastro)} · Último acesso ${formatarDataHora(u.ultimo_acesso)}</p>

    <form id="formEditarUsuario" class="form-grid">
      <input type="hidden" name="id" value="${u.id}">
      <div class="form-group">
        <label>Nome *</label>
        <input type="text" name="nome" required maxlength="150" value="${escaparHTML(u.nome)}">
      </div>
      <div class="form-group">
        <label>E-mail *</label>
        <input type="email" name="email" required maxlength="150" value="${escaparHTML(u.email)}">
      </div>
      <div class="form-group">
        <label>Telefone</label>
        <input type="text" name="telefone" maxlength="20" value="${escaparHTML(u.telefone ?? '')}">
      </div>
      <div class="form-group">
        <label>Tipo</label>
        <select name="tipo_usuario">
          <option value="comum" ${u.tipo_usuario === 'comum' ? 'selected' : ''}>Comum</option>
          <option value="admin" ${u.tipo_usuario === 'admin' ? 'selected' : ''}>Admin</option>
        </select>
      </div>
      <div class="form-group">
        <label>Status</label>
        <select name="status">
          <option value="ativo" ${u.status === 'ativo' ? 'selected' : ''}>Ativo</option>
          <option value="inativo" ${u.status === 'inativo' ? 'selected' : ''}>Inativo</option>
          <option value="pendente" ${u.status === 'pendente' ? 'selected' : ''}>Pendente</option>
        </select>
      </div>

      <div class="form-group" style="grid-column:1/-1;">
        <label>Empresa vinculada</label>
        <select name="id_empresa">
          <option value="">— Nenhuma empresa —</option>
          ${opcoes}
        </select>
      </div>

      <div class="form-actions" style="grid-column:1/-1; display:flex; justify-content:space-between; gap:10px; flex-wrap:wrap;">
        <div style="display:flex; gap:10px; flex-wrap:wrap;">
          <button type="button" class="btn-remove-outline" onclick="excluirUsuario(${u.id})">Excluir</button>
          <button type="button" class="btn-reset-senha" onclick="resetarSenha(${u.id})">🔑 Resetar senha</button>
        </div>
        <div style="display:flex; gap:10px;">
          <button type="button" class="btn btn-ghost" onclick="fecharModalUsuario()">Cancelar</button>
          <button type="submit" class="btn btn-primary">Salvar</button>
        </div>
      </div>
      <div id="feedbackUsuario" class="form-feedback" style="grid-column:1/-1;"></div>
      <div id="feedbackSenha" class="feedback-senha" style="grid-column:1/-1; display:none;"></div>
    </form>
  `;
  document.getElementById('modalUsuario').classList.add('active');

  document.getElementById('formEditarUsuario').addEventListener('submit', async (e) => {
    e.preventDefault();
    const fb = document.getElementById('feedbackUsuario');
    fb.textContent = 'Salvando...';
    fb.className = 'form-feedback';

    const res = await fetch(`${API}?action=atualizar`, { method: 'POST', body: new FormData(e.target) });
    const data = await res.json();

    fb.textContent = data.message;
    fb.className = 'form-feedback ' + (data.success ? 'ok' : 'erro');

    if (data.success) {
      carregar();
      setTimeout(fecharModalUsuario, 900);
    }
  });
}


function fecharModalUsuario() {
  document.getElementById('modalUsuario').classList.remove('active');
}

/* ---------- RESETAR SENHA ---------- */
async function resetarSenha(id) {
  if (!confirm('Gerar uma nova senha para este usuário? A senha atual deixará de funcionar.')) return;

  const fd = new FormData(); fd.append('id', id);
  const res = await fetch(`${API}?action=resetar_senha`, { method: 'POST', body: fd });
  const data = await res.json();

  const box = document.getElementById('feedbackSenha');
  if (data.success) {
    box.style.display = 'block';
    box.innerHTML = `
      <strong>Nova senha gerada:</strong>
      <div class="senha-box">
        <code id="senhaGerada">${data.nova_senha}</code>
        <button type="button" class="btn-copiar" onclick="copiarSenha('${data.nova_senha}')">Copiar</button>
      </div>
      <small>⚠️ Anote esta senha. Ela não será mostrada novamente.</small>
    `;
  } else {
    box.style.display = 'block';
    box.innerHTML = `<span style="color:var(--erro);">${data.message}</span>`;
  }
}

function copiarSenha(senha) {
  navigator.clipboard.writeText(senha).then(() => {
    const btn = event.target;
    btn.textContent = '✓ Copiado';
    setTimeout(() => btn.textContent = 'Copiar', 1500);
  });
}

/* ---------- EXCLUIR ---------- */
async function excluirUsuario(id) {
  if (!confirm('Excluir este usuário? A empresa e os dados vinculados também serão removidos.')) return;
  const fd = new FormData(); fd.append('id', id);
  await fetch(`${API}?action=excluir`, { method: 'POST', body: fd });
  fecharModalUsuario();
  carregar();
}

function limparFiltros() {
  filtroBusca.value = '';
  filtroTipo.value = '';
  filtroStatus.value = '';
  carregar(1);
}

carregar(1);
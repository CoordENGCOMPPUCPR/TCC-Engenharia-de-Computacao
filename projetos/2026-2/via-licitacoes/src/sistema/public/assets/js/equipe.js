const API = BASE_URL + '/api/equipe.php';
const lista = document.getElementById('listaEquipe');
const contador = document.getElementById('contadorEquipe');
let EU = null;

function escaparHTML(s) {
  if (s == null) return '';
  return String(s).replace(/[&<>"']/g, c => ({ '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;' }[c]));
}
function formatarDataHora(dt) {
  if (!dt) return '—';
  const d = new Date(dt.replace(' ', 'T'));
  return d.toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' });
}

async function carregar() {
  const res = await fetch(`${API}?action=listar`);
  const data = await res.json();

  if (!data.success) {
    lista.innerHTML = `<p class="empty-msg">${data.message}</p>`;
    contador.textContent = '0';
    return;
  }

  EU = data.eu;
  const items = data.items;
  contador.textContent = items.length;

  if (!items.length) {
    lista.innerHTML = `
      <div class="empty-state">
        <p>Nenhum usuário vinculado ainda.</p>
        <p style="font-size:13px;">Clique em "Convidar usuário" para adicionar o primeiro.</p>
      </div>`;
    return;
  }

  lista.innerHTML = items.map(u => {
    const souEu = u.id == EU;
    const ehOwner = u.eh_owner == 1;
    const ativo = u.status === 'ativo';

    return `
      <div class="list-item membro-item">
        <div class="membro-info">
          <div class="membro-avatar">${escaparHTML(u.nome.charAt(0).toUpperCase())}</div>
          <div>
            <div class="membro-nome">
              ${escaparHTML(u.nome)}
              ${souEu ? '<span class="badge badge-azul" style="margin-left:8px;">Você</span>' : ''}
              ${ehOwner ? '<span class="badge badge-roxo" style="margin-left:8px;">Criador</span>' : ''}
              ${!ativo ? '<span class="badge badge-vermelho" style="margin-left:8px;">Inativo</span>' : ''}
            </div>
            <div class="membro-email">${escaparHTML(u.email)}</div>
            <div class="membro-meta">Último acesso: ${formatarDataHora(u.ultimo_acesso)}</div>
          </div>
        </div>
        <div class="list-actions">
          ${!souEu && !ehOwner ? `
            <button class="btn-toggle ${ativo ? 'on' : 'off'}" onclick="toggleStatus(${u.id})">
              ${ativo ? 'Ativo' : 'Inativo'}
            </button>
            <button class="btn-remove" onclick="remover(${u.id})">Remover</button>
          ` : `
            <span class="cinza" style="font-size:12.5px;">
              ${ehOwner ? 'Conta protegida' : ''}
            </span>
          `}
        </div>
      </div>
    `;
  }).join('');
}

async function toggleStatus(id) {
  const fd = new FormData(); fd.append('id', id);
  const res = await fetch(`${API}?action=toggle_status`, { method: 'POST', body: fd });
  const data = await res.json();
  if (!data.success) alert(data.message);
  carregar();
}

async function remover(id) {
  if (!confirm('Remover este usuário da equipe?')) return;
  const fd = new FormData(); fd.append('id', id);
  const res = await fetch(`${API}?action=remover`, { method: 'POST', body: fd });
  const data = await res.json();
  if (!data.success) alert(data.message);
  carregar();
}

function abrirModalConvite() {
  document.getElementById('modalConviteBody').innerHTML = `
    <h2>Convidar usuário</h2>
    <p class="modal-sub">Ele terá acesso à sua empresa com a mesma permissão que você.</p>

    <form id="formConvite" class="form-grid">
      <div class="form-group">
        <label>Nome completo *</label>
        <input type="text" name="nome" required maxlength="150">
      </div>
      <div class="form-group">
        <label>E-mail *</label>
        <input type="email" name="email" required maxlength="150">
      </div>
      <div class="form-group" style="grid-column:1/-1;">
        <label>Telefone</label>
        <input type="text" name="telefone" maxlength="20">
      </div>
      <div class="form-actions" style="grid-column:1/-1; display:flex; justify-content:flex-end; gap:10px;">
        <button type="button" class="btn btn-ghost" onclick="fecharModalConvite()">Cancelar</button>
        <button type="submit" class="btn btn-primary">Convidar</button>
      </div>
      <div id="feedbackConvite" class="form-feedback" style="grid-column:1/-1;"></div>
      <div id="senhaGeradaBox" class="feedback-senha" style="grid-column:1/-1; display:none;"></div>
    </form>
  `;
  document.getElementById('modalConvite').classList.add('active');

  document.getElementById('formConvite').addEventListener('submit', async (e) => {
    e.preventDefault();
    const fb = document.getElementById('feedbackConvite');
    fb.textContent = 'Convidando...';
    fb.className = 'form-feedback';

    const res = await fetch(`${API}?action=convidar`, { method: 'POST', body: new FormData(e.target) });
    const data = await res.json();

    if (data.success) {
      fb.textContent = '✓ Usuário convidado com sucesso.';
      fb.className = 'form-feedback ok';

      const box = document.getElementById('senhaGeradaBox');
      box.style.display = 'block';
      box.innerHTML = `
        <strong>Senha temporária:</strong>
        <div class="senha-box">
          <code>${data.senha_temporaria}</code>
          <button type="button" class="btn-copiar" onclick="navigator.clipboard.writeText('${data.senha_temporaria}')">Copiar</button>
        </div>
        <small>Envie esta senha ao novo usuário.</small>
      `;

      e.target.querySelectorAll('input').forEach(i => i.value = '');
      carregar();
    } else {
      fb.textContent = data.message;
      fb.className = 'form-feedback erro';
    }
  });
}

function fecharModalConvite() {
  document.getElementById('modalConvite').classList.remove('active');
}

carregar();
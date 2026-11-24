const API = BASE_URL + '/api/palavras.php';

const form         = document.getElementById('formPalavra');
const palavraInput = document.getElementById('palavraInput');
const feedback     = document.getElementById('feedbackPalavra');
const lista        = document.getElementById('listaPalavras');

form?.addEventListener('submit', async (e) => {
  e.preventDefault();
  const palavra = palavraInput.value.trim();
  if (!palavra) return;

  const fd = new FormData();
  fd.append('palavra', palavra);

  const res = await fetch(`${API}?action=adicionar`, { method: 'POST', body: fd });
  const data = await res.json();

  feedback.textContent = data.message;
  feedback.className = 'form-feedback ' + (data.success ? 'ok' : 'erro');

  if (data.success) {
    palavraInput.value = '';
    carregar();
  }
});

/* Sugestões rápidas */
document.querySelectorAll('.chip-sugestao').forEach(chip => {
  chip.addEventListener('click', () => {
    palavraInput.value = chip.dataset.p;
    palavraInput.focus();
  });
});

async function carregar() {
  const res = await fetch(`${API}?action=listar`);
  const data = await res.json();

  if (!data.items.length) {
    lista.innerHTML = '<p class="empty-msg">Nenhuma palavra cadastrada ainda.</p>';
    return;
  }

  lista.innerHTML = data.items.map(p => `
    <div class="list-item">
      <div>
        <strong>${escaparHTML(p.palavra)}</strong>
      </div>
      <div class="list-actions">
        <button class="btn-toggle ${p.ativo == 1 ? 'on' : 'off'}" onclick="toggle(${p.id})">
          ${p.ativo == 1 ? 'Ativa' : 'Inativa'}
        </button>
        <button class="btn-remove" onclick="remover(${p.id})">Remover</button>
      </div>
    </div>
  `).join('');
}

function escaparHTML(s) {
  if (s == null) return '';
  return String(s).replace(/[&<>"']/g, c => ({ '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;' }[c]));
}

async function toggle(id) {
  const fd = new FormData(); fd.append('id', id);
  await fetch(`${API}?action=toggle`, { method: 'POST', body: fd });
  carregar();
}

async function remover(id) {
  if (!confirm('Remover esta palavra?')) return;
  const fd = new FormData(); fd.append('id', id);
  await fetch(`${API}?action=remover`, { method: 'POST', body: fd });
  carregar();
}

carregar();
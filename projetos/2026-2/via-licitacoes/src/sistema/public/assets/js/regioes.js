const API = BASE_URL + '/api/regioes.php';

const UFS = [
  ['AC','Acre'],['AL','Alagoas'],['AP','Amapá'],['AM','Amazonas'],['BA','Bahia'],
  ['CE','Ceará'],['DF','Distrito Federal'],['ES','Espírito Santo'],['GO','Goiás'],
  ['MA','Maranhão'],['MT','Mato Grosso'],['MS','Mato Grosso do Sul'],['MG','Minas Gerais'],
  ['PA','Pará'],['PB','Paraíba'],['PR','Paraná'],['PE','Pernambuco'],['PI','Piauí'],
  ['RJ','Rio de Janeiro'],['RN','Rio Grande do Norte'],['RS','Rio Grande do Sul'],
  ['RO','Rondônia'],['RR','Roraima'],['SC','Santa Catarina'],['SP','São Paulo'],
  ['SE','Sergipe'],['TO','Tocantins']
];

const ufSelect    = document.getElementById('ufSelect');
const municipio   = document.getElementById('municipioInput');
const form        = document.getElementById('formRegiao');
const feedback    = document.getElementById('feedbackRegiao');
const lista       = document.getElementById('listaRegioes');

// Popula select de UFs
UFS.forEach(([sigla, nome]) => {
  const opt = document.createElement('option');
  opt.value = sigla;
  opt.textContent = `${sigla} — ${nome}`;
  ufSelect.appendChild(opt);
});

form?.addEventListener('submit', async (e) => {
  e.preventDefault();
  const fd = new FormData();
  fd.append('action', 'adicionar');
  fd.append('uf', ufSelect.value);
  fd.append('municipio', municipio.value);

  const res = await fetch(API, { method: 'POST', body: fd });
  const data = await res.json();

  feedback.textContent = data.message;
  feedback.className = 'form-feedback ' + (data.success ? 'ok' : 'erro');

  if (data.success) {
    municipio.value = '';
    ufSelect.value = '';
    carregar();
  }
});

async function carregar() {
  const res = await fetch(`${API}?action=listar`);
  const data = await res.json();

  if (!data.items.length) {
    lista.innerHTML = '<p class="empty-msg">Nenhuma região cadastrada ainda.</p>';
    return;
  }

  lista.innerHTML = data.items.map(r => `
    <div class="list-item">
      <div>
        <strong>${r.uf}</strong>
        <span>${r.municipio ?? 'Todo o estado'}</span>
      </div>
      <div class="list-actions">
        <button class="btn-toggle ${r.ativo == 1 ? 'on' : 'off'}" onclick="toggle(${r.id})">
          ${r.ativo == 1 ? 'Ativa' : 'Inativa'}
        </button>
        <button class="btn-remove" onclick="remover(${r.id})">Remover</button>
      </div>
    </div>
  `).join('');
}

async function toggle(id) {
  const fd = new FormData(); fd.append('action', 'toggle'); fd.append('id', id);
  await fetch(API, { method: 'POST', body: fd });
  carregar();
}

async function remover(id) {
  if (!confirm('Remover esta região?')) return;
  const fd = new FormData(); fd.append('action', 'remover'); fd.append('id', id);
  await fetch(API, { method: 'POST', body: fd });
  carregar();
}

carregar();
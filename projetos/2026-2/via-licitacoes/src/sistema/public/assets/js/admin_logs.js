const API = BASE_URL + '/api/admin/logs.php';

const tbody        = document.getElementById('tbodyLogs');
const contador     = document.getElementById('contadorLogs');
const paginacao    = document.getElementById('paginacao');
const filtroStatus = document.getElementById('filtroStatus');
const filtroTipo   = document.getElementById('filtroTipo');

const STATUS_CLS = {
  'SUCESSO': 'badge-verde',
  'PARCIAL': 'badge-amarelo',
  'ERRO':    'badge-vermelho',
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

async function carregar(pagina = 1) {
  tbody.innerHTML = '<tr><td colspan="6" class="empty-msg">Carregando...</td></tr>';

  const params = new URLSearchParams({
    action: 'listar',
    status: filtroStatus.value,
    tipo:   filtroTipo.value,
    pagina: pagina,
  });

  const res = await fetch(`${API}?${params}`);
  const data = await res.json();

  if (!data.items.length) {
    tbody.innerHTML = '<tr><td colspan="6" class="empty-msg">Nenhuma execução registrada ainda.</td></tr>';
    contador.textContent = '0';
    paginacao.innerHTML = '';
    return;
  }

  contador.textContent = data.total;

  tbody.innerHTML = data.items.map(l => `
    <tr>
      <td>${formatarDataHora(l.data_execucao)}</td>
      <td>${escaparHTML(l.fonte_nome ?? '—')}</td>
      <td>${escaparHTML(l.tipo_execucao ?? '—')}</td>
      <td><span class="badge ${STATUS_CLS[l.status] ?? 'badge-azul'}">${l.status}</span></td>
      <td>${l.quantidade_registros ?? 0}</td>
      <td style="max-width:320px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">
        ${escaparHTML(l.mensagem ?? '—')}
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

function limparFiltros() {
  filtroStatus.value = '';
  filtroTipo.value = '';
  carregar(1);
}

carregar(1);
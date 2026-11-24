const API = BASE_URL + '/api/notificacoes.php';
const lista = document.getElementById('listaNotificacoes');

function formatarDataHora(dt) {
  if (!dt) return '';
  const d = new Date(dt.replace(' ', 'T'));
  return d.toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' });
}

async function carregar() {
  const res = await fetch(`${API}?action=listar`);
  const data = await res.json();

  if (!data.items.length) {
    lista.innerHTML = `
      <div class="empty-state">
        <p>Você não tem notificações ainda.</p>
        <p style="font-size:13px;">Assim que configurarmos seus CNAEs e regiões, você será avisado sobre novas oportunidades.</p>
      </div>`;
    return;
  }

  lista.innerHTML = data.items.map(n => `
    <div class="notif-item ${n.lida == 1 ? 'lida' : 'nova'}" onclick="marcarLida(${n.id})">
      <div class="notif-dot"></div>
      <div class="notif-body">
        <div class="notif-top">
          <strong>${n.titulo ?? 'Nova notificação'}</strong>
          <span class="notif-data">${formatarDataHora(n.data_envio)}</span>
        </div>
        <p class="notif-msg">${n.mensagem ?? ''}</p>
        ${n.objeto ? `<p class="notif-lic">🔗 ${n.numero_licitacao ? '#' + n.numero_licitacao + ' — ' : ''}${n.objeto}</p>` : ''}
      </div>
    </div>
  `).join('');
}

async function marcarLida(id) {
  const fd = new FormData();
  fd.append('action', 'marcar_lida');
  fd.append('id', id);
  await fetch(API, { method: 'POST', body: fd });
  carregar();
}

async function marcarTodasLidas() {
  const fd = new FormData();
  fd.append('action', 'marcar_todas');
  await fetch(API, { method: 'POST', body: fd });
  carregar();
}

carregar();
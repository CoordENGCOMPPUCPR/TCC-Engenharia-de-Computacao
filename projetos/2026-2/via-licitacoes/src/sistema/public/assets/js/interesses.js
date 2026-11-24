const API = BASE_URL + '/api/interesses.php';

const listaInteresses = document.getElementById('listaInteresses');
let statusFiltro = '';
let interesseAbertoId = null;

/* ---------- HELPERS ---------- */
function escaparHTML(s) {
  if (s == null) return '';
  return String(s).replace(/[&<>"']/g, c => ({ '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;' }[c]));
}
function formatarValor(v) {
  if (v == null || v === '' || v === 0) return '—';
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

const STATUS_INFO = {
  'INTERESSE':           { label: 'Interesse',           cls: 'st-azul' },
  'ANALISANDO':          { label: 'Analisando',          cls: 'st-amarelo' },
  'PREPARANDO_PROPOSTA': { label: 'Preparando proposta', cls: 'st-laranja' },
  'PROPOSTA_ENVIADA':    { label: 'Proposta enviada',    cls: 'st-roxo' },
  'EM_DISPUTA':          { label: 'Em disputa',          cls: 'st-azul-escuro' },
  'GANHAMOS':            { label: 'Ganhamos',            cls: 'st-verde' },
  'PERDEMOS':            { label: 'Perdemos',            cls: 'st-vermelho' },
  'DESCARTADO':          { label: 'Descartado',          cls: 'st-cinza' },
};

/* ---------- CARREGAR ---------- */
async function carregar() {
  const res = await fetch(`${API}?action=listar`);
  const data = await res.json();
  if (!data.success) {
    listaInteresses.innerHTML = `<p class="empty-msg">${data.message}</p>`;
    return;
  }

  let items = data.items;
  if (statusFiltro) items = items.filter(i => i.status_disputa === statusFiltro);

  if (!items.length) {
    listaInteresses.innerHTML = `
      <div class="empty-state">
        <p>Sua empresa ainda não salvou nenhuma licitação como interesse.</p>
        <a href="${BASE_URL}/app/licitacoes.php" class="btn btn-primary">Ver licitações disponíveis</a>
      </div>`;
    return;
  }

  listaInteresses.innerHTML = items.map(i => {
    const st = STATUS_INFO[i.status_disputa] || STATUS_INFO['INTERESSE'];
    const tarefasTxt = i.tarefas_total > 0
      ? `<span class="ic-mini ${i.tarefas_pendentes > 0 ? 'pendente' : 'ok'}">☑️ ${i.tarefas_total - i.tarefas_pendentes}/${i.tarefas_total}</span>`
      : '';
    const comentTxt = i.comentarios_total > 0
      ? `<span class="ic-mini">💬 ${i.comentarios_total}</span>`
      : '';

    return `
      <div class="interesse-card" onclick="abrirWorkspace(${i.id})">
        <div class="ic-top">
          <span class="status-badge ${st.cls}">${st.label}</span>
          <span class="ic-uf">${escaparHTML(i.uf ?? '—')} · ${escaparHTML(i.municipio ?? '—')}</span>
        </div>
        <h3 class="ic-titulo">${escaparHTML(i.numero_licitacao ?? 'Edital')}</h3>
        <p class="ic-objeto">${escaparHTML(truncar(i.objeto ?? 'Sem descrição', 160))}</p>
        <div class="ic-meta">
          <span><strong>Órgão:</strong> ${escaparHTML(truncar(i.orgao ?? '—', 40))}</span>
          <span><strong>Estimado:</strong> ${formatarValor(i.valor_estimado)}</span>
          ${i.fim_propostas ? `<span><strong>Abertura:</strong> ${formatarDataCurta(i.fim_propostas)}</span>` : ''}
        </div>
        ${i.valor_minimo || i.valor_inicial ? `
          <div class="ic-negociacao">
            ${i.valor_minimo ? `<span><strong>Mín:</strong> ${formatarValor(i.valor_minimo)}</span>` : ''}
            ${i.valor_inicial ? `<span><strong>Inicial:</strong> ${formatarValor(i.valor_inicial)}</span>` : ''}
            ${i.valor_maximo ? `<span><strong>Máx:</strong> ${formatarValor(i.valor_maximo)}</span>` : ''}
          </div>
        ` : ''}
        <div class="ic-bottom">
          <div class="ic-mini-group">${tarefasTxt} ${comentTxt}</div>
          <span class="ic-autor">por ${escaparHTML(i.autor_nome ?? '—')}</span>
        </div>
      </div>
    `;
  }).join('');
}

function truncar(txt, max) {
  if (!txt) return '';
  return txt.length > max ? txt.substring(0, max) + '…' : txt;
}

/* ---------- FILTRO POR STATUS ---------- */
document.querySelectorAll('.btn-status').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.btn-status').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    statusFiltro = btn.dataset.status;
    carregar();
  });
});

/* ---------- WORKSPACE (modal) ---------- */
async function abrirWorkspace(id) {
  interesseAbertoId = id;
  const res = await fetch(`${API}?action=detalhes&id=${id}`);
  const data = await res.json();
  if (!data.success) return;
  renderizarWorkspace(data.interesse);
  document.getElementById('modalWorkspace').classList.add('active');
}

function fecharModalWorkspace() {
  document.getElementById('modalWorkspace').classList.remove('active');
  interesseAbertoId = null;
  carregar();
}

function renderizarWorkspace(i) {
  const st = STATUS_INFO[i.status_disputa] || STATUS_INFO['INTERESSE'];

  // Opções de status
  const statusOpts = Object.entries(STATUS_INFO).map(([k, v]) =>
    `<option value="${k}" ${k === i.status_disputa ? 'selected' : ''}>${v.label}</option>`
  ).join('');

  // Tarefas
  const tarefasHtml = i.tarefas.length
    ? i.tarefas.map(t => `
        <div class="tarefa-item ${t.concluida ? 'concluida' : ''}">
          <label class="tarefa-check">
            <input type="checkbox" ${t.concluida ? 'checked' : ''} onchange="toggleTarefa(${t.id})">
            <span class="tarefa-titulo">${escaparHTML(t.titulo)}</span>
          </label>
          <div class="tarefa-acoes">
            ${t.concluida && t.concluido_por ? `<small>✓ ${escaparHTML(t.concluido_por)}</small>` : ''}
            <button class="tarefa-remove" onclick="removerTarefa(${t.id})" title="Remover">✕</button>
          </div>
        </div>
      `).join('')
    : `<p class="empty-msg">Nenhuma tarefa ainda. ${i.tarefas.length === 0 ? 'Crie o checklist padrão abaixo.' : ''}</p>`;

  // Comentários
  const comentHtml = i.comentarios.length
    ? i.comentarios.map(c => {
        const tipoCls = c.tipo === 'MUDANCA_STATUS' ? 'com-sistema' :
                        c.tipo === 'SISTEMA' ? 'com-sistema' : 'com-normal';
        const icone = c.tipo === 'MUDANCA_STATUS' ? '🔄' :
                      c.tipo === 'SISTEMA' ? '⚙️' : '💬';
        return `
          <div class="comentario ${tipoCls}">
            <div class="com-header">
              <strong>${icone} ${escaparHTML(c.nome_usuario)}</strong>
              <span>${formatarDataHora(c.data_criacao)}</span>
            </div>
            <p>${escaparHTML(c.comentario)}</p>
          </div>
        `;
      }).join('')
    : '<p class="empty-msg">Sem comentários ainda.</p>';

  const encerra = i.fim_propostas ? diasRestantes(i.fim_propostas) : null;
  const localidade = i.localidade || [i.municipio, i.uf].filter(Boolean).join(' — ') || '—';

  document.getElementById('modalWorkspaceBody').innerHTML = `
    <div class="ws-header">
      <div>
        <span class="status-badge ${st.cls}">${st.label}</span>
        <h2>${escaparHTML(i.numero_licitacao ?? 'Edital')}</h2>
        <p class="modal-sub">${escaparHTML(i.orgao ?? '—')} · ${escaparHTML(localidade)}</p>
      </div>
    </div>

    <!-- Info resumida -->
    <div class="ws-info-grid">
      <div class="ws-info">
        <span class="ws-label">VALOR ESTIMADO</span>
        <span class="ws-value">${formatarValor(i.valor_estimado)}</span>
      </div>
      <div class="ws-info">
        <span class="ws-label">ABERTURA</span>
        <span class="ws-value">${formatarDataHora(i.fim_propostas)}</span>
        ${encerra ? `<span class="ws-hint ${encerra.encerrado ? 'erro' : ''}">${encerra.texto}</span>` : ''}
      </div>
      <div class="ws-info">
        <span class="ws-label">PUBLICADO</span>
        <span class="ws-value">${formatarDataCurta(i.data_publicacao)}</span>
      </div>
      <div class="ws-info">
        <span class="ws-label">MARCADO POR</span>
        <span class="ws-value">${escaparHTML(i.autor_nome ?? '—')}</span>
      </div>
    </div>

    <!-- Objeto -->
    <div class="ws-secao">
      <h4 class="ws-secao-titulo">Objeto</h4>
      <p class="ws-objeto">${escaparHTML(i.objeto ?? 'Sem descrição')}</p>
    </div>

    <!-- Grid de gestão: status + valores -->
    <div class="ws-secao">
      <h4 class="ws-secao-titulo">Gestão da disputa</h4>
      <form id="formGestao" class="ws-form-grid">
        <input type="hidden" name="id" value="${i.id}">
        <div class="form-group">
          <label>Status</label>
          <select name="status_disputa">${statusOpts}</select>
        </div>
        <div class="form-group">
          <label>Prazo interno</label>
          <input type="date" name="data_limite_interna" value="${i.data_limite_interna ?? ''}">
        </div>
        <div class="form-group">
          <label>Valor mínimo (R$)</label>
          <input type="text" name="valor_minimo" value="${i.valor_minimo ?? ''}" placeholder="0,00">
        </div>
        <div class="form-group">
          <label>Valor inicial da proposta (R$)</label>
          <input type="text" name="valor_inicial" value="${i.valor_inicial ?? ''}" placeholder="0,00">
        </div>
        <div class="form-group">
          <label>Valor máximo aceitável (R$)</label>
          <input type="text" name="valor_maximo" value="${i.valor_maximo ?? ''}" placeholder="0,00">
        </div>
        <div class="form-group" style="align-self:end;">
          <button type="submit" class="btn btn-primary" style="width:100%;">Salvar</button>
        </div>
        <div id="feedbackGestao" class="form-feedback" style="grid-column:1/-1;"></div>
      </form>
    </div>

    <!-- Tabs: Checklist e Comentários -->
    <div class="ws-tabs">
      <div class="ws-tab-headers">
        <button class="ws-tab-btn active" data-tab="checklist">Checklist</button>
        <button class="ws-tab-btn" data-tab="comentarios">Comentários & Histórico</button>
      </div>

      <!-- Checklist -->
      <div class="ws-tab" data-tab="checklist">
        <div class="tarefas-header">
          <div class="tarefas-add">
            <input type="text" id="novaTarefaInput" placeholder="Nova tarefa...">
            <button class="btn btn-primary" onclick="adicionarTarefa()">Adicionar</button>
          </div>
          <button class="btn btn-ghost btn-sm" onclick="criarChecklistPadrao()">+ Checklist padrão</button>
        </div>
        <div class="tarefas-lista" id="tarefasLista">${tarefasHtml}</div>
      </div>

      <!-- Comentários -->
      <div class="ws-tab" data-tab="comentarios" style="display:none;">
        <div class="comentarios-lista" id="comentariosLista">${comentHtml}</div>
        <div class="comentario-add">
          <textarea id="novoComentario" rows="2" placeholder="Escreva um comentário interno..."></textarea>
          <button class="btn btn-primary" onclick="adicionarComentario()">Comentar</button>
        </div>
      </div>
    </div>

    <div class="ws-footer">
      <button class="btn-remove-outline" onclick="removerInteresse(${i.id})">Remover interesse</button>
      <div style="display:flex; gap:10px;">
        ${i.link_detalhes || true ? `<a href="${BASE_URL}/app/licitacoes.php" class="btn btn-ghost">Ver nas licitações</a>` : ''}
        <button class="btn btn-primary" onclick="fecharModalWorkspace()">Fechar</button>
      </div>
    </div>
  `;

  // Listeners do modal
  document.querySelectorAll('.ws-tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.ws-tab-btn').forEach(b => b.classList.remove('active'));
      document.querySelectorAll('.ws-tab').forEach(t => t.style.display = 'none');
      btn.classList.add('active');
      document.querySelector(`.ws-tab[data-tab="${btn.dataset.tab}"]`).style.display = 'block';
    });
  });

  document.getElementById('formGestao').addEventListener('submit', salvarGestao);

  // Máscaras dos valores
  document.querySelectorAll('#formGestao input[name^="valor_"]').forEach(inp => {
    inp.addEventListener('input', (e) => {
      let v = e.target.value.replace(/\D/g, '');
      if (v === '') { e.target.value = ''; return; }
      v = (parseInt(v, 10) / 100).toFixed(2);
      v = v.replace('.', ',').replace(/\B(?=(\d{3})+(?!\d))/g, '.');
      e.target.value = v;
    });
  });
}

function diasRestantes(fimStr) {
  if (!fimStr) return null;
  const fim = new Date(fimStr.replace(' ', 'T'));
  if (isNaN(fim)) return null;
  const diff = fim - new Date();
  if (diff < 0) return { texto: 'Encerrado', encerrado: true };
  const dias  = Math.floor(diff / 86400000);
  const horas = Math.floor((diff % 86400000) / 3600000);
  if (dias > 0) return { texto: `Encerra em ${dias}d ${horas}h`, encerrado: false };
  return { texto: `Encerra em ${horas}h`, encerrado: false };
}

/* ---------- SALVAR GESTÃO ---------- */
async function salvarGestao(e) {
  e.preventDefault();
  const fb = document.getElementById('feedbackGestao');
  fb.textContent = 'Salvando...';
  fb.className = 'form-feedback';

  const res = await fetch(`${API}?action=atualizar_dados`, { method: 'POST', body: new FormData(e.target) });
  const data = await res.json();

  fb.textContent = data.message;
  fb.className = 'form-feedback ' + (data.success ? 'ok' : 'erro');

  if (data.success) {
    // Recarrega o workspace para atualizar status badge
    setTimeout(() => abrirWorkspace(interesseAbertoId), 600);
  }
}

/* ---------- TAREFAS ---------- */
async function adicionarTarefa() {
  const input = document.getElementById('novaTarefaInput');
  const titulo = input.value.trim();
  if (!titulo) return;

  const fd = new FormData();
  fd.append('id_interesse', interesseAbertoId);
  fd.append('titulo', titulo);

  const res = await fetch(`${API}?action=tarefa_adicionar`, { method: 'POST', body: fd });
  const data = await res.json();
  if (data.success) {
    input.value = '';
    abrirWorkspace(interesseAbertoId);
  } else {
    alert(data.message);
  }
}

async function toggleTarefa(id) {
  const fd = new FormData(); fd.append('id', id);
  await fetch(`${API}?action=tarefa_toggle`, { method: 'POST', body: fd });
  abrirWorkspace(interesseAbertoId);
}

async function removerTarefa(id) {
  if (!confirm('Remover esta tarefa?')) return;
  const fd = new FormData(); fd.append('id', id);
  await fetch(`${API}?action=tarefa_remover`, { method: 'POST', body: fd });
  abrirWorkspace(interesseAbertoId);
}

async function criarChecklistPadrao() {
  if (!confirm('Criar checklist padrão de licitação? Isso adicionará 13 tarefas.')) return;
  const fd = new FormData();
  fd.append('id_interesse', interesseAbertoId);
  const res = await fetch(`${API}?action=tarefas_padrao`, { method: 'POST', body: fd });
  const data = await res.json();
  if (data.success) abrirWorkspace(interesseAbertoId);
  else alert(data.message);
}

/* ---------- COMENTÁRIOS ---------- */
async function adicionarComentario() {
  const ta = document.getElementById('novoComentario');
  const texto = ta.value.trim();
  if (!texto) return;

  const fd = new FormData();
  fd.append('id_interesse', interesseAbertoId);
  fd.append('comentario', texto);

  const res = await fetch(`${API}?action=comentario_adicionar`, { method: 'POST', body: fd });
  const data = await res.json();
  if (data.success) abrirWorkspace(interesseAbertoId);
  else alert(data.message);
}

/* ---------- REMOVER INTERESSE ---------- */
async function removerInteresse(id) {
  if (!confirm('Remover este interesse? Todos os comentários e tarefas também serão apagados.')) return;
  const fd = new FormData(); fd.append('id', id);
  await fetch(`${API}?action=remover`, { method: 'POST', body: fd });
  fecharModalWorkspace();
}

carregar();
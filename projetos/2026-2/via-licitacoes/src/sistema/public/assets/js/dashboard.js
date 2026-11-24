const API = BASE_URL + '/api/dashboard.php';

/* ---------- HELPERS ---------- */
function escaparHTML(s) {
  if (s == null) return '';
  return String(s).replace(/[&<>"']/g, c => ({ '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;' }[c]));
}
function formatarValorCurto(v) {
  if (!v || v == 0) return 'R$ 0';
  const n = parseFloat(v);
  if (n >= 1000000) return 'R$ ' + (n / 1000000).toFixed(1).replace('.', ',') + ' mi';
  if (n >= 1000)    return 'R$ ' + (n / 1000).toFixed(1).replace('.', ',') + ' mil';
  return 'R$ ' + n.toLocaleString('pt-BR', { minimumFractionDigits: 0 });
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
function truncar(txt, max = 60) {
  if (!txt) return '';
  return txt.length > max ? txt.substring(0, max) + '…' : txt;
}
function diasRestantes(fimStr) {
  if (!fimStr) return null;
  const fim = new Date(fimStr.replace(' ', 'T'));
  if (isNaN(fim)) return null;
  const diff = fim - new Date();
  if (diff < 0) return { texto: 'Encerrado', encerrado: true };
  const dias  = Math.floor(diff / 86400000);
  const horas = Math.floor((diff % 86400000) / 3600000);
  if (dias > 0) return { texto: `em ${dias}d`, encerrado: false };
  return { texto: `em ${horas}h`, encerrado: false };
}

const STATUS_INFO = {
  'INTERESSE':           { label: 'Interesse',           cls: 'st-azul' },
  'ANALISANDO':          { label: 'Analisando',          cls: 'st-amarelo' },
  'PREPARANDO_PROPOSTA': { label: 'Preparando',          cls: 'st-laranja' },
  'PROPOSTA_ENVIADA':    { label: 'Enviada',             cls: 'st-roxo' },
  'EM_DISPUTA':          { label: 'Disputa',             cls: 'st-azul-escuro' },
  'GANHAMOS':            { label: 'Ganhamos',            cls: 'st-verde' },
  'PERDEMOS':            { label: 'Perdemos',            cls: 'st-vermelho' },
  'DESCARTADO':          { label: 'Descartado',          cls: 'st-cinza' },
};

/* ---------- CARREGAR ---------- */
async function carregar() {
  const res = await fetch(`${API}?action=resumo`);
  const data = await res.json();

  if (!data.success) {
    document.getElementById('subtitulo').textContent = data.message ?? 'Erro ao carregar painel.';
    return;
  }

  if (data.sem_empresa) {
    document.getElementById('subtitulo').textContent = 'Cadastre sua empresa para começar.';
    document.querySelector('main').innerHTML = `
      <div class="dash-panel" style="text-align:center; padding:60px 20px;">
        <h2>Bem-vindo à Via Licitações!</h2>
        <p style="color:var(--cinza-texto); margin:12px 0 24px;">
          Antes de começar, cadastre os dados da sua empresa para que possamos monitorar as licitações de acordo com o seu perfil.
        </p>
        <a href="${BASE_URL}/app/empresa.php" class="btn btn-primary">Cadastrar minha empresa</a>
      </div>`;
    return;
  }

  const k = data.kpi;

  // Saudação
  const empresa = data.empresa?.nome_fantasia || data.empresa?.razao_social || '';
  document.getElementById('subtitulo').innerHTML =
    `Visão geral de <strong>${escaparHTML(empresa)}</strong> — atualizada agora.`;

  // KPIs
  document.getElementById('kpiTotalLicitacoes').textContent = k.total_licitacoes.toLocaleString('pt-BR');
  document.getElementById('kpiTotalMatch').textContent      = k.total_match.toLocaleString('pt-BR');
  document.getElementById('kpiInteresses').textContent      = k.interesses_total.toLocaleString('pt-BR');
  document.getElementById('kpiValorDisputa').textContent    = formatarValorCurto(k.valor_em_disputa);
  document.getElementById('kpiEncerrando').textContent      = k.encerrando_7_dias.toLocaleString('pt-BR');
  document.getElementById('kpiTarefas').textContent         = k.tarefas_pendentes.toLocaleString('pt-BR');

  // Palavras
  const boxP = document.getElementById('listaPalavras');
  if (!data.palavras.length) {
    boxP.innerHTML = `<p class="empty-msg">Nenhuma palavra cadastrada. <a href="${BASE_URL}/app/palavras.php">Cadastrar</a></p>`;
  } else {
    boxP.innerHTML = data.palavras.map(p => `
      <a href="${BASE_URL}/app/licitacoes.php" class="mini-item ${p.ativo == 1 ? '' : 'inativo'}">
        <div class="mini-item-left">
          <span class="mini-dot ${p.ativo == 1 ? 'on' : 'off'}"></span>
          <strong>${escaparHTML(p.palavra)}</strong>
        </div>
        <span class="mini-badge">${p.qtd_licitacoes}</span>
      </a>
    `).join('');
  }

  // Regiões
  const boxR = document.getElementById('listaRegioes');
  if (!data.regioes.length) {
    boxR.innerHTML = `<p class="empty-msg">Nenhuma região cadastrada. <a href="${BASE_URL}/app/regioes.php">Cadastrar</a></p>`;
  } else {
    boxR.innerHTML = data.regioes.map(r => `
      <a href="${BASE_URL}/app/licitacoes.php" class="mini-item ${r.ativo == 1 ? '' : 'inativo'}">
        <div class="mini-item-left">
          <span class="mini-dot ${r.ativo == 1 ? 'on' : 'off'}"></span>
          <strong>${escaparHTML(r.uf)}${r.municipio ? ' — ' + escaparHTML(r.municipio) : ' (todo o estado)'}</strong>
        </div>
        <span class="mini-badge">${r.qtd_licitacoes}</span>
      </a>
    `).join('');
  }

  // Pipeline
  const pipeline = document.getElementById('pipeline');
  const statusOrdem = ['INTERESSE','ANALISANDO','PREPARANDO_PROPOSTA','PROPOSTA_ENVIADA','EM_DISPUTA','GANHAMOS','PERDEMOS','DESCARTADO'];
  const ativos = statusOrdem.filter(s => k.interesses_status[s] > 0);

  if (!ativos.length) {
    pipeline.innerHTML = `<p class="empty-msg">Nenhuma licitação salva ainda. <a href="${BASE_URL}/app/licitacoes.php">Ver licitações disponíveis</a></p>`;
  } else {
    const max = Math.max(...ativos.map(s => k.interesses_status[s]));
    pipeline.innerHTML = ativos.map(s => {
      const st = STATUS_INFO[s];
      const qtd = k.interesses_status[s];
      const pct = Math.max(8, (qtd / max) * 100);
      return `
        <a href="${BASE_URL}/app/interesses.php" class="pipeline-item">
          <div class="pipeline-head">
            <span class="status-badge ${st.cls}">${st.label}</span>
            <span class="pipeline-num">${qtd}</span>
          </div>
          <div class="pipeline-bar">
            <div class="pipeline-bar-fill ${st.cls}" style="width:${pct}%"></div>
          </div>
        </a>
      `;
    }).join('');
  }

  // Tarefas
  const boxT = document.getElementById('tarefasPendentes');
  if (!data.tarefas.length) {
    boxT.innerHTML = '<p class="empty-msg">Nenhuma tarefa pendente. Bom trabalho! 🎉</p>';
  } else {
    boxT.innerHTML = data.tarefas.map(t => {
      const encerra = diasRestantes(t.fim_propostas);
      const urgente = encerra && !encerra.encerrado && encerra.texto.includes('h') ? 'urgente' : '';
      return `
        <a href="${BASE_URL}/app/interesses.php" class="mini-item ${urgente}">
          <div class="mini-item-left">
            <span class="mini-check">☐</span>
            <div>
              <strong>${escaparHTML(truncar(t.titulo, 55))}</strong>
              <small>${escaparHTML(t.numero_licitacao ?? '')}</small>
            </div>
          </div>
          ${encerra ? `<span class="mini-prazo ${encerra.encerrado ? 'fim' : ''}">${encerra.texto}</span>` : ''}
        </a>
      `;
    }).join('');
  }

  // Urgentes
  const boxU = document.getElementById('licitacoesUrgentes');
  if (!data.urgentes.length) {
    boxU.innerHTML = '<p class="empty-msg">Nenhuma licitação encerrando nos próximos 7 dias.</p>';
  } else {
    boxU.innerHTML = data.urgentes.map(l => {
      const encerra = diasRestantes(l.fim_propostas);
      const marcada = l.marcada > 0 ? '<span class="mini-star">★</span>' : '';
      return `
        <a href="${BASE_URL}/app/licitacoes.php" class="mini-item urgente">
          <div class="mini-item-left">
            <span class="mini-dot urgente-dot"></span>
            <div>
              <strong>${marcada} ${escaparHTML(truncar(l.numero_licitacao ?? 'Edital', 40))}</strong>
              <small>${escaparHTML(l.uf ?? '')} · ${escaparHTML(truncar(l.objeto ?? '', 45))}</small>
            </div>
          </div>
          <span class="mini-prazo">${encerra.texto}</span>
        </a>
      `;
    }).join('');
  }

  // Atividade
  const boxA = document.getElementById('atividadeRecente');
  if (!data.atividade.length) {
    boxA.innerHTML = '<p class="empty-msg">Nenhuma atividade recente.</p>';
  } else {
    boxA.innerHTML = data.atividade.map(c => {
      const icone = c.tipo === 'MUDANCA_STATUS' ? '🔄' :
                    c.tipo === 'SISTEMA' ? '⚙️' : '💬';
      const tipoCls = c.tipo === 'COMENTARIO' ? 'at-comentario' : 'at-sistema';
      return `
        <div class="atividade-item ${tipoCls}">
          <div class="at-icone">${icone}</div>
          <div class="at-body">
            <div class="at-header">
              <strong>${escaparHTML(c.nome_usuario ?? 'Sistema')}</strong>
              <span>${formatarDataHora(c.data_criacao)}</span>
            </div>
            <p>${escaparHTML(truncar(c.comentario, 140))}</p>
            <small>em <em>${escaparHTML(c.numero_licitacao ?? '—')}</em></small>
          </div>
        </div>
      `;
    }).join('');
  }
}

carregar();
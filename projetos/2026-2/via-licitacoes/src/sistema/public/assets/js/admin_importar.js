const API = BASE_URL + '/api/admin/importar.php';

const uploadArea   = document.getElementById('uploadArea');
const arquivoInput = document.getElementById('arquivoInput');
const arquivoSel   = document.getElementById('arquivoSelecionado');
const feedbackUp   = document.getElementById('feedbackUpload');
const previewPanel = document.getElementById('previewPanel');
const tabelaPrev   = document.getElementById('tabelaPreview');
const contadorPrev = document.getElementById('contadorPreview');
const feedbackImp  = document.getElementById('feedbackImport');
const btnConfirmar = document.getElementById('btnConfirmar');

let arquivoTmpAtual = null;
let formatoAtual = 'PNCP';

/* ---------- SELETOR DE FORMATO ---------- */
document.querySelectorAll('.formato-card').forEach(card => {
  card.addEventListener('click', () => {
    document.querySelectorAll('.formato-card').forEach(c => c.classList.remove('active'));
    card.classList.add('active');
    card.querySelector('input').checked = true;
    formatoAtual = card.dataset.chave;
    cancelarPreview();
  });
});

/* ---------- UPLOAD ---------- */
uploadArea.addEventListener('click', () => arquivoInput.click());
uploadArea.addEventListener('dragover', (e) => { e.preventDefault(); uploadArea.classList.add('drag'); });
uploadArea.addEventListener('dragleave', () => uploadArea.classList.remove('drag'));
uploadArea.addEventListener('drop', (e) => {
  e.preventDefault();
  uploadArea.classList.remove('drag');
  if (e.dataTransfer.files.length) {
    arquivoInput.files = e.dataTransfer.files;
    enviarPreview();
  }
});
arquivoInput.addEventListener('change', enviarPreview);

async function enviarPreview() {
  const f = arquivoInput.files[0];
  if (!f) return;

  arquivoSel.style.display = 'block';
  arquivoSel.innerHTML = `📎 <strong>${f.name}</strong> — ${(f.size / 1024).toFixed(1)} KB`;
  feedbackUp.textContent = 'Processando arquivo...';
  feedbackUp.className = 'form-feedback';

  const fd = new FormData();
  fd.append('arquivo', f);

  try {
    const res = await fetch(`${API}?action=preview&formato=${encodeURIComponent(formatoAtual)}`, {
      method: 'POST',
      body: fd,
    });
    const data = await res.json();

    if (!data.success) {
      feedbackUp.textContent = data.message;
      feedbackUp.className = 'form-feedback erro';
      return;
    }

    feedbackUp.innerHTML = `
      ✓ <strong>${data.total}</strong> linhas encontradas —
      <span style="color:var(--sucesso);">${data.novos} novas</span>,
      <span style="color:var(--azul-principal);">${data.atualizados} para atualizar</span>,
      <span style="color:var(--cinza-texto);">${data.ignorados} ignoradas</span>
    `;
    feedbackUp.className = 'form-feedback ok';

    arquivoTmpAtual = data.arquivo_tmp;
    renderizarPreview(data.colunas, data.preview, data.total);
  } catch (err) {
    feedbackUp.textContent = 'Erro ao processar. Tente novamente.';
    feedbackUp.className = 'form-feedback erro';
  }
}

function renderizarPreview(colunas, preview, total) {
  contadorPrev.textContent = total;

  const colunasVisiveis = colunas.filter(c => !['_ignorar', 'hash_registro'].includes(c));

  let html = '<thead><tr>';
  colunasVisiveis.forEach(c => html += `<th>${rotuloColuna(c)}</th>`);
  html += '</tr></thead><tbody>';

  preview.forEach(row => {
    html += '<tr>';
    colunasVisiveis.forEach(c => {
      let v = row[c] ?? '';
      if (c === 'objeto') v = v.length > 120 ? v.substring(0, 120) + '…' : v;
      html += `<td>${escaparHTML(v)}</td>`;
    });
    html += '</tr>';
  });
  html += '</tbody>';

  tabelaPrev.innerHTML = html;
  previewPanel.style.display = 'block';
  previewPanel.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function rotuloColuna(c) {
  const mapa = {
    'link_detalhes': 'Link',
    'numero_licitacao': 'Edital',
    'data_publicacao': 'Publicação',
    'id_contratacao_pncp': 'ID PNCP',
    'situacao_pncp': 'Situação',
    'modalidade': 'Modalidade',
    'amparo_legal': 'Amparo Legal',
    'modo_disputa': 'Modo',
    'srp': 'SRP',
    'fonte_orcamentaria': 'Fonte',
    'orgao': 'Órgão',
    'unidade': 'Unidade',
    'localidade': 'Localidade',
    'inicio_propostas': 'Início Propostas',
    'fim_propostas': 'Fim Propostas',
    'plataforma': 'Plataforma',
    'objeto': 'Objeto',
    'valor_estimado': 'Valor Estimado',
    'valor_homologado': 'Valor Homologado',
    'uf': 'UF',
    'municipio': 'Município',
  };
  return mapa[c] ?? c;
}

function escaparHTML(s) {
  if (s == null) return '';
  return String(s).replace(/[&<>"']/g, c => ({ '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;' }[c]));
}

/* ---------- CONFIRMAR ---------- */
async function confirmarImportacao() {
  if (!arquivoTmpAtual) return;

  if (!confirm('Confirmar a importação? Os registros já existentes serão ATUALIZADOS com os novos dados.')) return;

  btnConfirmar.disabled = true;
  feedbackImp.textContent = 'Importando... isso pode levar alguns segundos.';
  feedbackImp.className = 'form-feedback';

  const fd = new FormData();
  fd.append('arquivo_tmp', arquivoTmpAtual);

    try {
      const res = await fetch(`${API}?action=confirmar`, { method: 'POST', body: fd });
      const texto = await res.text();

      let data;
      try {
        data = JSON.parse(texto);
      } catch (e) {
        console.error('Resposta não-JSON do servidor:', texto);
        feedbackImp.innerHTML = `<strong>Erro do servidor:</strong><br>
          <pre style="font-size:11px;text-align:left;background:#fef2f2;padding:10px;border-radius:6px;overflow:auto;max-height:200px;">${escaparHTML(texto.substring(0, 600))}</pre>`;
        feedbackImp.className = 'form-feedback erro';
        btnConfirmar.disabled = false;
        return;
      }

      feedbackImp.textContent = data.message;
      feedbackImp.className = 'form-feedback ' + (data.success ? 'ok' : 'erro');

      if (data.success) {
        setTimeout(() => {
          window.location.href = BASE_URL + '/admin/licitacoes.php';
        }, 1500);
      } else {
        btnConfirmar.disabled = false;
      }
    } catch (err) {
      feedbackImp.textContent = 'Erro de rede: ' + err.message;
      feedbackImp.className = 'form-feedback erro';
      btnConfirmar.disabled = false;
    }
  
}

function cancelarPreview() {
  previewPanel.style.display = 'none';
  arquivoInput.value = '';
  arquivoSel.style.display = 'none';
  feedbackUp.textContent = '';
  arquivoTmpAtual = null;
}
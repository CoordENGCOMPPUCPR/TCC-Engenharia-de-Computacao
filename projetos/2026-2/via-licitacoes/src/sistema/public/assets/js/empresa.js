const API = BASE_URL + '/api/empresa.php';
const API_PERFIL = BASE_URL + '/api/perfil.php';

const formEmpresa = document.getElementById('formEmpresa');
const feedbackEmpresa = document.getElementById('feedbackEmpresa');
const btnBuscarCnpj = document.getElementById('btnBuscarCnpj');
const feedbackCnpj = document.getElementById('feedbackCnpj');

const cnpjInput = document.getElementById('cnpjInput');
const telInput  = document.getElementById('telefoneInput');

cnpjInput?.addEventListener('input', (e) => {
  let v = e.target.value.replace(/\D/g, '').slice(0, 14);
  v = v.replace(/^(\d{2})(\d)/, '$1.$2')
       .replace(/^(\d{2})\.(\d{3})(\d)/, '$1.$2.$3')
       .replace(/\.(\d{3})(\d)/, '.$1/$2')
       .replace(/(\d{4})(\d)/, '$1-$2');
  e.target.value = v;
});

telInput?.addEventListener('input', (e) => {
  let v = e.target.value.replace(/\D/g, '').slice(0, 11);
  if (v.length <= 10) {
    v = v.replace(/(\d{0,2})(\d{0,4})(\d{0,4}).*/, '($1) $2-$3').trim();
  } else {
    v = v.replace(/(\d{2})(\d{5})(\d{0,4}).*/, '($1) $2-$3');
  }
  e.target.value = v;
});

btnBuscarCnpj?.addEventListener('click', async () => {
  const cnpj = cnpjInput.value.replace(/\D/g, '');
  if (cnpj.length !== 14) {
    feedbackCnpj.textContent = 'Digite um CNPJ válido (14 dígitos).';
    feedbackCnpj.className = 'form-feedback erro';
    return;
  }

  feedbackCnpj.textContent = 'Consultando...';
  feedbackCnpj.className = 'form-feedback';
  btnBuscarCnpj.disabled = true;

  try {
    const res = await fetch(`${API_PERFIL}?action=consultar_cnpj&cnpj=${cnpj}`);
    const data = await res.json();

    if (!data.success) {
      feedbackCnpj.textContent = data.message;
      feedbackCnpj.className = 'form-feedback erro';
      return;
    }

    const e = data.empresa;
    document.getElementById('razaoInput').value      = e.razao_social || '';
    document.getElementById('fantasiaInput').value   = e.nome_fantasia || '';
    document.getElementById('naturezaInput').value   = e.natureza_juridica || '';
    document.getElementById('cnaeInput').value       = e.cnae_principal || '';
    document.getElementById('telefoneInput').value   = formatarTelefoneVisual(e.telefone) || '';
    document.getElementById('emailInput').value      = e.email_contato || '';
    document.getElementById('enderecoInput').value   = e.endereco || '';
    document.getElementById('ufInput').value         = e.uf || '';
    document.getElementById('municipioInput').value  = e.municipio || '';

    feedbackCnpj.textContent = '✓ Dados preenchidos automaticamente. Revise e salve.';
    feedbackCnpj.className = 'form-feedback ok';

    renderizarCnaesSugeridos(data.cnaes || []);
  } catch (err) {
    feedbackCnpj.textContent = 'Erro ao consultar. Tente novamente.';
    feedbackCnpj.className = 'form-feedback erro';
  } finally {
    btnBuscarCnpj.disabled = false;
  }
});

function formatarTelefoneVisual(v) {
  if (!v) return '';
  v = v.replace(/\D/g, '');
  if (v.length === 11) return v.replace(/(\d{2})(\d{5})(\d{4})/, '($1) $2-$3');
  if (v.length === 10) return v.replace(/(\d{2})(\d{4})(\d{4})/, '($1) $2-$3');
  return v;
}

function renderizarCnaesSugeridos(cnaes) {
  const box = document.getElementById('boxSugestoesCnaes');
  const lista = document.getElementById('listaCnaesSugeridos');

  if (!cnaes || !cnaes.length) {
    box.style.display = 'none';
    return;
  }

  lista.innerHTML = cnaes
    .filter(c => !c.principal)
    .map(c => `
      <button type="button" class="chip-cnae" data-codigo="${c.codigo}">
        <strong>${c.codigo}</strong> — ${c.descricao}
      </button>
    `).join('');

  box.style.display = 'block';

  lista.querySelectorAll('.chip-cnae').forEach(btn => {
    btn.addEventListener('click', async () => {
      const codigo = btn.dataset.codigo;
      const fd = new FormData();
      fd.append('codigo', codigo);

      const res = await fetch(BASE_URL + '/api/cnaes.php?action=adicionar', { method: 'POST', body: fd });
      const data = await res.json();

      btn.classList.toggle('ativo', data.success);
      if (data.success) {
        btn.textContent = '✓ Adicionado — ' + codigo;
      } else {
        btn.textContent = '⚠ ' + data.message;
      }
    });
  });
}

formEmpresa?.addEventListener('submit', async (e) => {
  e.preventDefault();
  feedbackEmpresa.textContent = 'Salvando...';
  feedbackEmpresa.className = 'form-feedback';

  const res = await fetch(API, { method: 'POST', body: new FormData(formEmpresa) });
  const data = await res.json();

  feedbackEmpresa.textContent = data.message;
  feedbackEmpresa.className = 'form-feedback ' + (data.success ? 'ok' : 'erro');
});
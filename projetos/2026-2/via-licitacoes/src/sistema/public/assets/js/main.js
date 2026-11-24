/* =====================================================
   VIA LICITAÇÕES — JS principal (landing)
   ===================================================== */

/* ---------- MODAL LOGIN ---------- */
function abrirModalLogin() {
  const modal = document.getElementById('modalLogin');
  modal.classList.add('active');
  modal.setAttribute('aria-hidden', 'false');
  setTimeout(() => modal.querySelector('input[name="email"]')?.focus(), 100);
}

function fecharModalLogin() {
  const modal = document.getElementById('modalLogin');
  modal.classList.remove('active');
  modal.setAttribute('aria-hidden', 'true');
  const fb = document.getElementById('loginFeedback');
  if (fb) { fb.textContent = ''; fb.className = 'form-feedback'; }
}

document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') fecharModalLogin();
});

/* ---------- MÁSCARAS SIMPLES ---------- */
function mascaraTelefone(v) {
  v = v.replace(/\D/g, '').slice(0, 11);
  if (v.length <= 10) {
    return v.replace(/(\d{0,2})(\d{0,4})(\d{0,4}).*/, '($1) $2-$3').trim();
  }
  return v.replace(/(\d{2})(\d{5})(\d{0,4}).*/, '($1) $2-$3');
}

function mascaraCNPJ(v) {
  v = v.replace(/\D/g, '').slice(0, 14);
  return v
    .replace(/^(\d{2})(\d)/, '$1.$2')
    .replace(/^(\d{2})\.(\d{3})(\d)/, '$1.$2.$3')
    .replace(/\.(\d{3})(\d)/, '.$1/$2')
    .replace(/(\d{4})(\d)/, '$1-$2');
}

document.addEventListener('input', (e) => {
  if (e.target.name === 'telefone') e.target.value = mascaraTelefone(e.target.value);
  if (e.target.name === 'cnpj')     e.target.value = mascaraCNPJ(e.target.value);
});

/* ---------- LOGIN (AJAX) ---------- */
document.getElementById('formLogin')?.addEventListener('submit', async (e) => {
  e.preventDefault();
  const fb = document.getElementById('loginFeedback');
  fb.textContent = 'Entrando...';
  fb.className = 'form-feedback';

  try {
    const res = await fetch(BASE_URL + '/login.php', {
      method: 'POST',
      body: new FormData(e.target),
    });
    const data = await res.json();

    if (data.success) {
      fb.textContent = 'Sucesso! Redirecionando...';
      fb.className = 'form-feedback ok';
      window.location.href = data.redirect;
    } else {
      fb.textContent = data.message;
      fb.className = 'form-feedback erro';
    }
  } catch (err) {
    fb.textContent = 'Erro de conexão. Tente novamente.';
    fb.className = 'form-feedback erro';
  }
});

/* ---------- CADASTRO LEAD (AJAX) ---------- */
document.getElementById('formCadastro')?.addEventListener('submit', async (e) => {
  e.preventDefault();
  const fb = document.getElementById('formFeedback');
  fb.textContent = 'Enviando...';
  fb.className = 'form-feedback';

  try {
    const res = await fetch(BASE_URL + '/cadastro.php', {
      method: 'POST',
      body: new FormData(e.target),
    });
    const data = await res.json();

    if (data.success) {
      fb.textContent = '✓ ' + data.message;
      fb.className = 'form-feedback ok';
      e.target.reset();
    } else {
      fb.textContent = data.message;
      fb.className = 'form-feedback erro';
    }
  } catch (err) {
    fb.textContent = 'Erro de conexão. Tente novamente.';
    fb.className = 'form-feedback erro';
  }
});
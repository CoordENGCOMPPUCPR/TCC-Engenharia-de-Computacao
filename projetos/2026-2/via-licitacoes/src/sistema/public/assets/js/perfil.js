const API = BASE_URL + '/api/perfil.php';

document.querySelector('input[name="telefone"]')?.addEventListener('input', (e) => {
  let v = e.target.value.replace(/\D/g, '').slice(0, 11);
  if (v.length <= 10) {
    v = v.replace(/(\d{0,2})(\d{0,4})(\d{0,4}).*/, '($1) $2-$3').trim();
  } else {
    v = v.replace(/(\d{2})(\d{5})(\d{0,4}).*/, '($1) $2-$3');
  }
  e.target.value = v;
});

(async () => {
  const res = await fetch(`${API}?action=meus_dados`);
  const data = await res.json();
  if (!data.success) return;
  document.querySelector('input[name="telefone"]').value = data.dados.telefone ?? '';
})();

document.getElementById('formPerfil').addEventListener('submit', async (e) => {
  e.preventDefault();
  const fb = document.getElementById('feedbackPerfil');
  fb.textContent = 'Salvando...';
  fb.className = 'form-feedback';

  const res = await fetch(`${API}?action=atualizar`, { method: 'POST', body: new FormData(e.target) });
  const data = await res.json();

  fb.textContent = data.message;
  fb.className = 'form-feedback ' + (data.success ? 'ok' : 'erro');
});

document.getElementById('formSenha').addEventListener('submit', async (e) => {
  e.preventDefault();
  const fb = document.getElementById('feedbackSenha');
  fb.textContent = 'Alterando...';
  fb.className = 'form-feedback';

  const res = await fetch(`${API}?action=alterar_senha`, { method: 'POST', body: new FormData(e.target) });
  const data = await res.json();

  fb.textContent = data.message;
  fb.className = 'form-feedback ' + (data.success ? 'ok' : 'erro');

  if (data.success) e.target.reset();
});
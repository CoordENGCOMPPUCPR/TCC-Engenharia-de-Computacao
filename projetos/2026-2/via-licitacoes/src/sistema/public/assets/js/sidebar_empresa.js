(function () {
  const el = document.getElementById('empresaNomeSidebar');
  if (!el) return;

  fetch(BASE_URL + '/api/perfil.php?action=meus_dados')
    .then(r => r.json())
    .then(data => {
      if (data.success && data.dados && data.dados.razao_social) {
        el.textContent = data.dados.razao_social;
        el.title = data.dados.razao_social;
        el.style.opacity = '1';
      } else {
        el.textContent = 'Sem empresa';
        el.style.opacity = '0.5';
      }
    })
    .catch(() => {
      el.textContent = '—';
    });
})();
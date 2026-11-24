<?php
require_once __DIR__ . '/../../src/config/config.php';
require_once __DIR__ . '/../../src/core/Auth.php';
Auth::exigirLogin();
$user = Auth::usuario();
?>
<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Meus Interesses — Via Licitações</title>
<link rel="icon" type="image/png" href="<?= BASE_URL ?>/assets/img/favicon.png">
<link rel="stylesheet" href="<?= BASE_URL ?>/assets/css/style.css">
<link rel="stylesheet" href="<?= BASE_URL ?>/assets/css/dashboard.css">
</head>
<body class="dash-body">

<aside class="sidebar">
  <div class="sidebar-logo">
    <img src="<?= BASE_URL ?>/assets/img/logo.png" alt="Via Licitações">
    <span id="empresaNomeSidebar" class="empresa-nome-sidebar">—</span>
  </div>
  <nav class="sidebar-nav">
    <a href="<?= BASE_URL ?>/app/index.php"><span class="ico">📊</span> Dashboard</a>
    <a href="<?= BASE_URL ?>/app/licitacoes.php"><span class="ico">📋</span> Licitações</a>
    <a href="<?= BASE_URL ?>/app/interesses.php" class="active"><span class="ico">⭐</span> Meus Interesses</a>
    <a href="<?= BASE_URL ?>/app/palavras.php"><span class="ico">🎯</span> Palavras de Interesse</a>
    <a href="<?= BASE_URL ?>/app/regioes.php"><span class="ico">📍</span> Regiões</a>
    <a href="<?= BASE_URL ?>/app/empresa.php"><span class="ico">🏢</span> Minha Empresa</a>
    <a href="<?= BASE_URL ?>/app/equipe.php"><span class="ico">👥</span> Equipe</a>
    <a href="<?= BASE_URL ?>/app/notificacoes.php"><span class="ico">🔔</span> Notificações</a>
    <a href="<?= BASE_URL ?>/app/perfil.php"><span class="ico">👤</span> Meu Perfil</a>
  </nav>
  <div class="sidebar-footer"><a href="<?= BASE_URL ?>/logout.php" class="logout-link">Sair</a></div>
</aside>

<main class="dash-main">
  <header class="dash-header">
    <h1>Meus Interesses</h1>
    <p class="dash-sub">Workspace de cada licitação salva: checklist, negociação, comentários e histórico.</p>
  </header>

  <!-- Filtro por status -->
  <div class="dash-panel">
    <div class="filtros-status" id="filtrosStatus">
      <button class="btn-status active" data-status="">Todos</button>
      <button class="btn-status" data-status="INTERESSE">Interesse</button>
      <button class="btn-status" data-status="ANALISANDO">Analisando</button>
      <button class="btn-status" data-status="PREPARANDO_PROPOSTA">Preparando proposta</button>
      <button class="btn-status" data-status="PROPOSTA_ENVIADA">Proposta enviada</button>
      <button class="btn-status" data-status="EM_DISPUTA">Em disputa</button>
      <button class="btn-status" data-status="GANHAMOS">Ganhamos</button>
      <button class="btn-status" data-status="PERDEMOS">Perdemos</button>
      <button class="btn-status" data-status="DESCARTADO">Descartado</button>
    </div>
  </div>

  <div id="listaInteresses" class="interesses-grid">
    <p class="empty-msg">Carregando...</p>
  </div>
</main>

<!-- Modal workspace -->
<div id="modalWorkspace" class="modal">
  <div class="modal-backdrop" onclick="fecharModalWorkspace()"></div>
  <div class="modal-content modal-xl">
    <button class="modal-close" onclick="fecharModalWorkspace()">×</button>
    <div id="modalWorkspaceBody"></div>
  </div>
</div>

<script>
  const BASE_URL = "<?= BASE_URL ?>";
</script>
<script src="<?= BASE_URL ?>/assets/js/sidebar_empresa.js?v=<?= filemtime(__DIR__ . '/../assets/js/sidebar_empresa.js') ?>"></script>
<script src="<?= BASE_URL ?>/assets/js/interesses.js?v=<?= filemtime(__DIR__ . '/../assets/js/interesses.js') ?>"></script>
</body>
</html>
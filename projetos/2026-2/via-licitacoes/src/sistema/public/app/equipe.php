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
<title>Equipe — Via Licitações</title>
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
    <a href="<?= BASE_URL ?>/app/interesses.php"><span class="ico">⭐</span> Meus Interesses</a>
    <a href="<?= BASE_URL ?>/app/palavras.php"><span class="ico">🎯</span> Palavras de Interesse</a>    <a href="<?= BASE_URL ?>/app/regioes.php"><span class="ico">📍</span> Regiões</a>
    <a href="<?= BASE_URL ?>/app/empresa.php"><span class="ico">🏢</span> Minha Empresa</a>
    <a href="<?= BASE_URL ?>/app/equipe.php" class="active"><span class="ico">👥</span> Equipe</a>
    <a href="<?= BASE_URL ?>/app/notificacoes.php"><span class="ico">🔔</span> Notificações</a>
    <a href="<?= BASE_URL ?>/app/perfil.php"><span class="ico">👤</span> Meu Perfil</a>
  </nav>
  <div class="sidebar-footer"><a href="<?= BASE_URL ?>/logout.php" class="logout-link">Sair</a></div>
</aside>

<main class="dash-main">
  <header class="dash-header">
    <div style="display:flex; justify-content:space-between; align-items:flex-start; flex-wrap:wrap; gap:14px;">
      <div>
        <h1>Equipe</h1>
        <p class="dash-sub">Usuários com acesso à sua empresa.</p>
      </div>
      <button class="btn btn-primary" onclick="abrirModalConvite()">+ Convidar usuário</button>
    </div>
  </header>

  <div class="dash-panel">
    <div class="panel-head">
      <h2>Membros da equipe</h2>
      <span id="contadorEquipe" class="contador">0</span>
    </div>
    <div id="listaEquipe" class="list-box">
      <p class="empty-msg">Carregando...</p>
    </div>
  </div>
</main>

<div id="modalConvite" class="modal">
  <div class="modal-backdrop" onclick="fecharModalConvite()"></div>
  <div class="modal-content modal-lg">
    <button class="modal-close" onclick="fecharModalConvite()">×</button>
    <div id="modalConviteBody"></div>
  </div>
</div>

<script>
  const BASE_URL = "<?= BASE_URL ?>";
</script>
<script src="<?= BASE_URL ?>/assets/js/sidebar_empresa.js?v=<?= filemtime(__DIR__ . '/../assets/js/sidebar_empresa.js') ?>"></script>
<script src="<?= BASE_URL ?>/assets/js/equipe.js?v=<?= filemtime(__DIR__ . '/../assets/js/equipe.js') ?>"></script>
</body>
</html>
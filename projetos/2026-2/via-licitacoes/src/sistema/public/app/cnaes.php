<?php
require_once __DIR__ . '/../../src/config/config.php';
require_once __DIR__ . '/../../src/core/Auth.php';
Auth::exigirLogin();
$user = Auth::usuario();
?>
<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <link rel="icon" type="image/png" href="<?= BASE_URL ?>/assets/img/favicon.png">
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>CNAEs Monitorados — Via Licitações</title>
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
    <a href="<?= BASE_URL ?>/app/cnaes.php" class="active"><span class="ico">🎯</span> CNAEs Monitorados</a>
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
    <h1>CNAEs Monitorados</h1>
    <p class="dash-sub">Cadastre os CNAEs da sua empresa para receber oportunidades compatíveis.</p>
  </header>

  <div class="dash-panel">
    <h2>Adicionar CNAE</h2>
    <form id="formCnae" class="inline-form">
      <div class="form-group" style="position:relative; flex: 1;">
        <label>Buscar por código ou descrição</label>
        <input type="text" id="buscaCnae" autocomplete="off" placeholder="Ex: 6201-5/01 ou 'desenvolvimento de software'">
        <div id="sugestoesCnae" class="autocomplete-box"></div>
      </div>
      <button type="submit" class="btn btn-primary">Adicionar</button>
    </form>
    <div id="feedbackCnae" class="form-feedback" style="text-align:left; margin-top:10px;"></div>
  </div>

  <div class="dash-panel" style="margin-top:24px;">
    <h2>Meus CNAEs</h2>
    <div id="listaCnaes" class="list-box">
      <p class="empty-msg">Carregando...</p>
    </div>
  </div>
</main>

<script>
  const BASE_URL = "<?= BASE_URL ?>";
</script>
<script src="<?= BASE_URL ?>/assets/js/cnaes.js"></script>
<script src="<?= BASE_URL ?>/assets/js/sidebar_empresa.js?v=<?= filemtime(__DIR__ . '/../assets/js/sidebar_empresa.js') ?>"></script>
</body>
</html>
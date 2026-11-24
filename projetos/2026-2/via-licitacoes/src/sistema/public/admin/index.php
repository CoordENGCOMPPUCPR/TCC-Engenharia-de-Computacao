<?php
require_once __DIR__ . '/../../src/config/config.php';
require_once __DIR__ . '/../../src/core/Auth.php';

Auth::exigirAdmin();
$user = Auth::usuario();
?>
<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <link rel="icon" type="image/png" href="<?= BASE_URL ?>/assets/img/favicon.png">
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Admin — Via Licitações</title>
<link rel="stylesheet" href="<?= BASE_URL ?>/assets/css/style.css">
<link rel="stylesheet" href="<?= BASE_URL ?>/assets/css/dashboard.css">
</head>
<body class="dash-body">

<aside class="sidebar sidebar-admin">
  <div class="sidebar-logo">
    <img src="<?= BASE_URL ?>/assets/img/logo.png" alt="Via Licitações">
    <span class="admin-tag">ADMIN</span>
  </div>
  <nav class="sidebar-nav">
    <a href="<?= BASE_URL ?>/admin/index.php" class="active"><span class="ico">📊</span> Visão Geral</a>
    <a href="<?= BASE_URL ?>/admin/leads.php"><span class="ico">📥</span> Leads</a>
    <a href="<?= BASE_URL ?>/admin/usuarios.php"><span class="ico">👥</span> Usuários</a>
    <a href="<?= BASE_URL ?>/admin/empresas.php"><span class="ico">🏢</span> Empresas</a>
    <a href="<?= BASE_URL ?>/admin/licitacoes.php"><span class="ico">📋</span> Licitações</a>
    <a href="<?= BASE_URL ?>/admin/importar.php"><span class="ico">📤</span> Importar Planilha</a>    
    <a href="<?= BASE_URL ?>/admin/logs.php"><span class="ico">⚙️</span> Logs de Execução</a>
  </nav>
  <div class="sidebar-footer">
    <a href="<?= BASE_URL ?>/logout.php" class="logout-link">Sair</a>
  </div>
</aside>

<main class="dash-main">
  <header class="dash-header">
    <div>
      <h1>Painel Administrativo</h1>
      <p class="dash-sub">Bem-vindo, <?= htmlspecialchars($user['nome']) ?>.</p>
    </div>
  </header>

  <div class="cards-grid">
    <div class="card-stat"><div class="stat-ico azul">📥</div><div><span class="stat-num">—</span><span class="stat-label">Leads novos</span></div></div>
    <div class="card-stat"><div class="stat-ico verde">👥</div><div><span class="stat-num">—</span><span class="stat-label">Usuários ativos</span></div></div>
    <div class="card-stat"><div class="stat-ico amarelo">📋</div><div><span class="stat-num">—</span><span class="stat-label">Licitações no banco</span></div></div>
    <div class="card-stat"><div class="stat-ico roxo">⚙️</div><div><span class="stat-num">—</span><span class="stat-label">Execuções hoje</span></div></div>
  </div>

  <div class="dash-panel">
    <h2>Em construção</h2>
    <p>Os módulos de gestão de leads, usuários, empresas e logs serão implementados no Bloco 3.</p>
  </div>
</main>

</body>
</html>
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
<title>Meu Perfil — Via Licitações</title>
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
    <a href="<?= BASE_URL ?>/app/equipe.php"><span class="ico">👥</span> Equipe</a>
    <a href="<?= BASE_URL ?>/app/notificacoes.php"><span class="ico">🔔</span> Notificações</a>
    <a href="<?= BASE_URL ?>/app/perfil.php" class="active"><span class="ico">👤</span> Meu Perfil</a>
  </nav>
  <div class="sidebar-footer"><a href="<?= BASE_URL ?>/logout.php" class="logout-link">Sair</a></div>
</aside>

<main class="dash-main">
  <header class="dash-header">
    <h1>Meu Perfil</h1>
    <p class="dash-sub">Mantenha seus dados pessoais atualizados.</p>
  </header>

  <div class="dash-panel">
    <h2>Dados pessoais</h2>
    <form id="formPerfil" class="form-grid">
      <div class="form-group">
        <label>Nome completo *</label>
        <input type="text" name="nome" required maxlength="150" value="<?= htmlspecialchars($user['nome']) ?>">
      </div>
      <div class="form-group">
        <label>E-mail *</label>
        <input type="email" name="email" required maxlength="150" value="<?= htmlspecialchars($user['email']) ?>">
      </div>
      <div class="form-group">
        <label>Telefone</label>
        <input type="text" name="telefone" maxlength="20">
      </div>
      <div class="form-actions" style="grid-column:1/-1;">
        <button type="submit" class="btn btn-primary">Salvar dados</button>
      </div>
      <div id="feedbackPerfil" class="form-feedback" style="grid-column:1/-1;"></div>
    </form>
  </div>

  <div class="dash-panel" style="margin-top:24px;">
    <h2>Alterar senha</h2>
    <form id="formSenha" class="form-grid">
      <div class="form-group">
        <label>Senha atual *</label>
        <input type="password" name="senha_atual" required autocomplete="current-password">
      </div>
      <div class="form-group">
        <label>Nova senha * (mín. 6 caracteres)</label>
        <input type="password" name="senha_nova" required minlength="6" autocomplete="new-password">
      </div>
      <div class="form-group">
        <label>Confirmar nova senha *</label>
        <input type="password" name="senha_confirma" required minlength="6" autocomplete="new-password">
      </div>
      <div class="form-actions" style="grid-column:1/-1;">
        <button type="submit" class="btn btn-primary">Alterar senha</button>
      </div>
      <div id="feedbackSenha" class="form-feedback" style="grid-column:1/-1;"></div>
    </form>
  </div>
</main>

<script>
  const BASE_URL = "<?= BASE_URL ?>";
</script>
<script src="<?= BASE_URL ?>/assets/js/sidebar_empresa.js?v=<?= filemtime(__DIR__ . '/../assets/js/sidebar_empresa.js') ?>"></script>
<script src="<?= BASE_URL ?>/assets/js/perfil.js?v=<?= filemtime(__DIR__ . '/../assets/js/perfil.js') ?>"></script>
</body>
</html>
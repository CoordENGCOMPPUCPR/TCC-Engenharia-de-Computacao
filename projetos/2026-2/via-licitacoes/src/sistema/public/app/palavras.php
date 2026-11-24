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
<title>Palavras de Interesse — Via Licitações</title>
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
    <a href="<?= BASE_URL ?>/app/palavras.php" class="active"><span class="ico">🎯</span> Palavras de Interesse</a>
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
    <h1>Palavras de Interesse</h1>
    <p class="dash-sub">Cadastre palavras ou frases que aparecem no objeto das licitações que interessam à sua empresa.</p>
  </header>

  <div class="dash-panel">
    <h2>Adicionar palavra ou frase</h2>
    <form id="formPalavra" class="inline-form">
      <div class="form-group" style="flex:1;">
        <label>Palavra ou frase</label>
        <input type="text" id="palavraInput" autocomplete="off" maxlength="120"
               placeholder="Ex: software, merenda escolar, obra de pavimentação...">
      </div>
      <button type="submit" class="btn btn-primary">Adicionar</button>
    </form>
    <div id="feedbackPalavra" class="form-feedback" style="text-align:left; margin-top:10px;"></div>

    <div class="sugestoes-box" style="margin-top:18px;">
      <span class="sugestoes-label">Sugestões rápidas:</span>
      <div class="sugestoes-chips" id="sugestoesChips">
        <button type="button" class="chip-sugestao" data-p="software">software</button>
        <button type="button" class="chip-sugestao" data-p="merenda">merenda</button>
        <button type="button" class="chip-sugestao" data-p="obra">obra</button>
        <button type="button" class="chip-sugestao" data-p="material de escritório">material de escritório</button>
        <button type="button" class="chip-sugestao" data-p="ar-condicionado">ar-condicionado</button>
        <button type="button" class="chip-sugestao" data-p="medicamento">medicamento</button>
        <button type="button" class="chip-sugestao" data-p="transporte">transporte</button>
        <button type="button" class="chip-sugestao" data-p="uniforme">uniforme</button>
      </div>
    </div>
  </div>

  <div class="dash-panel" style="margin-top:24px;">
    <h2>Minhas palavras monitoradas</h2>
    <div id="listaPalavras" class="list-box">
      <p class="empty-msg">Carregando...</p>
    </div>
  </div>
</main>

<script>
  const BASE_URL = "<?= BASE_URL ?>";
</script>
<script src="<?= BASE_URL ?>/assets/js/sidebar_empresa.js?v=<?= filemtime(__DIR__ . '/../assets/js/sidebar_empresa.js') ?>"></script>
<script src="<?= BASE_URL ?>/assets/js/palavras.js?v=<?= filemtime(__DIR__ . '/../assets/js/palavras.js') ?>"></script>
</body>
</html>
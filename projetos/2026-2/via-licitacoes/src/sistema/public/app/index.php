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
<title>Dashboard — Via Licitações</title>
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
    <a href="<?= BASE_URL ?>/app/index.php" class="active"><span class="ico">📊</span> Dashboard</a>
    <a href="<?= BASE_URL ?>/app/licitacoes.php"><span class="ico">📋</span> Licitações</a>
    <a href="<?= BASE_URL ?>/app/interesses.php"><span class="ico">⭐</span> Meus Interesses</a>
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
    <div>
      <h1 id="saudacao">Olá 👋</h1>
      <p class="dash-sub" id="subtitulo">Carregando painel...</p>
    </div>
    <div class="header-acoes">
      <a href="<?= BASE_URL ?>/app/licitacoes.php" class="btn btn-primary">Ver licitações</a>
    </div>
  </header>

  <!-- ===================== KPIs ===================== -->
  <section class="kpi-grid">
    <a href="<?= BASE_URL ?>/app/licitacoes.php" class="kpi-card kpi-azul">
      <div class="kpi-icon">📋</div>
      <div class="kpi-body">
        <span class="kpi-num" id="kpiTotalLicitacoes">—</span>
        <span class="kpi-label">Licitações no sistema</span>
      </div>
    </a>

    <a href="<?= BASE_URL ?>/app/licitacoes.php" class="kpi-card kpi-verde">
      <div class="kpi-icon">✓</div>
      <div class="kpi-body">
        <span class="kpi-num" id="kpiTotalMatch">—</span>
        <span class="kpi-label">De acordo com seus interesses</span>
      </div>
    </a>

    <a href="<?= BASE_URL ?>/app/interesses.php" class="kpi-card kpi-amarelo">
      <div class="kpi-icon">⭐</div>
      <div class="kpi-body">
        <span class="kpi-num" id="kpiInteresses">—</span>
        <span class="kpi-label">Licitações salvas</span>
      </div>
    </a>

    <a href="<?= BASE_URL ?>/app/interesses.php" class="kpi-card kpi-roxo">
      <div class="kpi-icon">💰</div>
      <div class="kpi-body">
        <span class="kpi-num" id="kpiValorDisputa">—</span>
        <span class="kpi-label">Valor em disputa</span>
      </div>
    </a>

    <div class="kpi-card kpi-vermelho">
      <div class="kpi-icon">⏰</div>
      <div class="kpi-body">
        <span class="kpi-num" id="kpiEncerrando">—</span>
        <span class="kpi-label">Encerram em 7 dias</span>
      </div>
    </div>

    <a href="<?= BASE_URL ?>/app/interesses.php" class="kpi-card kpi-cinza">
      <div class="kpi-icon">☑️</div>
      <div class="kpi-body">
        <span class="kpi-num" id="kpiTarefas">—</span>
        <span class="kpi-label">Tarefas pendentes</span>
      </div>
    </a>
  </section>

  <!-- ===================== GRID PRINCIPAL ===================== -->
  <div class="dash-grid-2">

    <!-- Palavras de interesse -->
    <div class="dash-block">
      <div class="dash-block-head">
        <h2>🎯 Palavras de interesse</h2>
        <a href="<?= BASE_URL ?>/app/palavras.php" class="dash-link">Gerenciar →</a>
      </div>
      <div id="listaPalavras" class="mini-list">
        <p class="empty-msg">Carregando...</p>
      </div>
    </div>

    <!-- Regiões -->
    <div class="dash-block">
      <div class="dash-block-head">
        <h2>📍 Regiões de interesse</h2>
        <a href="<?= BASE_URL ?>/app/regioes.php" class="dash-link">Gerenciar →</a>
      </div>
      <div id="listaRegioes" class="mini-list">
        <p class="empty-msg">Carregando...</p>
      </div>
    </div>
  </div>

  <!-- ===================== PIPELINE ===================== -->
  <div class="dash-block">
    <div class="dash-block-head">
      <h2>📊 Pipeline de disputas</h2>
      <a href="<?= BASE_URL ?>/app/interesses.php" class="dash-link">Ver tudo →</a>
    </div>
    <div id="pipeline" class="pipeline">
      <p class="empty-msg">Carregando...</p>
    </div>
  </div>

  <div class="dash-grid-2">

    <!-- Tarefas pendentes -->
    <div class="dash-block">
      <div class="dash-block-head">
        <h2>☑️ Próximas tarefas</h2>
        <a href="<?= BASE_URL ?>/app/interesses.php" class="dash-link">Ver todas →</a>
      </div>
      <div id="tarefasPendentes" class="mini-list">
        <p class="empty-msg">Carregando...</p>
      </div>
    </div>

    <!-- Urgentes -->
    <div class="dash-block">
      <div class="dash-block-head">
        <h2>⏰ Encerrando em 7 dias</h2>
        <a href="<?= BASE_URL ?>/app/licitacoes.php" class="dash-link">Ver todas →</a>
      </div>
      <div id="licitacoesUrgentes" class="mini-list">
        <p class="empty-msg">Carregando...</p>
      </div>
    </div>
  </div>

  <!-- ===================== ATIVIDADE RECENTE ===================== -->
  <div class="dash-block">
    <div class="dash-block-head">
      <h2>💬 Atividade recente</h2>
    </div>
    <div id="atividadeRecente" class="atividade-list">
      <p class="empty-msg">Carregando...</p>
    </div>
  </div>

</main>

<script>
  const BASE_URL = "<?= BASE_URL ?>";
</script>
<script src="<?= BASE_URL ?>/assets/js/sidebar_empresa.js?v=<?= filemtime(__DIR__ . '/../assets/js/sidebar_empresa.js') ?>"></script>
<script src="<?= BASE_URL ?>/assets/js/dashboard.js?v=<?= filemtime(__DIR__ . '/../assets/js/dashboard.js') ?>"></script>
</body>
</html>
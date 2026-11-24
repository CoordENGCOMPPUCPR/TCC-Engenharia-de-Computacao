<?php
require_once __DIR__ . '/../../src/config/config.php';
require_once __DIR__ . '/../../src/config/importadores.php';
require_once __DIR__ . '/../../src/core/Auth.php';
Auth::exigirAdmin();
$user = Auth::usuario();
?>
<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Importar Planilha — Admin Via Licitações</title>
<link rel="icon" type="image/png" href="<?= BASE_URL ?>/assets/img/favicon.png">
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
    <a href="<?= BASE_URL ?>/admin/index.php"><span class="ico">📊</span> Visão Geral</a>
    <a href="<?= BASE_URL ?>/admin/leads.php"><span class="ico">📥</span> Leads</a>
    <a href="<?= BASE_URL ?>/admin/usuarios.php"><span class="ico">👥</span> Usuários</a>
    <a href="<?= BASE_URL ?>/admin/empresas.php"><span class="ico">🏢</span> Empresas</a>
    <a href="<?= BASE_URL ?>/admin/licitacoes.php"><span class="ico">📋</span> Licitações</a>
    <a href="<?= BASE_URL ?>/admin/importar.php" class="active"><span class="ico">📤</span> Importar Planilha</a>
    <a href="<?= BASE_URL ?>/admin/logs.php"><span class="ico">⚙️</span> Logs de Execução</a>
  </nav>
  <div class="sidebar-footer"><a href="<?= BASE_URL ?>/logout.php" class="logout-link">Sair</a></div>
</aside>

<main class="dash-main">
  <header class="dash-header">
    <h1>Importar Planilha de Licitações</h1>
    <p class="dash-sub">Escolha o formato, envie o arquivo e confira o preview antes de confirmar.</p>
  </header>

  <!-- 1. Formato -->
  <div class="dash-panel">
    <h2>1. Formato da planilha</h2>
    <div class="formato-grid" id="formatoGrid">
      <?php foreach ($IMPORTADORES as $chave => $c): ?>
        <label class="formato-card <?= $chave === 'PNCP' ? 'active' : '' ?>" data-chave="<?= htmlspecialchars($chave) ?>">
          <input type="radio" name="formato" value="<?= htmlspecialchars($chave) ?>" <?= $chave === 'PNCP' ? 'checked' : '' ?>>
          <strong><?= htmlspecialchars($c['nome']) ?></strong>
          <small><?= htmlspecialchars($c['descricao']) ?></small>
        </label>
      <?php endforeach; ?>
    </div>
  </div>

  <!-- 2. Upload -->
  <div class="dash-panel" style="margin-top:24px;">
    <h2>2. Selecione o arquivo</h2>
    <form id="formUpload" enctype="multipart/form-data">
      <div class="upload-area" id="uploadArea">
        <div class="upload-icon">📤</div>
        <p>Arraste o arquivo aqui ou <strong>clique para selecionar</strong></p>
        <small>Formatos aceitos: .xlsx, .xls, .csv (máx. 20 MB)</small>
        <input type="file" id="arquivoInput" name="arquivo" accept=".xlsx,.xls,.csv" hidden>
      </div>
      <div id="arquivoSelecionado" class="arquivo-selecionado" style="display:none;"></div>
      <div id="feedbackUpload" class="form-feedback" style="margin-top:12px;"></div>
    </form>
  </div>

  <!-- 3. Preview -->
  <div class="dash-panel" id="previewPanel" style="margin-top:24px; display:none;">
    <div class="panel-head">
      <h2>3. Preview dos dados</h2>
      <span id="contadorPreview" class="contador">0</span>
    </div>
    <p class="dash-sub" style="margin-bottom:16px;">
      Confira abaixo as primeiras linhas. Se estiver tudo certo, confirme a importação.
    </p>
    <div class="tabela-wrapper" style="max-height:500px; overflow:auto;">
      <table class="tabela" id="tabelaPreview"></table>
    </div>
    <div class="form-actions" style="margin-top:20px; display:flex; justify-content:flex-end; gap:10px; flex-wrap:wrap;">
      <button type="button" class="btn btn-ghost" onclick="cancelarPreview()">Cancelar</button>
      <button type="button" class="btn btn-primary" id="btnConfirmar" onclick="confirmarImportacao()">
        Confirmar importação
      </button>
    </div>
    <div id="feedbackImport" class="form-feedback" style="margin-top:12px;"></div>
  </div>
</main>

<script>
  const BASE_URL = "<?= BASE_URL ?>";
</script>
<script src="<?= BASE_URL ?>/assets/js/admin_importar.js?v=<?= filemtime(__DIR__ . '/../assets/js/admin_importar.js') ?>"></script>
</body>
</html>
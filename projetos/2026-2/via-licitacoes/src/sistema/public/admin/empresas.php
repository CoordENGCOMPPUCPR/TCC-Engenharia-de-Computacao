<?php
require_once __DIR__ . '/../../src/config/config.php';
require_once __DIR__ . '/../../src/core/Auth.php';
Auth::exigirAdmin();
$user = Auth::usuario();
?>
<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Empresas — Admin Via Licitações</title>
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
    <a href="<?= BASE_URL ?>/admin/empresas.php" class="active"><span class="ico">🏢</span> Empresas</a>
    <a href="<?= BASE_URL ?>/admin/licitacoes.php"><span class="ico">📋</span> Licitações</a>
    <a href="<?= BASE_URL ?>/admin/importar.php"><span class="ico">📤</span> Importar Planilha</a>
    <a href="<?= BASE_URL ?>/admin/logs.php"><span class="ico">⚙️</span> Logs de Execução</a>
  </nav>
  <div class="sidebar-footer"><a href="<?= BASE_URL ?>/logout.php" class="logout-link">Sair</a></div>
</aside>

<main class="dash-main">
  <header class="dash-header">
    <h1>Empresas</h1>
    <p class="dash-sub">Todas as empresas cadastradas pelos usuários da plataforma.</p>
  </header>

  <div class="dash-panel">
    <div class="filtros-grid-leads">
      <div class="form-group">
        <label>Buscar</label>
        <input type="text" id="filtroBusca" placeholder="Razão social, CNPJ, e-mail do responsável...">
      </div>
      <div class="form-group">
        <label>UF</label>
        <select id="filtroUf"><option value="">Todas</option></select>
      </div>
      <div class="filtros-actions">
        <button class="btn btn-primary" onclick="carregar(1)">Filtrar</button>
        <button class="btn btn-ghost" onclick="limparFiltros()">Limpar</button>
      </div>
    </div>
  </div>

  <div class="dash-panel" style="margin-top:24px;">
    <div class="panel-head">
      <h2>Empresas cadastradas</h2>
      <span id="contadorEmpresas" class="contador">0</span>
    </div>
    <div class="tabela-wrapper">
      <table class="tabela">
          <thead>
            <tr>
              <th>Razão Social</th>
              <th>CNPJ</th>
              <th>Responsável principal</th>
              <th>Usuários</th>
              <th>Localização</th>
              <th style="text-align:right;">Ações</th>
            </tr>
          </thead>
        <tbody id="tbodyEmpresas">
          <tr><td colspan="5" class="empty-msg">Carregando...</td></tr>
        </tbody>
      </table>
    </div>
    <div class="paginacao" id="paginacao"></div>
  </div>
</main>

<div id="modalEmpresa" class="modal">
  <div class="modal-backdrop" onclick="fecharModalEmpresa()"></div>
  <div class="modal-content modal-lg">
    <button class="modal-close" onclick="fecharModalEmpresa()">×</button>
    <div id="modalEmpresaBody"></div>
  </div>
</div>

<script>
  const BASE_URL = "<?= BASE_URL ?>";
</script>
<script src="<?= BASE_URL ?>/assets/js/admin_empresas.js?v=<?= filemtime(__DIR__ . '/../assets/js/admin_empresas.js') ?>"></script>
</body>
</html>
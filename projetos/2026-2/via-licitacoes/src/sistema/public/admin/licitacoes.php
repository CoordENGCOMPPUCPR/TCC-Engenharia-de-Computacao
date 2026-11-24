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
<title>Licitações — Admin Via Licitações</title>
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
    <a href="<?= BASE_URL ?>/admin/licitacoes.php" class="active"><span class="ico">📋</span> Licitações</a>
    <a href="<?= BASE_URL ?>/admin/importar.php"><span class="ico">📤</span> Importar Planilha</a>
    <a href="<?= BASE_URL ?>/admin/logs.php"><span class="ico">⚙️</span> Logs de Execução</a>
  </nav>
  <div class="sidebar-footer"><a href="<?= BASE_URL ?>/logout.php" class="logout-link">Sair</a></div>
</aside>

<main class="dash-main">
  <header class="dash-header">
    <div style="display:flex; justify-content:space-between; align-items:flex-start; flex-wrap:wrap; gap:14px;">
      <div>
        <h1>Licitações</h1>
        <p class="dash-sub">Todas as licitações importadas e coletadas pela plataforma.</p>
      </div>
      <a href="<?= BASE_URL ?>/admin/importar.php" class="btn btn-primary">+ Importar planilha</a>
    </div>
  </header>

  <!-- Filtros -->
  <div class="dash-panel">
    <div class="filtros-grid-leads">
      <div class="form-group">
        <label>Buscar</label>
        <input type="text" id="filtroBusca" placeholder="Objeto, número, órgão...">
      </div>
      <div class="form-group">
        <label>UF</label>
        <select id="filtroUf"><option value="">Todas</option></select>
      </div>
      <div class="form-group">
        <label>Situação</label>
        <select id="filtroSituacao">
          <option value="">Todas</option>
          <option value="Divulgada no PNCP">Divulgada no PNCP</option>
          <option value="Suspensa">Suspensa</option>
          <option value="Revogada">Revogada</option>
          <option value="Anulada">Anulada</option>
        </select>
      </div>
      <div class="form-group">
        <label>Modalidade</label>
        <select id="filtroModalidade">
          <option value="">Todas</option>
          <option value="Pregão - Eletrônico">Pregão Eletrônico</option>
          <option value="Pregão - Presencial">Pregão Presencial</option>
          <option value="Concorrência - Eletrônica">Concorrência Eletrônica</option>
          <option value="Concorrência - Presencial">Concorrência Presencial</option>
        </select>
      </div>
      <div class="filtros-actions">
        <button class="btn btn-primary" onclick="carregar(1)">Filtrar</button>
        <button class="btn btn-ghost" onclick="limparFiltros()">Limpar</button>
      </div>
    </div>
  </div>

  <!-- Tabela -->
  <div class="dash-panel" style="margin-top:24px;">
    <div class="panel-head">
      <h2>Licitações cadastradas</h2>
      <span id="contadorLicitacoes" class="contador">0</span>
    </div>
    <div class="tabela-wrapper">
      <table class="tabela">
        <thead>
          <tr>
            <th>Edital</th>
            <th>Órgão</th>
            <th>Localidade</th>
            <th>Modalidade</th>
            <th>Situação</th>
            <th>Início Propostas</th>
            <th>Fim Propostas</th>
            <th>Valor Estimado</th>
            <th style="text-align:right;">Ações</th>
          </tr>
        </thead>
        <tbody id="tbodyLicitacoes">
          <tr><td colspan="9" class="empty-msg">Carregando...</td></tr>
        </tbody>
      </table>
    </div>
    <div class="paginacao" id="paginacao"></div>
  </div>
</main>

<!-- Modal detalhes -->
<div id="modalLicitacao" class="modal">
  <div class="modal-backdrop" onclick="fecharModalLicitacao()"></div>
  <div class="modal-content modal-lg">
    <button class="modal-close" onclick="fecharModalLicitacao()">×</button>
    <div id="modalLicitacaoBody"></div>
  </div>
</div>

<script>
  const BASE_URL = "<?= BASE_URL ?>";
</script>
<script src="<?= BASE_URL ?>/assets/js/admin_licitacoes.js?v=<?= filemtime(__DIR__ . '/../assets/js/admin_licitacoes.js') ?>"></script>
</body>
</html>
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
<title>Leads — Admin Via Licitações</title>
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
    <a href="<?= BASE_URL ?>/admin/leads.php" class="active"><span class="ico">📥</span> Leads</a>
    <a href="<?= BASE_URL ?>/admin/usuarios.php"><span class="ico">👥</span> Usuários</a>
    <a href="<?= BASE_URL ?>/admin/empresas.php"><span class="ico">🏢</span> Empresas</a>
    <a href="<?= BASE_URL ?>/admin/licitacoes.php"><span class="ico">📋</span> Licitações</a>
    <a href="<?= BASE_URL ?>/admin/importar.php"><span class="ico">📤</span> Importar Planilha</a>
    <a href="<?= BASE_URL ?>/admin/logs.php"><span class="ico">⚙️</span> Logs de Execução</a>
  </nav>
  <div class="sidebar-footer"><a href="<?= BASE_URL ?>/logout.php" class="logout-link">Sair</a></div>
</aside>

<main class="dash-main">
  <header class="dash-header">
    <h1>Leads</h1>
    <p class="dash-sub">Cadastros recebidos pela landing page. Gerencie o funil comercial.</p>
  </header>

  <!-- Resumo do funil -->
  <div class="cards-grid" id="cardsFunil">
    <div class="card-stat" data-status="LEAD NOVO">
      <div class="stat-ico azul">🆕</div>
      <div><span class="stat-num" id="qtdLeadNovo">—</span><span class="stat-label">Lead Novo</span></div>
    </div>
    <div class="card-stat" data-status="EM NEGOCIACAO">
      <div class="stat-ico amarelo">💬</div>
      <div><span class="stat-num" id="qtdEmNegociacao">—</span><span class="stat-label">Em Negociação</span></div>
    </div>
    <div class="card-stat" data-status="CLIENTE ATIVO">
      <div class="stat-ico verde">✅</div>
      <div><span class="stat-num" id="qtdClienteAtivo">—</span><span class="stat-label">Cliente Ativo</span></div>
    </div>
    <div class="card-stat" data-status="DESISTENCIA">
      <div class="stat-ico roxo">🚫</div>
      <div><span class="stat-num" id="qtdDesistencia">—</span><span class="stat-label">Desistência</span></div>
    </div>
  </div>

  <!-- Filtro -->
  <div class="dash-panel">
    <div class="panel-head">
      <h2>Filtrar leads</h2>
    </div>
    <div class="filtros-grid-leads">
      <div class="form-group">
        <label>Buscar</label>
        <input type="text" id="filtroBusca" placeholder="Nome, e-mail, CNPJ...">
      </div>
      <div class="form-group">
        <label>Status</label>
        <select id="filtroStatus">
          <option value="">Todos</option>
          <option value="LEAD NOVO">Lead Novo</option>
          <option value="EM NEGOCIACAO">Em Negociação</option>
          <option value="CLIENTE ATIVO">Cliente Ativo</option>
          <option value="DESISTENCIA">Desistência</option>
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
      <h2>Leads cadastrados</h2>
      <span id="contadorLeads" class="contador">0</span>
    </div>
    <div class="tabela-wrapper">
      <table class="tabela">
        <thead>
          <tr>
            <th>Nome</th>
            <th>Contato</th>
            <th>CNPJ</th>
            <th>Enviado em</th>
            <th>Status</th>
            <th style="text-align:right;">Ações</th>
          </tr>
        </thead>
        <tbody id="tbodyLeads">
          <tr><td colspan="6" class="empty-msg">Carregando...</td></tr>
        </tbody>
      </table>
    </div>
    <div class="paginacao" id="paginacao"></div>
  </div>
</main>

<!-- Modal lead -->
<div id="modalLead" class="modal">
  <div class="modal-backdrop" onclick="fecharModalLead()"></div>
  <div class="modal-content modal-lg">
    <button class="modal-close" onclick="fecharModalLead()">×</button>
    <div id="modalLeadBody"></div>
  </div>
</div>

<script>
  const BASE_URL = "<?= BASE_URL ?>";
</script>
<script src="<?= BASE_URL ?>/assets/js/admin_leads.js"></script>
</body>
</html>
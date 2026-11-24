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
<title>Usuários — Admin Via Licitações</title>
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
    <a href="<?= BASE_URL ?>/admin/usuarios.php" class="active"><span class="ico">👥</span> Usuários</a>
    <a href="<?= BASE_URL ?>/admin/empresas.php"><span class="ico">🏢</span> Empresas</a>
    <a href="<?= BASE_URL ?>/admin/licitacoes.php"><span class="ico">📋</span> Licitações</a>
    <a href="<?= BASE_URL ?>/admin/importar.php"><span class="ico">📤</span> Importar Planilha</a>
    <a href="<?= BASE_URL ?>/admin/logs.php"><span class="ico">⚙️</span> Logs de Execução</a>
  </nav>
  <div class="sidebar-footer"><a href="<?= BASE_URL ?>/logout.php" class="logout-link">Sair</a></div>
</aside>

<main class="dash-main">
  <header class="dash-header">
    <div style="display:flex; justify-content:space-between; align-items:flex-start; flex-wrap:wrap; gap:14px;">
      <div>
        <h1>Usuários</h1>
        <p class="dash-sub">Gerencie os acessos à plataforma.</p>
      </div>
      <button class="btn btn-primary" onclick="abrirModalNovoUsuario()">+ Novo usuário</button>
    </div>
  </header>

  <div class="dash-panel">
    <div class="filtros-grid-leads">
      <div class="form-group">
        <label>Buscar</label>
        <input type="text" id="filtroBusca" placeholder="Nome ou e-mail...">
      </div>
      <div class="form-group">
        <label>Tipo</label>
        <select id="filtroTipo">
          <option value="">Todos</option>
          <option value="comum">Comum</option>
          <option value="admin">Admin</option>
        </select>
      </div>
      <div class="form-group">
        <label>Status</label>
        <select id="filtroStatus">
          <option value="">Todos</option>
          <option value="ativo">Ativo</option>
          <option value="inativo">Inativo</option>
          <option value="pendente">Pendente</option>
        </select>
      </div>
      <div class="filtros-actions">
        <button class="btn btn-primary" onclick="carregar(1)">Filtrar</button>
        <button class="btn btn-ghost" onclick="limparFiltros()">Limpar</button>
      </div>
    </div>
  </div>

  <div class="dash-panel" style="margin-top:24px;">
    <div class="panel-head">
      <h2>Usuários cadastrados</h2>
      <span id="contadorUsuarios" class="contador">0</span>
    </div>
    <div class="tabela-wrapper">
      <table class="tabela">
        <thead>
          <tr>
            <th>Nome</th>
            <th>E-mail</th>
            <th>Tipo</th>
            <th>Status</th>
            <th>Empresa</th>
            <th>Último acesso</th>
            <th style="text-align:right;">Ações</th>
          </tr>
        </thead>
        <tbody id="tbodyUsuarios">
          <tr><td colspan="7" class="empty-msg">Carregando...</td></tr>
        </tbody>
      </table>
    </div>
    <div class="paginacao" id="paginacao"></div>
  </div>
</main>

<!-- Modal usuário (criar/editar) -->
<div id="modalUsuario" class="modal">
  <div class="modal-backdrop" onclick="fecharModalUsuario()"></div>
  <div class="modal-content modal-lg">
    <button class="modal-close" onclick="fecharModalUsuario()">×</button>
    <div id="modalUsuarioBody"></div>
  </div>
</div>

<script>
  const BASE_URL = "<?= BASE_URL ?>";
</script>
<script src="<?= BASE_URL ?>/assets/js/admin_usuarios.js?v=<?= filemtime(__DIR__ . '/../assets/js/admin_usuarios.js') ?>"></script>
</body>
</html>
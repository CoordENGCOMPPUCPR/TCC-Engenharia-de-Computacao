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
<title>Licitações — Via Licitações</title>
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
    <a href="<?= BASE_URL ?>/app/licitacoes.php" class="active"><span class="ico">📋</span> Licitações</a>
    <a href="<?= BASE_URL ?>/app/interesses.php"><span class="ico">⭐</span> Meus Interesses</a>
    <a href="<?= BASE_URL ?>/app/palavras.php"><span class="ico">🎯</span> Palavras de Interesse</a>    <a href="<?= BASE_URL ?>/app/regioes.php"><span class="ico">📍</span> Regiões</a>
    <a href="<?= BASE_URL ?>/app/empresa.php"><span class="ico">🏢</span> Minha Empresa</a>
    <a href="<?= BASE_URL ?>/app/equipe.php"><span class="ico">👥</span> Equipe</a>
    <a href="<?= BASE_URL ?>/app/notificacoes.php"><span class="ico">🔔</span> Notificações</a>
    <a href="<?= BASE_URL ?>/app/perfil.php"><span class="ico">👤</span> Meu Perfil</a>
  </nav>
  <div class="sidebar-footer"><a href="<?= BASE_URL ?>/logout.php" class="logout-link">Sair</a></div>
</aside>

<main class="dash-main">
  <header class="dash-header">
    <h1>Licitações Disponíveis</h1>
    <p class="dash-sub">Pesquise, filtre e marque as oportunidades que interessam à sua empresa.</p>
  </header>

  <!-- Filtros -->
<form id="formFiltros" class="filtros-grid">
  <div class="form-group">
    <label>Palavra-chave livre</label>
    <input type="text" id="filtroBusca" placeholder="Ex: software, merenda, obra...">
  </div>
  <div class="form-group">
    <label>UF</label>
    <select id="filtroUf"><option value="">Todas</option></select>
  </div>
  <div class="form-group">
    <label>Publicado a partir de</label>
    <input type="date" id="filtroData">
  </div>
  <div class="form-group">
    <label>Ordenar por</label>
    <select id="filtroOrdem">
      <option value="recentes">Mais recentes</option>
      <option value="valor">Maior valor</option>
      <option value="abertura">Data de abertura</option>
    </select>
  </div>
  <div class="filtros-actions">
    <button type="submit" class="btn btn-primary">Filtrar</button>
    <button type="button" class="btn btn-ghost" onclick="limparFiltros()">Limpar</button>
  </div>
</form>

<!-- Painel de interesses combináveis -->
<div class="interesses-filtro-box" id="interessesBox">
  <div class="ifb-header">
    <div>
      <strong>🎯 Filtrar pelos meus interesses</strong>
      <span class="ifb-hint">Marque palavras-chave e/ou regiões para cruzar. Sem marcar nada = todos os resultados.</span>
    </div>
    <button type="button" class="btn-limpar-interesses" id="btnLimparInteresses">Limpar seleção</button>
  </div>

  <div class="ifb-colunas">
    <div class="ifb-coluna">
      <span class="ifb-label">PALAVRAS-CHAVE</span>
      <div class="ifb-chips" id="ifbPalavras">
        <p class="empty-msg">Carregando...</p>
      </div>
    </div>
    <div class="ifb-coluna">
      <span class="ifb-label">REGIÕES</span>
      <div class="ifb-chips" id="ifbRegioes">
        <p class="empty-msg">Carregando...</p>
      </div>
    </div>
  </div>

  <div class="ifb-resumo" id="ifbResumo" style="display:none;"></div>
</div>

  <!-- Resultados -->
  <div class="dash-panel" style="margin-top:24px;">
    <div class="panel-head">
      <h2>Resultados</h2>
      <span id="contadorResultados" class="contador">0</span>
    </div>
    <div id="listaLicitacoes" class="licitacoes-lista">
      <p class="empty-msg">Carregando...</p>
    </div>
    <div class="paginacao" id="paginacao"></div>
  </div>
</main>

<!-- Modal Detalhes do Edital -->
<div id="modalLicitacao" class="modal">
  <div class="modal-backdrop" onclick="fecharModalLicitacao()"></div>
  <div class="modal-content modal-xl">
    <button class="modal-close" onclick="fecharModalLicitacao()">×</button>
    <div id="modalLicitacaoBody"></div>
  </div>
</div>

<script>
  const BASE_URL = "<?= BASE_URL ?>";
</script>
<script src="<?= BASE_URL ?>/assets/js/sidebar_empresa.js?v=<?= filemtime(__DIR__ . '/../assets/js/sidebar_empresa.js') ?>"></script>
<script src="<?= BASE_URL ?>/assets/js/licitacoes.js?v=<?= filemtime(__DIR__ . '/../assets/js/licitacoes.js') ?>"></script>
</body>
</html>
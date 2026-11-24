<?php
require_once __DIR__ . '/../../src/config/config.php';
require_once __DIR__ . '/../../src/config/database.php';
require_once __DIR__ . '/../../src/core/Auth.php';
Auth::exigirLogin();
$user = Auth::usuario();

$db = Database::getConnection();
$stmt = $db->prepare("
    SELECT e.*
    FROM empresas e
    INNER JOIN usuarios u ON u.id_empresa = e.id
    WHERE u.id = ?
    LIMIT 1
");
$stmt->execute([$user['id']]);
$empresa = $stmt->fetch();
?>
<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Minha Empresa — Via Licitações</title>
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
    <a href="<?= BASE_URL ?>/app/empresa.php" class="active"><span class="ico">🏢</span> Minha Empresa</a>
    <a href="<?= BASE_URL ?>/app/equipe.php"><span class="ico">👥</span> Equipe</a>
    <a href="<?= BASE_URL ?>/app/notificacoes.php"><span class="ico">🔔</span> Notificações</a>
    <a href="<?= BASE_URL ?>/app/perfil.php"><span class="ico">👤</span> Meu Perfil</a>
  </nav>
  <div class="sidebar-footer"><a href="<?= BASE_URL ?>/logout.php" class="logout-link">Sair</a></div>
</aside>

<main class="dash-main">
  <header class="dash-header">
    <h1>Minha Empresa</h1>
    <p class="dash-sub">Digite o CNPJ para preencher automaticamente os dados públicos.</p>
  </header>

  <div class="dash-panel">
    <h2><?= $empresa ? 'Editar dados' : 'Cadastrar empresa' ?></h2>
    <form id="formEmpresa" class="form-grid">
      <div class="form-group" style="grid-column:1/-1;">
        <label>CNPJ *</label>
        <div style="display:flex; gap:10px; align-items:stretch; flex-wrap:wrap;">
          <input type="text" name="cnpj" id="cnpjInput" required maxlength="18"
                 value="<?= htmlspecialchars($empresa['cnpj'] ?? '') ?>" style="flex:1; min-width:200px;">
          <button type="button" class="btn btn-primary" id="btnBuscarCnpj">Buscar dados</button>
        </div>
        <div id="feedbackCnpj" class="form-feedback" style="text-align:left; margin-top:6px;"></div>
      </div>

      <div class="form-group">
        <label>Razão Social *</label>
        <input type="text" name="razao_social" id="razaoInput" required maxlength="200"
               value="<?= htmlspecialchars($empresa['razao_social'] ?? '') ?>">
      </div>
      <div class="form-group">
        <label>Nome Fantasia</label>
        <input type="text" name="nome_fantasia" id="fantasiaInput" maxlength="200"
               value="<?= htmlspecialchars($empresa['nome_fantasia'] ?? '') ?>">
      </div>

      <div class="form-group">
        <label>Natureza Jurídica</label>
        <input type="text" name="natureza_juridica" id="naturezaInput" maxlength="100"
               value="<?= htmlspecialchars($empresa['natureza_juridica'] ?? '') ?>">
      </div>
      <div class="form-group">
        <label>CNAE Principal</label>
        <input type="text" name="cnae_principal" id="cnaeInput" maxlength="20"
               value="<?= htmlspecialchars($empresa['cnae_principal'] ?? '') ?>">
      </div>

      <div class="form-group">
        <label>Telefone</label>
        <input type="text" name="telefone" id="telefoneInput" maxlength="20"
               value="<?= htmlspecialchars($empresa['telefone'] ?? '') ?>">
      </div>
      <div class="form-group">
        <label>E-mail de contato</label>
        <input type="email" name="email_contato" id="emailInput" maxlength="150"
               value="<?= htmlspecialchars($empresa['email_contato'] ?? '') ?>">
      </div>

      <div class="form-group" style="grid-column:1/-1;">
        <label>Endereço</label>
        <input type="text" name="endereco" id="enderecoInput" maxlength="255"
               value="<?= htmlspecialchars($empresa['endereco'] ?? '') ?>">
      </div>

      <div class="form-group">
        <label>UF</label>
        <input type="text" name="uf" id="ufInput" maxlength="2" style="text-transform:uppercase;"
               value="<?= htmlspecialchars($empresa['uf'] ?? '') ?>">
      </div>
      <div class="form-group">
        <label>Município</label>
        <input type="text" name="municipio" id="municipioInput" maxlength="100"
               value="<?= htmlspecialchars($empresa['municipio'] ?? '') ?>">
      </div>

      <div id="boxSugestoesCnaes" style="grid-column:1/-1; display:none;">
        <label style="font-size:13px; font-weight:600; color:#334155; display:block; margin-bottom:8px;">
          Palavras-chave secundárias sugeridas — clique para adicionar como palavras-chave monitoradas
        </label>
        <div id="listaCnaesSugeridos" class="sugestoes-cnaes"></div>
      </div>

      <div class="form-actions" style="grid-column:1/-1;">
        <button type="submit" class="btn btn-primary">Salvar dados</button>
      </div>
      <div id="feedbackEmpresa" class="form-feedback" style="grid-column:1/-1;"></div>
    </form>
  </div>
</main>

<script>
  const BASE_URL = "<?= BASE_URL ?>";
</script>
<script src="<?= BASE_URL ?>/assets/js/sidebar_empresa.js?v=<?= filemtime(__DIR__ . '/../assets/js/sidebar_empresa.js') ?>"></script>
<script src="<?= BASE_URL ?>/assets/js/empresa.js?v=<?= filemtime(__DIR__ . '/../assets/js/empresa.js') ?>"></script>
</body>
</html>
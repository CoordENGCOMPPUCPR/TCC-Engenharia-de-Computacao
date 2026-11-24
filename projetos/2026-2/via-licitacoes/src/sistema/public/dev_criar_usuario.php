<?php
/**
 * ⚠️ PÁGINA TEMPORÁRIA DE DESENVOLVIMENTO ⚠️
 * Cria usuários com hash correto de senha.
 * APAGUE ESTE ARQUIVO ANTES DE COLOCAR EM PRODUÇÃO.
 */

require_once __DIR__ . '/../src/config/config.php';
require_once __DIR__ . '/../src/config/database.php';
require_once __DIR__ . '/../src/core/Response.php';

// Chave de proteção — só quem souber acessa
define('DEV_KEY', 'vialicitacoes2026');

// Se não veio a chave correta, bloqueia
if (($_GET['key'] ?? '') !== DEV_KEY) {
    http_response_code(403);
    exit('Acesso negado. Informe ?key=SUA_CHAVE na URL.');
}

$mensagem = '';
$tipo_msg = '';

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $nome  = trim($_POST['nome'] ?? '');
    $email = trim(strtolower($_POST['email'] ?? ''));
    $senha = $_POST['senha'] ?? '';
    $tipo  = ($_POST['tipo'] ?? 'comum') === 'admin' ? 'admin' : 'comum';

    if ($nome === '' || $email === '' || $senha === '') {
        $mensagem = 'Preencha todos os campos.';
        $tipo_msg = 'erro';
    } elseif (strlen($senha) < 6) {
        $mensagem = 'A senha deve ter no mínimo 6 caracteres.';
        $tipo_msg = 'erro';
    } elseif (!filter_var($email, FILTER_VALIDATE_EMAIL)) {
        $mensagem = 'E-mail inválido.';
        $tipo_msg = 'erro';
    } else {
        try {
            $db = Database::getConnection();

            // Verifica duplicidade
            $check = $db->prepare("SELECT id FROM usuarios WHERE email = ? LIMIT 1");
            $check->execute([$email]);
            if ($check->fetch()) {
                $mensagem = 'Já existe um usuário com este e-mail.';
                $tipo_msg = 'erro';
            } else {
                $hash = password_hash($senha, PASSWORD_DEFAULT);
                $stmt = $db->prepare("
                    INSERT INTO usuarios (nome, email, senha_hash, tipo_usuario, status)
                    VALUES (?, ?, ?, ?, 'ativo')
                ");
                $stmt->execute([$nome, $email, $hash, $tipo]);
                $novo_id = $db->lastInsertId();

                $mensagem = "✓ Usuário criado com sucesso! ID #{$novo_id} — E-mail: {$email} — Senha: {$senha}";
                $tipo_msg = 'ok';
            }
        } catch (Throwable $e) {
            $mensagem = 'Erro: ' . $e->getMessage();
            $tipo_msg = 'erro';
        }
    }
}
?>
<!DOCTYPE html>
<html lang="pt-BR">
<head>
<link rel="icon" type="image/png" href="<?= BASE_URL ?>/assets/img/favicon.png">
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>DEV — Criar Usuário | Via Licitações</title>
<link rel="stylesheet" href="<?= BASE_URL ?>/assets/css/style.css">
<style>
  body {
    background: #0B1220;
    display: flex; align-items: center; justify-content: center;
    min-height: 100vh; padding: 30px;
  }
  .dev-box {
    background: #fff; border-radius: 16px; padding: 40px;
    width: 100%; max-width: 500px;
    box-shadow: 0 30px 80px rgba(0,0,0,0.4);
  }
  .dev-tag {
    display: inline-block;
    background: #fef3c7; color: #92400e;
    font-size: 12px; font-weight: 700; padding: 4px 12px;
    border-radius: 100px; margin-bottom: 16px;
    letter-spacing: 0.5px;
  }
  .dev-box h1 { font-size: 22px; margin-bottom: 8px; }
  .dev-box > p { color: var(--cinza-texto); font-size: 14px; margin-bottom: 24px; }
  .dev-aviso {
    background: #fef2f2; color: #991b1b;
    padding: 12px 16px; border-radius: 8px;
    font-size: 13px; margin-bottom: 22px;
    border-left: 3px solid #dc2626;
  }
</style>
</head>
<body>

<div class="dev-box">
  <span class="dev-tag">PÁGINA DE DESENVOLVIMENTO</span>
  <h1>Criar usuário de teste</h1>
  <p>Gera o hash de senha automaticamente e cria o usuário no banco.</p>

  <div class="dev-aviso">
    ⚠️ Apague este arquivo (<code>dev_criar_usuario.php</code>) antes de subir para produção.
  </div>

  <?php if ($mensagem): ?>
    <div class="form-feedback <?= $tipo_msg ?>" style="margin-bottom:20px; text-align:left;">
      <?= htmlspecialchars($mensagem) ?>
    </div>
  <?php endif; ?>

  <form method="POST">
    <div class="form-group">
      <label>Nome completo</label>
      <input type="text" name="nome" required maxlength="150">
    </div>
    <div class="form-group">
      <label>E-mail</label>
      <input type="email" name="email" required maxlength="150">
    </div>
    <div class="form-group">
      <label>Senha (mín. 6 caracteres)</label>
      <input type="text" name="senha" required minlength="6" placeholder="A senha ficará visível para conferência">
    </div>
    <div class="form-group">
      <label>Tipo de usuário</label>
      <select name="tipo" style="width:100%; padding:12px 14px; border:1px solid #cbd5e1; border-radius:8px; font-size:15px;">
        <option value="comum">Comum</option>
        <option value="admin">Admin (no banco)</option>
      </select>
    </div>
    <button type="submit" class="btn btn-primary btn-block">Criar usuário</button>
  </form>

  <p style="margin-top:24px; text-align:center; font-size:13px; color:var(--cinza-texto);">
    <a href="<?= BASE_URL ?>/index.php" style="color:var(--azul-principal);">← Voltar para a landing</a>
  </p>
</div>

</body>
</html>
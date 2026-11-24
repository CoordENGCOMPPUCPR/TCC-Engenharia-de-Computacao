<?php
require_once __DIR__ . '/../src/config/config.php';
require_once __DIR__ . '/../src/config/database.php';
require_once __DIR__ . '/../src/core/Response.php';

if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    Response::error('Método não permitido', 405);
}

$nome     = trim($_POST['nome'] ?? '');
$email    = trim($_POST['email'] ?? '');
$telefone = trim($_POST['telefone'] ?? '');
$cnpj     = trim($_POST['cnpj'] ?? '');

// Validações
$erros = [];
if ($nome === '')     $erros[] = 'Nome é obrigatório.';
if ($email === '')    $erros[] = 'E-mail é obrigatório.';
if (!filter_var($email, FILTER_VALIDATE_EMAIL)) $erros[] = 'E-mail inválido.';
if ($telefone === '') $erros[] = 'Telefone é obrigatório.';
if ($cnpj === '')     $erros[] = 'CNPJ é obrigatório.';

if ($erros) {
    Response::error(implode(' ', $erros));
}

try {
    $db = Database::getConnection();

    // Evita duplicidade de lead pelo mesmo e-mail em curto prazo
    $check = $db->prepare("SELECT id FROM leads WHERE email = ? AND status_comercial IN ('LEAD NOVO','EM NEGOCIACAO') LIMIT 1");
    $check->execute([$email]);
    if ($check->fetch()) {
        Response::success('Recebemos seu cadastro! Em breve um consultor entrará em contato.');
    }

    $stmt = $db->prepare("INSERT INTO leads (nome, email, telefone, cnpj) VALUES (?, ?, ?, ?)");
    $stmt->execute([$nome, $email, $telefone, $cnpj]);

    Response::success('Recebemos seu cadastro! Em breve um consultor entrará em contato.');
} catch (Throwable $e) {
    if (APP_DEBUG) Response::error('Erro: ' . $e->getMessage(), 500);
    Response::error('Erro ao processar cadastro. Tente novamente.', 500);
}
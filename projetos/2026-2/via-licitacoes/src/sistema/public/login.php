<?php
require_once __DIR__ . '/../src/config/config.php';
require_once __DIR__ . '/../src/core/Auth.php';
require_once __DIR__ . '/../src/core/Response.php';

if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    Response::error('Método não permitido', 405);
}

$email = $_POST['email'] ?? '';
$senha = $_POST['senha'] ?? '';

if ($email === '' || $senha === '') {
    Response::error('Informe e-mail e senha.');
}

$user = Auth::login($email, $senha);

if (!$user) {
    Response::error('Credenciais inválidas ou usuário inativo.', 401);
}

$redirect = ($user['tipo'] === 'admin')
    ? BASE_URL . '/admin/index.php'
    : BASE_URL . '/app/index.php';

Response::success('Login realizado com sucesso.', ['redirect' => $redirect]);
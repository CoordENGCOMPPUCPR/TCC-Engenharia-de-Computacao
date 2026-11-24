<?php
require_once __DIR__ . '/../../src/config/config.php';
require_once __DIR__ . '/../../src/config/database.php';
require_once __DIR__ . '/../../src/core/Auth.php';
require_once __DIR__ . '/../../src/core/Response.php';

Auth::exigirLogin();
$user = Auth::usuario();
$db = Database::getConnection();
$action = $_GET['action'] ?? $_POST['action'] ?? '';

switch ($action) {

    case 'meus_dados':
        $stmt = $db->prepare("
            SELECT u.id, u.nome, u.email, u.telefone, u.tipo_usuario, u.id_empresa, u.eh_owner,
                   e.razao_social, e.nome_fantasia, e.cnpj, e.cnae_principal,
                   e.natureza_juridica, e.situacao_cadastral, e.data_abertura,
                   e.telefone AS empresa_telefone, e.email_contato,
                   e.endereco, e.uf, e.municipio
            FROM usuarios u
            LEFT JOIN empresas e ON e.id = u.id_empresa
            WHERE u.id = ?
        ");
        $stmt->execute([$user['id']]);
        Response::json(['success' => true, 'dados' => $stmt->fetch()]);
        break;

    case 'atualizar':
        $nome     = trim($_POST['nome'] ?? '');
        $email    = trim(strtolower($_POST['email'] ?? ''));
        $telefone = trim($_POST['telefone'] ?? '');

        if ($nome === '' || $email === '') Response::error('Nome e e-mail são obrigatórios.');
        if (!filter_var($email, FILTER_VALIDATE_EMAIL)) Response::error('E-mail inválido.');

        $check = $db->prepare("SELECT id FROM usuarios WHERE email = ? AND id <> ? LIMIT 1");
        $check->execute([$email, $user['id']]);
        if ($check->fetch()) Response::error('Este e-mail já está em uso.');

        $upd = $db->prepare("UPDATE usuarios SET nome = ?, email = ?, telefone = ? WHERE id = ?");
        $upd->execute([$nome, $email, $telefone ?: null, $user['id']]);

        $_SESSION['usuario']['nome']  = $nome;
        $_SESSION['usuario']['email'] = $email;

        Response::success('Dados atualizados com sucesso.');
        break;

    case 'alterar_senha':
        $atual = $_POST['senha_atual'] ?? '';
        $nova  = $_POST['senha_nova'] ?? '';
        $conf  = $_POST['senha_confirma'] ?? '';

        if ($atual === '' || $nova === '' || $conf === '') Response::error('Preencha todos os campos.');
        if (strlen($nova) < 6) Response::error('A nova senha deve ter no mínimo 6 caracteres.');
        if ($nova !== $conf) Response::error('As senhas novas não coincidem.');

        $stmt = $db->prepare("SELECT senha_hash FROM usuarios WHERE id = ?");
        $stmt->execute([$user['id']]);
        $hash = $stmt->fetchColumn();

        if (!password_verify($atual, $hash)) Response::error('Senha atual incorreta.');

        $novoHash = password_hash($nova, PASSWORD_DEFAULT);
        $upd = $db->prepare("UPDATE usuarios SET senha_hash = ? WHERE id = ?");
        $upd->execute([$novoHash, $user['id']]);

        Response::success('Senha alterada com sucesso.');
        break;

    case 'consultar_cnpj':
        $cnpj = preg_replace('/\D/', '', $_GET['cnpj'] ?? '');
        if (strlen($cnpj) !== 14) Response::error('CNPJ inválido.');

        $url = 'https://brasilapi.com.br/api/cnpj/v1/' . $cnpj;
        $ctx = stream_context_create([
            'http' => [
                'method'  => 'GET',
                'timeout' => 8,
                'header'  => "User-Agent: ViaLicitacoes/1.0\r\nAccept: application/json\r\n"
            ]
        ]);

        $json = @file_get_contents($url, false, $ctx);
        if ($json === false) Response::error('Não foi possível consultar o CNPJ agora. Tente novamente.');

        $data = json_decode($json, true);
        if (!$data || isset($data['message'])) Response::error('CNPJ não encontrado na base pública.');

        $cnaes = [];
        if (!empty($data['cnae_fiscal'])) {
            $cnaes[] = [
                'codigo'    => $data['cnae_fiscal'],
                'descricao' => $data['cnae_fiscal_descricao'] ?? '',
                'principal' => true,
            ];
        }
        foreach ($data['cnaes_secundarios'] ?? [] as $c) {
            $cnaes[] = [
                'codigo'    => $c['codigo'] ?? '',
                'descricao' => $c['descricao'] ?? '',
                'principal' => false,
            ];
        }

        Response::json([
            'success' => true,
            'empresa' => [
                'razao_social'       => $data['razao_social'] ?? '',
                'nome_fantasia'      => $data['nome_fantasia'] ?? '',
                'cnpj'               => $data['cnpj'] ?? $cnpj,
                'cnae_principal'     => $data['cnae_fiscal'] ?? '',
                'natureza_juridica'  => $data['natureza_juridica'] ?? '',
                'situacao_cadastral' => $data['descricao_situacao_cadastral'] ?? '',
                'data_abertura'      => $data['data_inicio_atividade'] ?? '',
                'telefone'           => isset($data['ddd_telefone_1']) ? preg_replace('/\D/', '', $data['ddd_telefone_1']) : '',
                'email_contato'      => $data['email'] ?? '',
                'endereco'           => trim(($data['descricao_tipo_de_logradouro'] ?? '') . ' ' . ($data['logradouro'] ?? '') . ', ' . ($data['numero'] ?? '') . ' ' . ($data['complemento'] ?? '')),
                'uf'                 => $data['uf'] ?? '',
                'municipio'          => $data['municipio'] ?? '',
            ],
            'cnaes' => $cnaes,
        ]);
        break;

    default:
        Response::error('Ação inválida.', 404);
}
<?php
require_once __DIR__ . '/../../src/config/config.php';
require_once __DIR__ . '/../../src/config/database.php';
require_once __DIR__ . '/../../src/core/Auth.php';
require_once __DIR__ . '/../../src/core/Response.php';

Auth::exigirLogin();
$user = Auth::usuario();
$db = Database::getConnection();

$stmt = $db->prepare("SELECT id_empresa FROM usuarios WHERE id = ?");
$stmt->execute([$user['id']]);
$idEmpresa = $stmt->fetchColumn();

if (!$idEmpresa) Response::error('Você precisa cadastrar sua empresa antes de definir palavras-chave.');

$action = $_GET['action'] ?? $_POST['action'] ?? '';

switch ($action) {

    case 'listar':
        $stmt = $db->prepare("
            SELECT id, palavra, ativo, data_cadastro
            FROM palavras_interesse
            WHERE id_empresa = ?
            ORDER BY data_cadastro DESC
        ");
        $stmt->execute([$idEmpresa]);
        Response::json(['success' => true, 'items' => $stmt->fetchAll()]);
        break;

    case 'adicionar':
        $palavra = trim($_POST['palavra'] ?? '');
        if ($palavra === '') Response::error('Informe a palavra ou frase.');
        if (strlen($palavra) < 2) Response::error('A palavra deve ter no mínimo 2 caracteres.');
        if (strlen($palavra) > 120) Response::error('Máximo de 120 caracteres.');

        // Normaliza espaços duplicados
        $palavra = preg_replace('/\s+/', ' ', $palavra);

        $dup = $db->prepare("SELECT id FROM palavras_interesse WHERE id_empresa = ? AND palavra = ? LIMIT 1");
        $dup->execute([$idEmpresa, $palavra]);
        if ($dup->fetch()) Response::error('Você já monitora essa palavra.');

        $ins = $db->prepare("INSERT INTO palavras_interesse (id_empresa, palavra) VALUES (?, ?)");
        $ins->execute([$idEmpresa, $palavra]);

        Response::success('Palavra adicionada com sucesso.', ['id' => $db->lastInsertId()]);
        break;

    case 'remover':
        $id = (int)($_POST['id'] ?? 0);
        $del = $db->prepare("DELETE FROM palavras_interesse WHERE id = ? AND id_empresa = ?");
        $del->execute([$id, $idEmpresa]);
        Response::success('Palavra removida.');
        break;

    case 'toggle':
        $id = (int)($_POST['id'] ?? 0);
        $upd = $db->prepare("UPDATE palavras_interesse SET ativo = 1 - ativo WHERE id = ? AND id_empresa = ?");
        $upd->execute([$id, $idEmpresa]);
        Response::success('Status atualizado.');
        break;

    default:
        Response::error('Ação inválida.', 404);
}
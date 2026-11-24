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

if (!$idEmpresa) Response::error('Você precisa cadastrar sua empresa antes de monitorar regiões.');

$action = $_GET['action'] ?? $_POST['action'] ?? '';

switch ($action) {

    case 'listar':
        $stmt = $db->prepare("
            SELECT id, uf, municipio, ativo
            FROM regioes_interesse
            WHERE id_empresa = ?
            ORDER BY uf, municipio
        ");
        $stmt->execute([$idEmpresa]);
        Response::json(['success' => true, 'items' => $stmt->fetchAll()]);
        break;

    case 'adicionar':
        $uf = strtoupper(trim($_POST['uf'] ?? ''));
        $municipio = trim($_POST['municipio'] ?? '');

        if (strlen($uf) !== 2) Response::error('UF inválida.');

        $sql = "SELECT id FROM regioes_interesse
                WHERE id_empresa = ? AND uf = ?
                AND ((municipio IS NULL AND ? = '') OR municipio = ?)
                LIMIT 1";
        $dup = $db->prepare($sql);
        $dup->execute([$idEmpresa, $uf, $municipio, $municipio]);
        if ($dup->fetch()) Response::error('Esta região já está cadastrada.');

        $ins = $db->prepare("INSERT INTO regioes_interesse (id_empresa, uf, municipio) VALUES (?, ?, ?)");
        $ins->execute([$idEmpresa, $uf, $municipio ?: null]);

        Response::success('Região adicionada.');
        break;

    case 'remover':
        $id = (int)($_POST['id'] ?? 0);
        $del = $db->prepare("DELETE FROM regioes_interesse WHERE id = ? AND id_empresa = ?");
        $del->execute([$id, $idEmpresa]);
        Response::success('Região removida.');
        break;

    case 'toggle':
        $id = (int)($_POST['id'] ?? 0);
        $upd = $db->prepare("UPDATE regioes_interesse SET ativo = 1 - ativo WHERE id = ? AND id_empresa = ?");
        $upd->execute([$id, $idEmpresa]);
        Response::success('Status atualizado.');
        break;

    default:
        Response::error('Ação inválida.', 404);
}
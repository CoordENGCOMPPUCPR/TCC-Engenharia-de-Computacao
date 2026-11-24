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

    case 'listar':
        $stmt = $db->prepare("
            SELECT n.id, n.titulo, n.mensagem, n.lida, n.data_envio,
                   n.id_licitacao,
                   l.numero_licitacao, l.objeto, l.uf
            FROM notificacoes n
            LEFT JOIN licitacoes l ON l.id = n.id_licitacao
            WHERE n.id_usuario = ?
            ORDER BY n.lida ASC, n.data_envio DESC
            LIMIT 100
        ");
        $stmt->execute([$user['id']]);
        Response::json(['success' => true, 'items' => $stmt->fetchAll()]);
        break;

    case 'marcar_lida':
        $id = (int)($_POST['id'] ?? 0);
        $upd = $db->prepare("UPDATE notificacoes SET lida = 1 WHERE id = ? AND id_usuario = ?");
        $upd->execute([$id, $user['id']]);
        Response::success('Notificação marcada como lida.');
        break;

    case 'marcar_todas':
        $upd = $db->prepare("UPDATE notificacoes SET lida = 1 WHERE id_usuario = ? AND lida = 0");
        $upd->execute([$user['id']]);
        Response::success('Todas as notificações foram marcadas como lidas.');
        break;

    default:
        Response::error('Ação inválida.', 404);
}
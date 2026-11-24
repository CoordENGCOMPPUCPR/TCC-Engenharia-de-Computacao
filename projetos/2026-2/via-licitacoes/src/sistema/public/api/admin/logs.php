<?php
require_once __DIR__ . '/../../../src/config/config.php';
require_once __DIR__ . '/../../../src/config/database.php';
require_once __DIR__ . '/../../../src/core/Auth.php';
require_once __DIR__ . '/../../../src/core/Response.php';

Auth::exigirAdmin();
$db = Database::getConnection();
$action = $_GET['action'] ?? $_POST['action'] ?? '';

switch ($action) {

    case 'listar':
        $status = trim($_GET['status'] ?? '');
        $tipo   = trim($_GET['tipo'] ?? '');
        $pagina = max(1, (int)($_GET['pagina'] ?? 1));
        $limite = 20;
        $offset = ($pagina - 1) * $limite;

        $where = ["1=1"];
        $params = [];
        if ($status !== '') { $where[] = "l.status = ?"; $params[] = $status; }
        if ($tipo !== '')   { $where[] = "l.tipo_execucao = ?"; $params[] = $tipo; }
        $whereSql = implode(' AND ', $where);

        $count = $db->prepare("SELECT COUNT(*) FROM logs_execucao l WHERE {$whereSql}");
        $count->execute($params);
        $total = (int)$count->fetchColumn();

        $stmt = $db->prepare("
            SELECT l.id, l.tipo_execucao, l.status, l.mensagem,
                   l.quantidade_registros, l.data_execucao,
                   f.nome AS fonte_nome
            FROM logs_execucao l
            LEFT JOIN fontes_coleta f ON f.id = l.id_fonte
            WHERE {$whereSql}
            ORDER BY l.data_execucao DESC
            LIMIT {$limite} OFFSET {$offset}
        ");
        $stmt->execute($params);

        Response::json([
            'success' => true,
            'items'   => $stmt->fetchAll(),
            'total'   => $total,
            'pagina'  => $pagina,
            'paginas' => max(1, (int)ceil($total / $limite)),
        ]);
        break;

    default:
        Response::error('Ação inválida.', 404);
}
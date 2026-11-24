<?php
require_once __DIR__ . '/../../../src/config/config.php';
require_once __DIR__ . '/../../../src/config/database.php';
require_once __DIR__ . '/../../../src/core/Auth.php';
require_once __DIR__ . '/../../../src/core/Response.php';

Auth::exigirAdmin();
$db = Database::getConnection();
$action = $_GET['action'] ?? $_POST['action'] ?? '';

switch ($action) {

    // ---------- RESUMO DO FUNIL ----------
    case 'resumo':
        $stmt = $db->query("
            SELECT status_comercial, COUNT(*) AS total
            FROM leads
            GROUP BY status_comercial
        ");
        $resumo = [
            'LEAD NOVO'      => 0,
            'EM NEGOCIACAO'  => 0,
            'CLIENTE ATIVO'  => 0,
            'DESISTENCIA'    => 0,
        ];
        foreach ($stmt->fetchAll() as $row) {
            $resumo[$row['status_comercial']] = (int)$row['total'];
        }
        Response::json(['success' => true, 'resumo' => $resumo]);
        break;

    // ---------- LISTAR ----------
    case 'listar':
        $busca  = trim($_GET['busca'] ?? '');
        $status = trim($_GET['status'] ?? '');
        $pagina = max(1, (int)($_GET['pagina'] ?? 1));
        $limite = 15;
        $offset = ($pagina - 1) * $limite;

        $where = ["1=1"];
        $params = [];

        if ($busca !== '') {
            $where[] = "(nome LIKE ? OR email LIKE ? OR cnpj LIKE ? OR telefone LIKE ?)";
            $like = "%{$busca}%";
            array_push($params, $like, $like, $like, $like);
        }
        if ($status !== '') {
            $where[] = "status_comercial = ?";
            $params[] = $status;
        }
        $whereSql = implode(' AND ', $where);

        $count = $db->prepare("SELECT COUNT(*) FROM leads WHERE {$whereSql}");
        $count->execute($params);
        $total = (int)$count->fetchColumn();

        $stmt = $db->prepare("
            SELECT id, nome, email, telefone, cnpj, status_comercial,
                   observacao, data_envio, data_atualizacao
            FROM leads
            WHERE {$whereSql}
            ORDER BY data_envio DESC
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

    // ---------- DETALHES ----------
    case 'detalhes':
        $id = (int)($_GET['id'] ?? 0);
        $stmt = $db->prepare("SELECT * FROM leads WHERE id = ?");
        $stmt->execute([$id]);
        $lead = $stmt->fetch();
        if (!$lead) Response::error('Lead não encontrado.', 404);
        Response::json(['success' => true, 'lead' => $lead]);
        break;

    // ---------- ATUALIZAR STATUS / OBSERVAÇÃO ----------
    case 'atualizar':
        $id     = (int)($_POST['id'] ?? 0);
        $status = trim($_POST['status_comercial'] ?? '');
        $obs    = trim($_POST['observacao'] ?? '');

        $statusValidos = ['LEAD NOVO', 'EM NEGOCIACAO', 'CLIENTE ATIVO', 'DESISTENCIA'];
        if (!in_array($status, $statusValidos, true)) {
            Response::error('Status inválido.');
        }

        $upd = $db->prepare("
            UPDATE leads
            SET status_comercial = ?, observacao = ?
            WHERE id = ?
        ");
        $upd->execute([$status, $obs ?: null, $id]);
        Response::success('Lead atualizado com sucesso.');
        break;

    // ---------- EXCLUIR ----------
    case 'excluir':
        $id = (int)($_POST['id'] ?? 0);
        $del = $db->prepare("DELETE FROM leads WHERE id = ?");
        $del->execute([$id]);
        Response::success('Lead excluído.');
        break;

    default:
        Response::error('Ação inválida.', 404);
}
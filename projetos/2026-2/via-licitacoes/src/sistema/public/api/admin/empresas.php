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
        $busca  = trim($_GET['busca'] ?? '');
        $uf     = strtoupper(trim($_GET['uf'] ?? ''));
        $pagina = max(1, (int)($_GET['pagina'] ?? 1));
        $limite = 15;
        $offset = ($pagina - 1) * $limite;

        $where = ["1=1"];
        $params = [];
        if ($busca !== '') {
            $where[] = "(e.razao_social LIKE ? OR e.cnpj LIKE ? OR EXISTS (
                SELECT 1 FROM usuarios ux
                WHERE ux.id_empresa = e.id AND (ux.email LIKE ? OR ux.nome LIKE ?)
            ))";
            $like = "%{$busca}%";
            array_push($params, $like, $like, $like, $like);
        }
        if ($uf !== '' && strlen($uf) === 2) {
            $where[] = "e.uf = ?";
            $params[] = $uf;
        }
        $whereSql = implode(' AND ', $where);

        $count = $db->prepare("
            SELECT COUNT(DISTINCT e.id)
            FROM empresas e
            LEFT JOIN usuarios u ON u.id_empresa = e.id
            WHERE {$whereSql}
        ");
        $count->execute($params);
        $total = (int)$count->fetchColumn();

        $stmt = $db->prepare("
            SELECT e.id, e.razao_social, e.nome_fantasia, e.cnpj,
                e.telefone, e.email_contato, e.uf, e.municipio,
                (SELECT COUNT(*) FROM usuarios u2 WHERE u2.id_empresa = e.id) AS qtd_usuarios,
                (SELECT u3.nome FROM usuarios u3 WHERE u3.id_empresa = e.id ORDER BY u3.id ASC LIMIT 1) AS responsavel,
                (SELECT u3.email FROM usuarios u3 WHERE u3.id_empresa = e.id ORDER BY u3.id ASC LIMIT 1) AS email_responsavel,
                (SELECT u3.id FROM usuarios u3 WHERE u3.id_empresa = e.id ORDER BY u3.id ASC LIMIT 1) AS id_usuario_principal
            FROM empresas e
            WHERE {$whereSql}
            ORDER BY e.data_atualizacao DESC
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

    case 'detalhes':
        $id = (int)($_GET['id'] ?? 0);
        $stmt = $db->prepare("
            SELECT e.*,
                (SELECT COUNT(*) FROM usuarios u WHERE u.id_empresa = e.id) AS qtd_usuarios
            FROM empresas e
            WHERE e.id = ?
        ");
        $stmt->execute([$id]);
        $emp = $stmt->fetch();
        if (!$emp) Response::error('Empresa não encontrada.', 404);

        // Lista os usuários vinculados
        $users = $db->prepare("
            SELECT id, nome, email, tipo_usuario, status
            FROM usuarios
            WHERE id_empresa = ?
            ORDER BY id ASC
        ");
        $users->execute([$id]);
        $emp['usuarios'] = $users->fetchAll();

        Response::json(['success' => true, 'empresa' => $emp]);
        break;

    case 'excluir':
        $id = (int)($_POST['id'] ?? 0);
        $del = $db->prepare("DELETE FROM empresas WHERE id = ?");
        $del->execute([$id]);
        Response::success('Empresa excluída.');
        break;

    default:
        Response::error('Ação inválida.', 404);
}
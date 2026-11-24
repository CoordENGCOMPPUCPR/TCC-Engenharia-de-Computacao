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
        $busca      = trim($_GET['busca'] ?? '');
        $uf         = strtoupper(trim($_GET['uf'] ?? ''));
        $situacao   = trim($_GET['situacao'] ?? '');
        $modalidade = trim($_GET['modalidade'] ?? '');
        $pagina     = max(1, (int)($_GET['pagina'] ?? 1));
        $limite     = 20;
        $offset     = ($pagina - 1) * $limite;

        $where  = ["1=1"];
        $params = [];

        if ($busca !== '') {
            $where[] = "(l.objeto LIKE ? OR l.numero_licitacao LIKE ? OR l.orgao LIKE ? OR l.id_contratacao_pncp LIKE ?)";
            $like = "%{$busca}%";
            array_push($params, $like, $like, $like, $like);
        }
        if ($uf !== '' && strlen($uf) === 2) {
            $where[] = "l.uf = ?";
            $params[] = $uf;
        }
        if ($situacao !== '') {
            $where[] = "l.situacao_pncp = ?";
            $params[] = $situacao;
        }
        if ($modalidade !== '') {
            $where[] = "l.modalidade = ?";
            $params[] = $modalidade;
        }

        $whereSql = implode(' AND ', $where);

        $count = $db->prepare("SELECT COUNT(*) FROM licitacoes l WHERE {$whereSql}");
        $count->execute($params);
        $total = (int)$count->fetchColumn();

        $stmt = $db->prepare("
            SELECT l.id, l.numero_licitacao, l.id_contratacao_pncp,
                   l.objeto, l.orgao, l.unidade, l.localidade, l.uf, l.municipio,
                   l.modalidade, l.situacao_pncp, l.status,
                   l.data_publicacao, l.inicio_propostas, l.fim_propostas,
                   l.valor_estimado, l.valor_homologado,
                   l.link_detalhes, l.plataforma,
                   (SELECT COUNT(*) FROM documentos_licitacao d WHERE d.id_licitacao = l.id) AS qtd_docs
            FROM licitacoes l
            WHERE {$whereSql}
            ORDER BY l.data_coleta DESC, l.id DESC
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
        $stmt = $db->prepare("SELECT * FROM licitacoes WHERE id = ?");
        $stmt->execute([$id]);
        $lic = $stmt->fetch();
        if (!$lic) Response::error('Licitação não encontrada.', 404);

        $docs = $db->prepare("SELECT id, nome_arquivo, url_origem, caminho_arquivo FROM documentos_licitacao WHERE id_licitacao = ?");
        $docs->execute([$id]);
        $lic['documentos'] = $docs->fetchAll();

        Response::json(['success' => true, 'licitacao' => $lic]);
        break;

    case 'excluir':
        $id = (int)($_POST['id'] ?? 0);
        $del = $db->prepare("DELETE FROM licitacoes WHERE id = ?");
        $del->execute([$id]);
        Response::success('Licitação excluída.');
        break;

    case 'filtros':
        // Retorna valores únicos de situação e modalidade para popular selects
        $situacoes = $db->query("
            SELECT DISTINCT situacao_pncp
            FROM licitacoes
            WHERE situacao_pncp IS NOT NULL AND situacao_pncp <> ''
            ORDER BY situacao_pncp
        ")->fetchAll(PDO::FETCH_COLUMN);

        $modalidades = $db->query("
            SELECT DISTINCT modalidade
            FROM licitacoes
            WHERE modalidade IS NOT NULL AND modalidade <> ''
            ORDER BY modalidade
        ")->fetchAll(PDO::FETCH_COLUMN);

        Response::json([
            'success'     => true,
            'situacoes'   => $situacoes,
            'modalidades' => $modalidades,
        ]);
        break;

    default:
        Response::error('Ação inválida.', 404);
}
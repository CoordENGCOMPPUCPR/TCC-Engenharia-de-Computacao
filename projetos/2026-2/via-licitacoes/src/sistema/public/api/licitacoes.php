<?php
require_once __DIR__ . '/../../src/config/config.php';
require_once __DIR__ . '/../../src/config/database.php';
require_once __DIR__ . '/../../src/core/Auth.php';
require_once __DIR__ . '/../../src/core/Response.php';

Auth::exigirLogin();
$user = Auth::usuario();
$db = Database::getConnection();
$action = $_GET['action'] ?? $_POST['action'] ?? '';

$stmtEmp = $db->prepare("SELECT id_empresa FROM usuarios WHERE id = ?");
$stmtEmp->execute([$user['id']]);
$idEmpresa = $stmtEmp->fetchColumn();

/**
 * Carrega as palavras e regiões da empresa (para cálculo de match)
 */
function carregarInteresses(PDO $db, ?int $idEmpresa): array
{
    if (!$idEmpresa) return ['palavras' => [], 'regioes' => []];

    $p = $db->prepare("SELECT palavra FROM palavras_interesse WHERE id_empresa = ? AND ativo = 1");
    $p->execute([$idEmpresa]);
    $palavras = $p->fetchAll(PDO::FETCH_COLUMN);

    $r = $db->prepare("SELECT uf, municipio FROM regioes_interesse WHERE id_empresa = ? AND ativo = 1");
    $r->execute([$idEmpresa]);
    $regioes = $r->fetchAll();

    return ['palavras' => $palavras, 'regioes' => $regioes];
}

/**
 * Calcula se uma licitação bate com os interesses
 * Retorna: ['match' => bool, 'palavras' => [...], 'regiao' => bool]
 */
function calcularMatch(array $lic, array $interesses): array
{
    $palavrasBatidas = [];
    $objetoLower = mb_strtolower($lic['objeto'] ?? '');

    foreach ($interesses['palavras'] as $p) {
        if ($p === '') continue;
        if (mb_strpos($objetoLower, mb_strtolower($p)) !== false) {
            $palavrasBatidas[] = $p;
        }
    }

    $matchRegiao = false;
    foreach ($interesses['regioes'] as $reg) {
        if ($reg['uf'] && $reg['uf'] === ($lic['uf'] ?? '')) {
            if (empty($reg['municipio']) || mb_strtolower($reg['municipio']) === mb_strtolower($lic['municipio'] ?? '')) {
                $matchRegiao = true;
                break;
            }
        }
    }

    return [
        'match'    => count($palavrasBatidas) > 0 || $matchRegiao,
        'palavras' => $palavrasBatidas,
        'regiao'   => $matchRegiao,
    ];
}

switch ($action) {

    case 'listar':
        $busca     = trim($_GET['busca'] ?? '');
        $uf        = strtoupper(trim($_GET['uf'] ?? ''));
        $data      = trim($_GET['data'] ?? '');
        $ordem     = $_GET['ordem'] ?? 'recentes';
        $apenasInt = ($_GET['apenas_interesses'] ?? '') === '1';

        // Listas combináveis
        $palavrasSel = array_filter(array_map('trim', explode(',', $_GET['palavras'] ?? '')));
        $regioesSel  = array_filter(array_map('trim', explode(',', $_GET['regioes'] ?? '')));

        $pagina = max(1, (int)($_GET['pagina'] ?? 1));
        $limite = 10;
        $offset = ($pagina - 1) * $limite;

        $interesses = carregarInteresses($db, $idEmpresa);

        $where  = ["1=1"];
        $params = [];

        // Busca textual livre
        if ($busca !== '') {
            $where[] = "(l.objeto LIKE ? OR l.descricao_resumida LIKE ? OR l.numero_licitacao LIKE ?)";
            $like = "%{$busca}%";
            array_push($params, $like, $like, $like);
        }
        if ($uf !== '' && strlen($uf) === 2) {
            $where[] = "l.uf = ?";
            $params[] = $uf;
        }
        if ($data !== '') {
            $where[] = "l.data_publicacao >= ?";
            $params[] = $data;
        }

        // ================= INTERESSES COMBINÁVEIS =================
        // Palavras-chave selecionadas (OR entre elas)
        if (!empty($palavrasSel)) {
            $orP = [];
            foreach ($palavrasSel as $p) {
                $orP[] = "l.objeto LIKE ?";
                $params[] = "%{$p}%";
            }
            $where[] = '(' . implode(' OR ', $orP) . ')';
        }

        // Regiões selecionadas (formato "UF" ou "UF|Municipio")
        if (!empty($regioesSel)) {
            $orR = [];
            foreach ($regioesSel as $r) {
                if (strpos($r, '|') !== false) {
                    [$ufR, $munR] = explode('|', $r, 2);
                    $orR[] = "(l.uf = ? AND l.municipio = ?)";
                    $params[] = $ufR;
                    $params[] = $munR;
                } else {
                    $orR[] = "l.uf = ?";
                    $params[] = $r;
                }
            }
            $where[] = '(' . implode(' OR ', $orR) . ')';
        }

        // Modo "só dos meus interesses" (comportamento antigo do checkbox)
        if ($apenasInt && empty($palavrasSel) && empty($regioesSel)) {
            $orConds = [];
            foreach ($interesses['palavras'] as $p) {
                $orConds[] = "l.objeto LIKE ?";
                $params[] = "%{$p}%";
            }
            foreach ($interesses['regioes'] as $reg) {
                if ($reg['uf']) {
                    if (!empty($reg['municipio'])) {
                        $orConds[] = "(l.uf = ? AND l.municipio = ?)";
                        $params[] = $reg['uf'];
                        $params[] = $reg['municipio'];
                    } else {
                        $orConds[] = "l.uf = ?";
                        $params[] = $reg['uf'];
                    }
                }
            }
            if ($orConds) $where[] = '(' . implode(' OR ', $orConds) . ')';
        }
        // ==========================================================

        $orderBy = match ($ordem) {
            'valor'    => "l.valor_estimado DESC",
            'abertura' => "l.fim_propostas ASC",
            default    => "l.data_publicacao DESC, l.id DESC",
        };

        $whereSql = implode(' AND ', $where);

        $count = $db->prepare("SELECT COUNT(*) FROM licitacoes l WHERE {$whereSql}");
        $count->execute($params);
        $total = (int)$count->fetchColumn();

        $sql = "
            SELECT l.id, l.numero_licitacao, l.objeto, l.descricao_resumida,
                   l.orgao, l.unidade, l.modalidade, l.uf, l.municipio, l.localidade,
                   l.data_publicacao, l.data_abertura,
                   l.inicio_propostas, l.fim_propostas,
                   l.valor_estimado, l.valor_homologado,
                   l.situacao_pncp, l.status, l.srp, l.plataforma,
                   l.link_detalhes,
                   i.id AS id_interesse,
                   (SELECT ua.nome FROM usuarios ua WHERE ua.id = i.id_usuario_autor LIMIT 1) AS autor_nome
            FROM licitacoes l
            LEFT JOIN interesses_licitacoes i
                ON i.id_licitacao = l.id AND i.id_empresa = ?
            WHERE {$whereSql}
            ORDER BY {$orderBy}
            LIMIT {$limite} OFFSET {$offset}
        ";

        $finalParams = array_merge([$idEmpresa], $params);
        $stmt = $db->prepare($sql);
        $stmt->execute($finalParams);
        $items = $stmt->fetchAll();

        // Enriquece com match
        foreach ($items as &$item) {
            $match = calcularMatch($item, $interesses);
            $item['match']          = $match['match'];
            $item['match_palavras'] = $match['palavras'];
            $item['match_regiao']   = $match['regiao'];

            $item['autores'] = [];
            if ($item['id_interesse']) {
                $st = $db->prepare("
                    SELECT u.nome
                    FROM interesses_licitacoes i
                    INNER JOIN usuarios u ON u.id = i.id_usuario_autor
                    WHERE i.id_empresa = ? AND i.id_licitacao = ?
                ");
                $st->execute([$idEmpresa, $item['id']]);
                $item['autores'] = $st->fetchAll(PDO::FETCH_COLUMN);
            }
        }
        unset($item);

        Response::json([
            'success' => true,
            'items'   => $items,
            'total'   => $total,
            'pagina'  => $pagina,
            'paginas' => max(1, (int)ceil($total / $limite)),
        ]);
        break;

    case 'interesses_disponiveis':
        $p = $db->prepare("SELECT id, palavra FROM palavras_interesse WHERE id_empresa = ? AND ativo = 1 ORDER BY palavra");
        $p->execute([$idEmpresa]);
        $palavras = $p->fetchAll();

        $r = $db->prepare("SELECT id, uf, municipio FROM regioes_interesse WHERE id_empresa = ? AND ativo = 1 ORDER BY uf, municipio");
        $r->execute([$idEmpresa]);
        $regioes = $r->fetchAll();

        Response::json(['success' => true, 'palavras' => $palavras, 'regioes' => $regioes]);
        break;

    case 'detalhes':
        $id = (int)($_GET['id'] ?? 0);
        $stmt = $db->prepare("
            SELECT l.*,
              (SELECT COUNT(*) FROM interesses_licitacoes i
               WHERE i.id_licitacao = l.id AND i.id_empresa = ?) AS marcada
            FROM licitacoes l WHERE l.id = ?
        ");
        $stmt->execute([$idEmpresa, $id]);
        $lic = $stmt->fetch();
        if (!$lic) Response::error('Licitação não encontrada.', 404);

        $docs = $db->prepare("SELECT id, nome_arquivo, url_origem, caminho_arquivo FROM documentos_licitacao WHERE id_licitacao = ?");
        $docs->execute([$id]);
        $lic['documentos'] = $docs->fetchAll();

        $auts = $db->prepare("
            SELECT u.nome, i.data_marcacao, i.observacao
            FROM interesses_licitacoes i
            INNER JOIN usuarios u ON u.id = i.id_usuario_autor
            WHERE i.id_empresa = ? AND i.id_licitacao = ?
            ORDER BY i.data_marcacao ASC
        ");
        $auts->execute([$idEmpresa, $id]);
        $lic['autores'] = $auts->fetchAll();

        // Calcula match para exibir no modal
        $interesses = carregarInteresses($db, $idEmpresa);
        $match = calcularMatch($lic, $interesses);
        $lic['match']          = $match['match'];
        $lic['match_palavras'] = $match['palavras'];
        $lic['match_regiao']   = $match['regiao'];

        Response::json(['success' => true, 'licitacao' => $lic]);
        break;

    case 'marcar':
        $id_licitacao = (int)($_POST['id_licitacao'] ?? 0);
        if (!$id_licitacao) Response::error('Licitação inválida.');
        if (!$idEmpresa) Response::error('Você precisa ter uma empresa cadastrada.');

        $dup = $db->prepare("SELECT id FROM interesses_licitacoes WHERE id_empresa = ? AND id_licitacao = ? LIMIT 1");
        $dup->execute([$idEmpresa, $id_licitacao]);
        if ($dup->fetch()) Response::success('Já estava marcada como interesse.');

        $ins = $db->prepare("
            INSERT INTO interesses_licitacoes (id_empresa, id_usuario_autor, id_licitacao)
            VALUES (?, ?, ?)
        ");
        $ins->execute([$idEmpresa, $user['id'], $id_licitacao]);

        Response::success('Marcada como interesse!', ['autor' => $user['nome']]);
        break;

    case 'desmarcar':
        $id_licitacao = (int)($_POST['id_licitacao'] ?? 0);
        $del = $db->prepare("DELETE FROM interesses_licitacoes WHERE id_empresa = ? AND id_licitacao = ?");
        $del->execute([$idEmpresa, $id_licitacao]);
        Response::success('Interesse removido.');
        break;

    case 'palavras_empresa':
        // Retorna as palavras cadastradas pela empresa (para montar o filtro de checkboxes)
        $stmt = $db->prepare("SELECT id, palavra FROM palavras_interesse WHERE id_empresa = ? AND ativo = 1 ORDER BY palavra");
        $stmt->execute([$idEmpresa]);
        Response::json(['success' => true, 'items' => $stmt->fetchAll()]);
        break;

    default:
        Response::error('Ação inválida.', 404);
}
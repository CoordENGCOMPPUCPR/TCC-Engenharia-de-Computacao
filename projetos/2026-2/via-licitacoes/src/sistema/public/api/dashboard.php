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

if (!$idEmpresa) {
    Response::json([
        'success' => true,
        'sem_empresa' => true,
    ]);
}

/* =====================================================
   1) KPIs GERAIS
   ===================================================== */
$kpi = [];

// Total de licitações no banco
$kpi['total_licitacoes'] = (int)$db->query("SELECT COUNT(*) FROM licitacoes")->fetchColumn();

// Licitações que casam com as palavras/regiões da empresa
$palavras = $db->prepare("SELECT palavra FROM palavras_interesse WHERE id_empresa = ? AND ativo = 1");
$palavras->execute([$idEmpresa]);
$palavrasLista = $palavras->fetchAll(PDO::FETCH_COLUMN);

$regioes = $db->prepare("SELECT uf, municipio FROM regioes_interesse WHERE id_empresa = ? AND ativo = 1");
$regioes->execute([$idEmpresa]);
$regioesLista = $regioes->fetchAll();

$whereMatch = [];
$paramsMatch = [];
foreach ($palavrasLista as $p) {
    $whereMatch[] = "objeto LIKE ?";
    $paramsMatch[] = "%{$p}%";
}
foreach ($regioesLista as $r) {
    if ($r['uf']) {
        if (!empty($r['municipio'])) {
            $whereMatch[] = "(uf = ? AND municipio = ?)";
            $paramsMatch[] = $r['uf'];
            $paramsMatch[] = $r['municipio'];
        } else {
            $whereMatch[] = "uf = ?";
            $paramsMatch[] = $r['uf'];
        }
    }
}
$kpi['total_match'] = 0;
if ($whereMatch) {
    $sqlM = "SELECT COUNT(*) FROM licitacoes WHERE (" . implode(' OR ', $whereMatch) . ") AND fim_propostas >= NOW()";
    $stmtM = $db->prepare($sqlM);
    $stmtM->execute($paramsMatch);
    $kpi['total_match'] = (int)$stmtM->fetchColumn();
}

// Interesses salvos (por status)
$stmt = $db->prepare("
    SELECT status_disputa, COUNT(*) AS total
    FROM interesses_licitacoes
    WHERE id_empresa = ?
    GROUP BY status_disputa
");
$stmt->execute([$idEmpresa]);
$statusCount = [
    'INTERESSE'           => 0,
    'ANALISANDO'          => 0,
    'PREPARANDO_PROPOSTA' => 0,
    'PROPOSTA_ENVIADA'    => 0,
    'EM_DISPUTA'          => 0,
    'GANHAMOS'            => 0,
    'PERDEMOS'            => 0,
    'DESCARTADO'          => 0,
];
foreach ($stmt->fetchAll() as $row) {
    $statusCount[$row['status_disputa']] = (int)$row['total'];
}
$kpi['interesses_status'] = $statusCount;
$kpi['interesses_total']  = array_sum($statusCount);

// Valor total em disputa (soma dos valores estimados das licitações em interesses ativos)
$stmt = $db->prepare("
    SELECT COALESCE(SUM(l.valor_estimado), 0)
    FROM interesses_licitacoes i
    INNER JOIN licitacoes l ON l.id = i.id_licitacao
    WHERE i.id_empresa = ?
      AND i.status_disputa IN ('INTERESSE','ANALISANDO','PREPARANDO_PROPOSTA','PROPOSTA_ENVIADA','EM_DISPUTA')
");
$stmt->execute([$idEmpresa]);
$kpi['valor_em_disputa'] = (float)$stmt->fetchColumn();

// Valor ganho (status GANHAMOS)
$stmt = $db->prepare("
    SELECT COALESCE(SUM(l.valor_estimado), 0)
    FROM interesses_licitacoes i
    INNER JOIN licitacoes l ON l.id = i.id_licitacao
    WHERE i.id_empresa = ? AND i.status_disputa = 'GANHAMOS'
");
$stmt->execute([$idEmpresa]);
$kpi['valor_ganho'] = (float)$stmt->fetchColumn();

// Licitações que encerram nos próximos 7 dias (com match ou já marcadas)
$stmt = $db->prepare("
    SELECT COUNT(*)
    FROM licitacoes l
    WHERE l.fim_propostas BETWEEN NOW() AND DATE_ADD(NOW(), INTERVAL 7 DAY)
      AND (
        EXISTS (SELECT 1 FROM interesses_licitacoes i WHERE i.id_licitacao = l.id AND i.id_empresa = ?)
        " . ($whereMatch ? " OR (" . implode(' OR ', $whereMatch) . ")" : "") . "
      )
");
$paramsUrgentes = array_merge([$idEmpresa], $paramsMatch);
$stmt->execute($paramsUrgentes);
$kpi['encerrando_7_dias'] = (int)$stmt->fetchColumn();

/* =====================================================
   2) PALAVRAS COM CONTAGEM
   ===================================================== */
$stmt = $db->prepare("
    SELECT id, palavra, ativo
    FROM palavras_interesse
    WHERE id_empresa = ?
    ORDER BY palavra
");
$stmt->execute([$idEmpresa]);
$palavrasDetalhe = $stmt->fetchAll();

foreach ($palavrasDetalhe as &$p) {
    $c = $db->prepare("
        SELECT COUNT(*) FROM licitacoes
        WHERE objeto LIKE ? AND fim_propostas >= NOW()
    ");
    $c->execute(["%{$p['palavra']}%"]);
    $p['qtd_licitacoes'] = (int)$c->fetchColumn();
}
unset($p);

/* =====================================================
   3) REGIÕES COM CONTAGEM
   ===================================================== */
$stmt = $db->prepare("
    SELECT id, uf, municipio, ativo
    FROM regioes_interesse
    WHERE id_empresa = ?
    ORDER BY uf, municipio
");
$stmt->execute([$idEmpresa]);
$regioesDetalhe = $stmt->fetchAll();

foreach ($regioesDetalhe as &$r) {
    if (!empty($r['municipio'])) {
        $c = $db->prepare("SELECT COUNT(*) FROM licitacoes WHERE uf = ? AND municipio = ? AND fim_propostas >= NOW()");
        $c->execute([$r['uf'], $r['municipio']]);
    } else {
        $c = $db->prepare("SELECT COUNT(*) FROM licitacoes WHERE uf = ? AND fim_propostas >= NOW()");
        $c->execute([$r['uf']]);
    }
    $r['qtd_licitacoes'] = (int)$c->fetchColumn();
}
unset($r);

/* =====================================================
   4) CHECKLIST — TAREFAS PENDENTES
   ===================================================== */
$stmt = $db->prepare("
    SELECT t.id, t.titulo, t.id_interesse,
           l.numero_licitacao, l.fim_propostas,
           i.status_disputa
    FROM interesses_tarefas t
    INNER JOIN interesses_licitacoes i ON i.id = t.id_interesse
    INNER JOIN licitacoes l ON l.id = i.id_licitacao
    WHERE i.id_empresa = ? AND t.concluida = 0
      AND i.status_disputa NOT IN ('GANHAMOS','PERDEMOS','DESCARTADO')
    ORDER BY l.fim_propostas ASC
    LIMIT 8
");
$stmt->execute([$idEmpresa]);
$tarefasPendentes = $stmt->fetchAll();

// Total de tarefas pendentes
$stmt = $db->prepare("
    SELECT COUNT(*)
    FROM interesses_tarefas t
    INNER JOIN interesses_licitacoes i ON i.id = t.id_interesse
    WHERE i.id_empresa = ? AND t.concluida = 0
      AND i.status_disputa NOT IN ('GANHAMOS','PERDEMOS','DESCARTADO')
");
$stmt->execute([$idEmpresa]);
$kpi['tarefas_pendentes'] = (int)$stmt->fetchColumn();

/* =====================================================
   5) LICITAÇÕES URGENTES (encerrando em 7 dias)
   ===================================================== */
$sqlU = "
    SELECT l.id, l.numero_licitacao, l.objeto, l.uf, l.municipio,
           l.fim_propostas, l.valor_estimado,
           (SELECT COUNT(*) FROM interesses_licitacoes i WHERE i.id_licitacao = l.id AND i.id_empresa = ?) AS marcada
    FROM licitacoes l
    WHERE l.fim_propostas BETWEEN NOW() AND DATE_ADD(NOW(), INTERVAL 7 DAY)
      AND (
        EXISTS (SELECT 1 FROM interesses_licitacoes i WHERE i.id_licitacao = l.id AND i.id_empresa = ?)
        " . ($whereMatch ? " OR (" . implode(' OR ', $whereMatch) . ")" : "") . "
      )
    ORDER BY l.fim_propostas ASC
    LIMIT 5
";
$paramsU = array_merge([$idEmpresa, $idEmpresa], $paramsMatch);
$stmtU = $db->prepare($sqlU);
$stmtU->execute($paramsU);
$urgentes = $stmtU->fetchAll();

/* =====================================================
   6) ATIVIDADE RECENTE
   ===================================================== */
$stmt = $db->prepare("
    SELECT c.id, c.comentario, c.tipo, c.nome_usuario, c.data_criacao,
           i.id AS id_interesse, l.numero_licitacao
    FROM interesses_comentarios c
    INNER JOIN interesses_licitacoes i ON i.id = c.id_interesse
    INNER JOIN licitacoes l ON l.id = i.id_licitacao
    WHERE i.id_empresa = ?
    ORDER BY c.data_criacao DESC
    LIMIT 6
");
$stmt->execute([$idEmpresa]);
$atividade = $stmt->fetchAll();

/* =====================================================
   7) INFO DA EMPRESA
   ===================================================== */
$stmt = $db->prepare("SELECT razao_social, nome_fantasia, cnpj, uf, municipio FROM empresas WHERE id = ?");
$stmt->execute([$idEmpresa]);
$empresa = $stmt->fetch();

/* =====================================================
   RETORNO
   ===================================================== */
Response::json([
    'success'        => true,
    'kpi'            => $kpi,
    'palavras'       => $palavrasDetalhe,
    'regioes'        => $regioesDetalhe,
    'tarefas'        => $tarefasPendentes,
    'urgentes'       => $urgentes,
    'atividade'      => $atividade,
    'empresa'        => $empresa,
]);
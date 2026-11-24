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

if (!$idEmpresa) Response::error('Você precisa ter uma empresa cadastrada.');

$action = $_GET['action'] ?? $_POST['action'] ?? '';

/**
 * Valida que o interesse pertence à empresa do usuário logado
 */
function validarInteresse(PDO $db, int $id, int $idEmpresa): array
{
    $s = $db->prepare("
        SELECT i.*, l.id AS id_licitacao, l.numero_licitacao, l.objeto,
               l.orgao, l.uf, l.municipio, l.localidade, l.data_publicacao,
               l.valor_estimado, l.inicio_propostas, l.fim_propostas
        FROM interesses_licitacoes i
        INNER JOIN licitacoes l ON l.id = i.id_licitacao
        WHERE i.id = ? AND i.id_empresa = ?
    ");
    $s->execute([$id, $idEmpresa]);
    $r = $s->fetch();
    if (!$r) Response::error('Interesse não encontrado.', 404);
    return $r;
}

/**
 * Adiciona comentário automático na timeline
 */
function registrarHistorico(PDO $db, int $idInteresse, ?int $idUsuario, string $nome, string $texto, string $tipo = 'SISTEMA'): void
{
    $db->prepare("
        INSERT INTO interesses_comentarios (id_interesse, id_usuario, nome_usuario, comentario, tipo)
        VALUES (?, ?, ?, ?, ?)
    ")->execute([$idInteresse, $idUsuario, $nome, $texto, $tipo]);
}

switch ($action) {

    // =====================================================
    // LISTAR (cards resumidos)
    // =====================================================
    case 'listar':
        $stmt = $db->prepare("
            SELECT i.id, i.observacao, i.data_marcacao, i.status_disputa,
                   i.valor_minimo, i.valor_inicial, i.valor_maximo, i.data_limite_interna,
                   l.id AS id_licitacao, l.numero_licitacao, l.objeto,
                   l.orgao, l.uf, l.municipio, l.localidade,
                   l.data_publicacao, l.fim_propostas, l.valor_estimado,
                   (SELECT u.nome FROM usuarios u WHERE u.id = i.id_usuario_autor LIMIT 1) AS autor_nome,
                   (SELECT COUNT(*) FROM interesses_tarefas t WHERE t.id_interesse = i.id AND t.concluida = 0) AS tarefas_pendentes,
                   (SELECT COUNT(*) FROM interesses_tarefas t WHERE t.id_interesse = i.id) AS tarefas_total,
                   (SELECT COUNT(*) FROM interesses_comentarios c WHERE c.id_interesse = i.id) AS comentarios_total
            FROM interesses_licitacoes i
            INNER JOIN licitacoes l ON l.id = i.id_licitacao
            WHERE i.id_empresa = ?
            ORDER BY i.data_marcacao DESC
        ");
        $stmt->execute([$idEmpresa]);
        Response::json(['success' => true, 'items' => $stmt->fetchAll()]);
        break;

    // =====================================================
    // DETALHES (workspace completo)
    // =====================================================
    case 'detalhes':
        $id = (int)($_GET['id'] ?? 0);
        $int = validarInteresse($db, $id, $idEmpresa);

        // Tarefas
        $t = $db->prepare("
            SELECT t.*, u.nome AS concluido_por
            FROM interesses_tarefas t
            LEFT JOIN usuarios u ON u.id = t.id_usuario_concluiu
            WHERE t.id_interesse = ?
            ORDER BY t.ordem ASC, t.id ASC
        ");
        $t->execute([$id]);
        $int['tarefas'] = $t->fetchAll();

        // Comentários
        $c = $db->prepare("
            SELECT * FROM interesses_comentarios
            WHERE id_interesse = ?
            ORDER BY data_criacao ASC, id ASC
        ");
        $c->execute([$id]);
        $int['comentarios'] = $c->fetchAll();

        Response::json(['success' => true, 'interesse' => $int]);
        break;

    // =====================================================
    // ATUALIZAR STATUS + VALORES
    // =====================================================
    case 'atualizar_dados':
        $id = (int)($_POST['id'] ?? 0);
        $int = validarInteresse($db, $id, $idEmpresa);

        $status  = $_POST['status_disputa'] ?? $int['status_disputa'];
        $statusValidos = ['INTERESSE','ANALISANDO','PREPARANDO_PROPOSTA','PROPOSTA_ENVIADA','EM_DISPUTA','GANHAMOS','PERDEMOS','DESCARTADO'];
        if (!in_array($status, $statusValidos, true)) $status = $int['status_disputa'];

        $min = trim($_POST['valor_minimo'] ?? '');
        $ini = trim($_POST['valor_inicial'] ?? '');
        $max = trim($_POST['valor_maximo'] ?? '');
        $lim = trim($_POST['data_limite_interna'] ?? '');

        $valorMinimo = $min === '' ? null : (float)str_replace(',', '.', str_replace('.', '', $min));
        $valorInicial = $ini === '' ? null : (float)str_replace(',', '.', str_replace('.', '', $ini));
        $valorMaximo = $max === '' ? null : (float)str_replace(',', '.', str_replace('.', '', $max));
        $dataLimite = $lim === '' ? null : $lim;

        // Registra mudança de status no histórico
        if ($status !== $int['status_disputa']) {
            registrarHistorico($db, $id, $user['id'], $user['nome'],
                "Status alterado de '{$int['status_disputa']}' para '$status'",
                'MUDANCA_STATUS');
        }

        $upd = $db->prepare("
            UPDATE interesses_licitacoes
            SET status_disputa = ?, valor_minimo = ?, valor_inicial = ?, valor_maximo = ?, data_limite_interna = ?
            WHERE id = ? AND id_empresa = ?
        ");
        $upd->execute([$status, $valorMinimo, $valorInicial, $valorMaximo, $dataLimite, $id, $idEmpresa]);

        Response::success('Dados atualizados com sucesso.');
        break;

    // =====================================================
    // TAREFAS (checklist)
    // =====================================================
    case 'tarefa_adicionar':
        $id = (int)($_POST['id_interesse'] ?? 0);
        $titulo = trim($_POST['titulo'] ?? '');
        if ($titulo === '') Response::error('Título da tarefa é obrigatório.');
        validarInteresse($db, $id, $idEmpresa);

        // ordem = última + 1
        $ordem = (int)$db->query("SELECT COALESCE(MAX(ordem), 0) + 1 FROM interesses_tarefas WHERE id_interesse = $id")->fetchColumn();

        $ins = $db->prepare("INSERT INTO interesses_tarefas (id_interesse, titulo, ordem) VALUES (?, ?, ?)");
        $ins->execute([$id, $titulo, $ordem]);

        Response::success('Tarefa adicionada.', ['id' => $db->lastInsertId()]);
        break;

    case 'tarefa_toggle':
        $idTarefa = (int)($_POST['id'] ?? 0);
        $s = $db->prepare("
            SELECT t.*, i.id_empresa FROM interesses_tarefas t
            INNER JOIN interesses_licitacoes i ON i.id = t.id_interesse
            WHERE t.id = ?
        ");
        $s->execute([$idTarefa]);
        $t = $s->fetch();
        if (!$t || (int)$t['id_empresa'] !== $idEmpresa) Response::error('Tarefa não encontrada.', 404);

        $novoEstado = $t['concluida'] ? 0 : 1;
        $upd = $db->prepare("
            UPDATE interesses_tarefas
            SET concluida = ?, data_conclusao = ?, id_usuario_concluiu = ?
            WHERE id = ?
        ");
        $upd->execute([
            $novoEstado,
            $novoEstado ? date('Y-m-d H:i:s') : null,
            $novoEstado ? $user['id'] : null,
            $idTarefa
        ]);

        Response::success($novoEstado ? 'Tarefa concluída.' : 'Tarefa reaberta.');
        break;

    case 'tarefa_remover':
        $idTarefa = (int)($_POST['id'] ?? 0);
        $s = $db->prepare("
            SELECT t.id FROM interesses_tarefas t
            INNER JOIN interesses_licitacoes i ON i.id = t.id_interesse
            WHERE t.id = ? AND i.id_empresa = ?
        ");
        $s->execute([$idTarefa, $idEmpresa]);
        if (!$s->fetch()) Response::error('Tarefa não encontrada.', 404);

        $db->prepare("DELETE FROM interesses_tarefas WHERE id = ?")->execute([$idTarefa]);
        Response::success('Tarefa removida.');
        break;

    case 'tarefas_padrao':
        // Cria o checklist padrão de licitação
        $id = (int)($_POST['id_interesse'] ?? 0);
        validarInteresse($db, $id, $idEmpresa);

        $checklistPadrao = [
            'Reunir documentos da empresa (CNPJ, certidões, contrato social)',
            'Analisar edital completo e anexos',
            'Verificar exigências técnicas e habilitação',
            'Analisar planilha de custos e viabilidade',
            'Definir valor mínimo de negociação',
            'Definir valor inicial da proposta',
            'Definir valor máximo aceitável',
            'Verificar cadastro no portal da disputa',
            'Preparar proposta técnica',
            'Preparar proposta comercial',
            'Revisar documentação final',
            'Enviar proposta dentro do prazo',
            'Confirmar recebimento e acompanhar sessão',
        ];

        // Verifica se já tem tarefas (evita duplicar)
        $ja = $db->prepare("SELECT COUNT(*) FROM interesses_tarefas WHERE id_interesse = ?");
        $ja->execute([$id]);
        if ((int)$ja->fetchColumn() > 0) Response::error('Já existem tarefas neste interesse.');

        $ins = $db->prepare("INSERT INTO interesses_tarefas (id_interesse, titulo, ordem) VALUES (?, ?, ?)");
        $ordem = 0;
        foreach ($checklistPadrao as $titulo) {
            $ins->execute([$id, $titulo, $ordem++]);
        }

        Response::success('Checklist padrão criado com ' . count($checklistPadrao) . ' tarefas.');
        break;

    // =====================================================
    // COMENTÁRIOS
    // =====================================================
    case 'comentario_adicionar':
        $id = (int)($_POST['id_interesse'] ?? 0);
        $texto = trim($_POST['comentario'] ?? '');
        if ($texto === '') Response::error('Comentário vazio.');
        validarInteresse($db, $id, $idEmpresa);

        $db->prepare("
            INSERT INTO interesses_comentarios (id_interesse, id_usuario, nome_usuario, comentario, tipo)
            VALUES (?, ?, ?, ?, 'COMENTARIO')
        ")->execute([$id, $user['id'], $user['nome'], $texto]);

        Response::success('Comentário adicionado.');
        break;

    // =====================================================
    // REMOVER
    // =====================================================
    case 'remover':
        $id = (int)($_POST['id'] ?? 0);
        $del = $db->prepare("DELETE FROM interesses_licitacoes WHERE id = ? AND id_empresa = ?");
        $del->execute([$id, $idEmpresa]);
        Response::success('Interesse removido.');
        break;

    case 'atualizar_obs':
        $id = (int)($_POST['id'] ?? 0);
        $obs = trim($_POST['observacao'] ?? '');
        $upd = $db->prepare("UPDATE interesses_licitacoes SET observacao = ? WHERE id = ? AND id_empresa = ?");
        $upd->execute([$obs, $id, $idEmpresa]);
        Response::success('Observação atualizada.');
        break;

    default:
        Response::error('Ação inválida.', 404);
}
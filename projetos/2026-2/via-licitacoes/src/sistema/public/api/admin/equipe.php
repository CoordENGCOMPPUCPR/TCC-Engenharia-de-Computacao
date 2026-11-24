<?php
require_once __DIR__ . '/../../src/config/config.php';
require_once __DIR__ . '/../../src/config/database.php';
require_once __DIR__ . '/../../src/core/Auth.php';
require_once __DIR__ . '/../../src/core/Response.php';

Auth::exigirLogin();
$user = Auth::usuario();
$db = Database::getConnection();
$action = $_GET['action'] ?? $_POST['action'] ?? '';

/**
 * Descobre o id_empresa do usuário logado
 */
function getIdEmpresa(PDO $db, int $idUsuario): ?int
{
    $s = $db->prepare("SELECT id_empresa FROM usuarios WHERE id = ?");
    $s->execute([$idUsuario]);
    $v = $s->fetchColumn();
    return $v !== false && $v !== null ? (int)$v : null;
}

function gerarSenhaTemporaria(int $tamanho = 10): string
{
    $chars = 'ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz23456789';
    $senha = '';
    for ($i = 0; $i < $tamanho; $i++) {
        $senha .= $chars[random_int(0, strlen($chars) - 1)];
    }
    return $senha;
}

$idEmpresa = getIdEmpresa($db, $user['id']);
if ($idEmpresa === null) {
    Response::error('Você ainda não está vinculado a nenhuma empresa. Cadastre sua empresa primeiro.');
}

switch ($action) {

    // ---------- LISTAR EQUIPE ----------
    case 'listar':
        $stmt = $db->prepare("
            SELECT id, nome, email, telefone, status, eh_owner, ultimo_acesso, data_cadastro
            FROM usuarios
            WHERE id_empresa = ?
            ORDER BY eh_owner DESC, data_cadastro ASC
        ");
        $stmt->execute([$idEmpresa]);
        Response::json([
            'success' => true,
            'items'   => $stmt->fetchAll(),
            'eu'      => $user['id'],
        ]);
        break;

    // ---------- CONVIDAR NOVO USUÁRIO ----------
    case 'convidar':
        $nome     = trim($_POST['nome'] ?? '');
        $email    = trim(strtolower($_POST['email'] ?? ''));
        $telefone = trim($_POST['telefone'] ?? '');
        $tipo     = ($_POST['tipo_usuario'] ?? 'comum') === 'admin' ? 'admin' : 'comum';

        if ($nome === '' || $email === '') Response::error('Nome e e-mail são obrigatórios.');
        if (!filter_var($email, FILTER_VALIDATE_EMAIL)) Response::error('E-mail inválido.');

        $check = $db->prepare("SELECT id FROM usuarios WHERE email = ? LIMIT 1");
        $check->execute([$email]);
        if ($check->fetch()) Response::error('Já existe um usuário com este e-mail.');

        $senhaTemp = gerarSenhaTemporaria();
        $hash = password_hash($senhaTemp, PASSWORD_DEFAULT);

        $ins = $db->prepare("
            INSERT INTO usuarios (nome, email, senha_hash, telefone, tipo_usuario, status, id_empresa, eh_owner)
            VALUES (?, ?, ?, ?, ?, 'ativo', ?, 0)
        ");
        $ins->execute([$nome, $email, $hash, $telefone ?: null, $tipo, $idEmpresa]);

        Response::success(
            'Usuário convidado com sucesso.',
            ['id' => $db->lastInsertId(), 'senha_temporaria' => $senhaTemp]
        );
        break;

    // ---------- ALTERAR STATUS ----------
    case 'toggle_status':
        $id = (int)($_POST['id'] ?? 0);

        // Não pode mexer em si mesmo
        if ($id === (int)$user['id']) Response::error('Você não pode alterar seu próprio status.');

        // Confirma que o alvo é da mesma empresa
        $stmt = $db->prepare("SELECT eh_owner, status, id_empresa FROM usuarios WHERE id = ?");
        $stmt->execute([$id]);
        $alvo = $stmt->fetch();
        if (!$alvo || (int)$alvo['id_empresa'] !== $idEmpresa) {
            Response::error('Usuário não pertence à sua empresa.');
        }

        // Owner não pode ser inativado por ninguém
        if ((int)$alvo['eh_owner'] === 1) {
            Response::error('O usuário criador da empresa não pode ser inativado.');
        }

        $novoStatus = $alvo['status'] === 'ativo' ? 'inativo' : 'ativo';
        $upd = $db->prepare("UPDATE usuarios SET status = ? WHERE id = ?");
        $upd->execute([$novoStatus, $id]);

        Response::success('Status atualizado.');
        break;

    // ---------- REMOVER DA EQUIPE ----------
    case 'remover':
        $id = (int)($_POST['id'] ?? 0);

        if ($id === (int)$user['id']) Response::error('Você não pode remover a si mesmo.');

        $stmt = $db->prepare("SELECT eh_owner, id_empresa FROM usuarios WHERE id = ?");
        $stmt->execute([$id]);
        $alvo = $stmt->fetch();
        if (!$alvo || (int)$alvo['id_empresa'] !== $idEmpresa) {
            Response::error('Usuário não pertence à sua empresa.');
        }
        if ((int)$alvo['eh_owner'] === 1) {
            Response::error('O usuário criador da empresa não pode ser removido.');
        }

        // Em vez de DELETE, apenas desvincula da empresa e inativa
        $upd = $db->prepare("UPDATE usuarios SET id_empresa = NULL, status = 'inativo' WHERE id = ?");
        $upd->execute([$id]);

        Response::success('Usuário desvinculado da empresa.');
        break;

    default:
        Response::error('Ação inválida.', 404);
}
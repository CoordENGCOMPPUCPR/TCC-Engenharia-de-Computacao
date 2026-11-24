<?php
require_once __DIR__ . '/../../../src/config/config.php';
require_once __DIR__ . '/../../../src/config/database.php';
require_once __DIR__ . '/../../../src/core/Auth.php';
require_once __DIR__ . '/../../../src/core/Response.php';

Auth::exigirAdmin();
$db = Database::getConnection();
$action = $_GET['action'] ?? $_POST['action'] ?? '';

/**
 * Gera senha temporária legível (sem caracteres ambíguos).
 */
function gerarSenhaTemporaria(int $tamanho = 10): string
{
    $chars = 'ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz23456789';
    $senha = '';
    for ($i = 0; $i < $tamanho; $i++) {
        $senha .= $chars[random_int(0, strlen($chars) - 1)];
    }
    return $senha;
}

switch ($action) {

    // ---------- LISTAR ----------
    case 'listar':
        $busca  = trim($_GET['busca'] ?? '');
        $tipo   = trim($_GET['tipo'] ?? '');
        $status = trim($_GET['status'] ?? '');
        $pagina = max(1, (int)($_GET['pagina'] ?? 1));
        $limite = 15;
        $offset = ($pagina - 1) * $limite;

        $where = ["1=1"];
        $params = [];

        if ($busca !== '') {
            $where[] = "(u.nome LIKE ? OR u.email LIKE ?)";
            $like = "%{$busca}%";
            array_push($params, $like, $like);
        }
        if (in_array($tipo, ['comum', 'admin'], true)) {
            $where[] = "u.tipo_usuario = ?";
            $params[] = $tipo;
        }
        if (in_array($status, ['ativo', 'inativo', 'pendente'], true)) {
            $where[] = "u.status = ?";
            $params[] = $status;
        }

        $whereSql = implode(' AND ', $where);

        $count = $db->prepare("SELECT COUNT(*) FROM usuarios u WHERE {$whereSql}");
        $count->execute($params);
        $total = (int)$count->fetchColumn();

        $stmt = $db->prepare("
            SELECT u.id, u.nome, u.email, u.tipo_usuario, u.status,
                   u.data_cadastro, u.ultimo_acesso,
                   e.razao_social AS empresa_nome, e.cnpj AS empresa_cnpj
            FROM usuarios u
            LEFT JOIN empresas e ON e.id = u.id_empresa
            WHERE {$whereSql}
            ORDER BY u.data_cadastro DESC
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
        $stmt = $db->prepare("
            SELECT u.id, u.nome, u.email, u.tipo_usuario, u.status,
                   u.telefone, u.data_cadastro, u.ultimo_acesso,
                   e.id AS empresa_id, e.razao_social, e.nome_fantasia, e.cnpj,
                   e.telefone AS empresa_telefone, e.email_contato,
                   e.endereco, e.uf, e.municipio
            FROM usuarios u
            LEFT JOIN empresas e ON e.id = u.id_empresa
            WHERE u.id = ?
        ");
        $stmt->execute([$id]);
        $u = $stmt->fetch();
        if (!$u) Response::error('Usuário não encontrado.', 404);
        Response::json(['success' => true, 'usuario' => $u]);
        break;


        // ---------- CRIAR ----------
    case 'criar':
        $nome     = trim($_POST['nome'] ?? '');
        $email    = trim(strtolower($_POST['email'] ?? ''));
        $senha    = $_POST['senha'] ?? '';
        $telefone = trim($_POST['telefone'] ?? '');
        $tipo     = ($_POST['tipo_usuario'] ?? 'comum') === 'admin' ? 'admin' : 'comum';
        $status   = in_array($_POST['status'] ?? 'ativo', ['ativo','inativo','pendente'], true)
                    ? $_POST['status'] : 'ativo';

        // Vínculo de empresa (pode vir de um select OU de "criar nova")
        $id_empresa  = !empty($_POST['id_empresa']) ? (int)$_POST['id_empresa'] : null;
        $novaEmpresa = trim($_POST['nova_empresa_razao'] ?? '');
        $novoCnpj    = trim($_POST['nova_empresa_cnpj'] ?? '');

        // Se o select mandou o valor especial, forçamos criação de nova
        if (($_POST['id_empresa'] ?? '') === '__NOVA__') {
            $id_empresa = null;
        }

        // Validações básicas
        if ($nome === '' || $email === '' || $senha === '') {
            Response::error('Nome, e-mail e senha são obrigatórios.');
        }
        if (!filter_var($email, FILTER_VALIDATE_EMAIL)) {
            Response::error('E-mail inválido.');
        }
        if (strlen($senha) < 6) {
            Response::error('A senha deve ter no mínimo 6 caracteres.');
        }

        // E-mail duplicado?
        $check = $db->prepare("SELECT id FROM usuarios WHERE email = ? LIMIT 1");
        $check->execute([$email]);
        if ($check->fetch()) Response::error('Já existe um usuário com este e-mail.');

        // Se vai criar empresa nova, valida dados mínimos
        $criarNovaEmpresa = ($id_empresa === null && $novaEmpresa !== '' && $novoCnpj !== '');
        if ($id_empresa === null && $novaEmpresa !== '' && $novoCnpj === '') {
            Response::error('Informe o CNPJ da nova empresa.');
        }
        if ($id_empresa === null && $novaEmpresa === '' && $novoCnpj !== '') {
            Response::error('Informe a razão social da nova empresa.');
        }

        // Se criando empresa nova, valida CNPJ duplicado
        if ($criarNovaEmpresa) {
            $checkCnpj = $db->prepare("SELECT id FROM empresas WHERE cnpj = ? LIMIT 1");
            $checkCnpj->execute([$novoCnpj]);
            if ($checkCnpj->fetch()) {
                Response::error('Já existe uma empresa com este CNPJ.');
            }
        }

        $db->beginTransaction();
        try {
            // 1) Se for criar empresa nova, cria antes
            if ($criarNovaEmpresa) {
                $insE = $db->prepare("
                    INSERT INTO empresas (razao_social, cnpj)
                    VALUES (?, ?)
                ");
                $insE->execute([$novaEmpresa, $novoCnpj]);
                $id_empresa = (int)$db->lastInsertId();
            }

            // 2) Cria o usuário (com id_empresa, que pode ser NULL)
            $hash = password_hash($senha, PASSWORD_DEFAULT);
            $ins = $db->prepare("
                INSERT INTO usuarios
                    (nome, email, senha_hash, telefone, tipo_usuario, status, id_empresa)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ");
            $ins->execute([
                $nome,
                $email,
                $hash,
                $telefone ?: null,
                $tipo,
                $status,
                $id_empresa,   // pode ser NULL
            ]);

            $novoUsuarioId = (int)$db->lastInsertId();
            $db->commit();

            Response::success('Usuário criado com sucesso.', ['id' => $novoUsuarioId]);
        } catch (Throwable $e) {
            $db->rollBack();
            Response::error('Erro ao criar usuário: ' . $e->getMessage(), 500);
        }
        break;

    // ---------- ATUALIZAR ----------
    case 'atualizar':
        $id         = (int)($_POST['id'] ?? 0);
        $nome       = trim($_POST['nome'] ?? '');
        $email      = trim(strtolower($_POST['email'] ?? ''));
        $telefone   = trim($_POST['telefone'] ?? '');
        $tipo       = ($_POST['tipo_usuario'] ?? 'comum') === 'admin' ? 'admin' : 'comum';
        $status     = in_array($_POST['status'] ?? 'ativo', ['ativo','inativo','pendente'], true)
                        ? $_POST['status'] : 'ativo';
        $id_empresa = !empty($_POST['id_empresa']) ? (int)$_POST['id_empresa'] : null;

        if (!$id) Response::error('Usuário inválido.');
        if ($nome === '' || $email === '') Response::error('Nome e e-mail são obrigatórios.');
        if (!filter_var($email, FILTER_VALIDATE_EMAIL)) Response::error('E-mail inválido.');

        // E-mail duplicado em outro usuário?
        $check = $db->prepare("SELECT id FROM usuarios WHERE email = ? AND id <> ? LIMIT 1");
        $check->execute([$email, $id]);
        if ($check->fetch()) Response::error('Já existe outro usuário com este e-mail.');

        // Se está vinculando a uma empresa, confirma que ela existe
        if ($id_empresa !== null) {
            $chkEmp = $db->prepare("SELECT id FROM empresas WHERE id = ? LIMIT 1");
            $chkEmp->execute([$id_empresa]);
            if (!$chkEmp->fetch()) {
                Response::error('Empresa selecionada não existe.');
            }
        }

        try {
            $upd = $db->prepare("
                UPDATE usuarios
                SET nome = ?, email = ?, telefone = ?, tipo_usuario = ?, status = ?, id_empresa = ?
                WHERE id = ?
            ");
            $upd->execute([
                $nome,
                $email,
                $telefone ?: null,
                $tipo,
                $status,
                $id_empresa,   // pode ser NULL
                $id,
            ]);

            // Atualiza a sessão se for o próprio usuário logado
            if (isset($_SESSION['usuario']['id']) && (int)$_SESSION['usuario']['id'] === $id) {
                $_SESSION['usuario']['nome']       = $nome;
                $_SESSION['usuario']['email']      = $email;
                $_SESSION['usuario']['id_empresa'] = $id_empresa;
            }

            Response::success('Usuário atualizado com sucesso.');
        } catch (Throwable $e) {
            Response::error('Erro ao atualizar usuário: ' . $e->getMessage(), 500);
        }
        break;
      
    
    // ---------- RESETAR SENHA ----------
    case 'resetar_senha':
        $id = (int)($_POST['id'] ?? 0);
        $novaSenha = gerarSenhaTemporaria();
        $hash = password_hash($novaSenha, PASSWORD_DEFAULT);

        $upd = $db->prepare("UPDATE usuarios SET senha_hash = ? WHERE id = ?");
        $upd->execute([$hash, $id]);

        Response::success('Senha resetada com sucesso.', ['nova_senha' => $novaSenha]);
        break;

    // ---------- EXCLUIR ----------
    case 'excluir':
        $id = (int)($_POST['id'] ?? 0);
        $del = $db->prepare("DELETE FROM usuarios WHERE id = ?");
        $del->execute([$id]);
        Response::success('Usuário excluído.');
        break;

    // ---------- LISTAR LEADS ELEGÍVEIS (para converter) ----------
    case 'leads_elegiveis':
        // Leads que ainda NÃO têm usuário criado (compara por e-mail)
        $stmt = $db->query("
            SELECT l.id, l.nome, l.email, l.telefone, l.cnpj, l.status_comercial
            FROM leads l
            LEFT JOIN usuarios u ON u.email = l.email
            WHERE u.id IS NULL
            ORDER BY l.data_envio DESC
        ");
        Response::json(['success' => true, 'items' => $stmt->fetchAll()]);
        break;

    // ---------- CONVERTER LEAD EM USUÁRIO ----------
    case 'converter_lead':
        $id_lead = (int)($_POST['id_lead'] ?? 0);
        if (!$id_lead) Response::error('Lead inválido.');

        $stmt = $db->prepare("SELECT * FROM leads WHERE id = ?");
        $stmt->execute([$id_lead]);
        $lead = $stmt->fetch();
        if (!$lead) Response::error('Lead não encontrado.');

        $check = $db->prepare("SELECT id FROM usuarios WHERE email = ? LIMIT 1");
        $check->execute([$lead['email']]);
        if ($check->fetch()) Response::error('Já existe um usuário com este e-mail.');

        $senhaTemp = gerarSenhaTemporaria();
        $hash = password_hash($senhaTemp, PASSWORD_DEFAULT);

        // Criar nova empresa se o lead tiver CNPJ e o admin pedir (checkbox)
        $criarEmpresa = !empty($_POST['criar_empresa']) && $lead['cnpj'];
        $id_empresa = null;

        $db->beginTransaction();
        try {
            if ($criarEmpresa) {
                // Cria empresa "placeholder" que o cliente completa depois
                $insEmp = $db->prepare("
                    INSERT INTO empresas (razao_social, cnpj, telefone, email_contato)
                    VALUES (?, ?, ?, ?)
                ");
                $insEmp->execute([
                    'Empresa de ' . $lead['nome'], // razão social provisória
                    $lead['cnpj'],
                    $lead['telefone'] ?: null,
                    $lead['email'],
                ]);
                $id_empresa = (int)$db->lastInsertId();
            }

            $ins = $db->prepare("
                INSERT INTO usuarios (nome, email, senha_hash, telefone, tipo_usuario, status, id_empresa)
                VALUES (?, ?, ?, ?, 'comum', 'ativo', ?)
            ");
            $ins->execute([$lead['nome'], $lead['email'], $hash, $lead['telefone'] ?: null, $id_empresa]);
            $id_novo_usuario = $db->lastInsertId();

            $updLead = $db->prepare("UPDATE leads SET status_comercial = 'CLIENTE ATIVO' WHERE id = ?");
            $updLead->execute([$id_lead]);

            $db->commit();

            Response::success(
                'Lead convertido em usuário com sucesso!',
                [
                    'id_usuario'       => $id_novo_usuario,
                    'senha_temporaria' => $senhaTemp,
                    'empresa_criada'   => $criarEmpresa,
                ]
            );
        } catch (Throwable $e) {
            $db->rollBack();
            Response::error('Erro ao converter lead: ' . $e->getMessage(), 500);
        }
        break;

    // ---------- LISTAR EMPRESAS (para select) ----------
    case 'empresas_disponiveis':
        $stmt = $db->query("
            SELECT id, razao_social, cnpj
            FROM empresas
            ORDER BY razao_social
        ");
        Response::json(['success' => true, 'items' => $stmt->fetchAll()]);
        break;
    

    default:
        Response::error('Ação inválida.', 404);
}
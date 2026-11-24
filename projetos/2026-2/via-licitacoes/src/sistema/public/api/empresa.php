<?php
require_once __DIR__ . '/../../src/config/config.php';
require_once __DIR__ . '/../../src/config/database.php';
require_once __DIR__ . '/../../src/core/Auth.php';
require_once __DIR__ . '/../../src/core/Response.php';

Auth::exigirLogin();
$user = Auth::usuario();
$db = Database::getConnection();

if ($_SERVER['REQUEST_METHOD'] !== 'POST') Response::error('Método não permitido.', 405);

$razao_social  = trim($_POST['razao_social'] ?? '');
$nome_fantasia = trim($_POST['nome_fantasia'] ?? '');
$cnpj          = trim($_POST['cnpj'] ?? '');
$telefone      = trim($_POST['telefone'] ?? '');
$email_contato = trim($_POST['email_contato'] ?? '');
$endereco      = trim($_POST['endereco'] ?? '');
$uf            = strtoupper(trim($_POST['uf'] ?? ''));
$municipio     = trim($_POST['municipio'] ?? '');
$cnae_principal     = trim($_POST['cnae_principal'] ?? '');
$natureza_juridica  = trim($_POST['natureza_juridica'] ?? '');

if ($razao_social === '') Response::error('Razão Social é obrigatória.');
if ($cnpj === '')         Response::error('CNPJ é obrigatório.');
if ($uf !== '' && strlen($uf) !== 2) Response::error('UF inválida.');

$stmt = $db->prepare("SELECT id_empresa FROM usuarios WHERE id = ? LIMIT 1");
$stmt->execute([$user['id']]);
$id_empresa = $stmt->fetchColumn();

$checkCnpj = $db->prepare("SELECT id FROM empresas WHERE cnpj = ? LIMIT 1");
$checkCnpj->execute([$cnpj]);
$empresaComMesmoCnpj = $checkCnpj->fetchColumn();

if ($empresaComMesmoCnpj && (int)$empresaComMesmoCnpj !== (int)$id_empresa) {
    Response::error('Este CNPJ já está cadastrado em outra empresa.');
}

if ($id_empresa) {
    $upd = $db->prepare("
        UPDATE empresas
        SET razao_social = ?, nome_fantasia = ?, cnpj = ?, telefone = ?,
            email_contato = ?, endereco = ?, uf = ?, municipio = ?,
            cnae_principal = ?, natureza_juridica = ?
        WHERE id = ?
    ");
    $upd->execute([
        $razao_social, $nome_fantasia ?: null, $cnpj, $telefone ?: null,
        $email_contato ?: null, $endereco ?: null, $uf ?: null, $municipio ?: null,
        $cnae_principal ?: null, $natureza_juridica ?: null,
        $id_empresa
    ]);
    Response::success('Dados atualizados com sucesso.');
} else {
    $db->beginTransaction();
    try {
        $ins = $db->prepare("
            INSERT INTO empresas
            (razao_social, nome_fantasia, cnpj, telefone, email_contato, endereco, uf, municipio, cnae_principal, natureza_juridica)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ");
        $ins->execute([
            $razao_social, $nome_fantasia ?: null, $cnpj, $telefone ?: null,
            $email_contato ?: null, $endereco ?: null, $uf ?: null, $municipio ?: null,
            $cnae_principal ?: null, $natureza_juridica ?: null
        ]);
        $novoId = $db->lastInsertId();

        $upd = $db->prepare("UPDATE usuarios SET id_empresa = ?, eh_owner = 1 WHERE id = ?");
        $upd->execute([$novoId, $user['id']]);

        $_SESSION['usuario']['id_empresa'] = (int)$novoId;

        $db->commit();
        Response::success('Empresa cadastrada com sucesso.');
    } catch (Throwable $e) {
        $db->rollBack();
        Response::error('Erro ao salvar: ' . $e->getMessage(), 500);
    }
}
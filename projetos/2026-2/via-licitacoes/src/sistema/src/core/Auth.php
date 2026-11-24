<?php
/**
 * Autenticação e controle de sessão
 * Admin é verificado via constantes em config/admin.php (hardcoded).
 * Usuários comuns são verificados na tabela `usuarios`.
 */

require_once __DIR__ . '/../config/config.php';
require_once __DIR__ . '/../config/database.php';
require_once __DIR__ . '/../config/admin.php';

class Auth
{
    /**
     * Tenta autenticar. Retorna array com dados do usuário ou null.
     */
    public static function login(string $email, string $senha): ?array
    {
        $email = trim(strtolower($email));

        // 1) Verifica admin hardcoded
        if ($email === strtolower(ADMIN_EMAIL) && password_verify($senha, ADMIN_SENHA_HASH)) {
            $_SESSION['usuario'] = [
                'id'        => 0,
                'nome'      => ADMIN_NOME,
                'email'     => ADMIN_EMAIL,
                'tipo'      => 'admin',
                'id_empresa'=> null,
            ];
            $_SESSION['logado_em'] = time();
            return $_SESSION['usuario'];
        }

        // 2) Verifica usuário comum no banco
        $db = Database::getConnection();
        $stmt = $db->prepare("SELECT id, nome, email, senha_hash, tipo_usuario, status, id_empresa FROM usuarios WHERE email = ? LIMIT 1");
        $stmt->execute([$email]);
        $user = $stmt->fetch();

        if (!$user) return null;
        if ($user['status'] !== 'ativo') return null;
        if (!password_verify($senha, $user['senha_hash'])) return null;

        // Atualiza último acesso
        $upd = $db->prepare("UPDATE usuarios SET ultimo_acesso = NOW() WHERE id = ?");
        $upd->execute([$user['id']]);
        $_SESSION['usuario'] = [
            'id'         => (int)$user['id'],
            'nome'       => $user['nome'],
            'email'      => $user['email'],
            'tipo'       => $user['tipo_usuario'],
            'id_empresa' => isset($user['id_empresa']) ? (int)$user['id_empresa'] : null,
        ];

        $_SESSION['logado_em'] = time();

        return $_SESSION['usuario'];
    }

    public static function logout(): void
    {
        $_SESSION = [];
        if (ini_get('session.use_cookies')) {
            $p = session_get_cookie_params();
            setcookie(session_name(), '', time() - 42000, $p['path'], $p['domain'], $p['secure'], $p['httponly']);
        }
        session_destroy();
    }

    public static function usuario(): ?array
    {
        return $_SESSION['usuario'] ?? null;
    }

    public static function logado(): bool
    {
        return isset($_SESSION['usuario']);
    }

    public static function isAdmin(): bool
    {
        return self::logado() && ($_SESSION['usuario']['tipo'] ?? '') === 'admin';
    }

    /**
     * Redireciona se não estiver logado
     */
    public static function exigirLogin(): void
    {
        if (!self::logado()) {
            header('Location: ' . BASE_URL . '/index.php?login=required');
            exit;
        }
    }

    public static function exigirAdmin(): void
    {
        self::exigirLogin();
        if (!self::isAdmin()) {
            header('Location: ' . BASE_URL . '/app/index.php');
            exit;
        }
    }
}
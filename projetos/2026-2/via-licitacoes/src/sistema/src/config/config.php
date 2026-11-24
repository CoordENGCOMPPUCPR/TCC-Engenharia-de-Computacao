<?php
/**
 * Configurações globais da aplicação
 */

// Evita acesso direto
if (!defined('VIA_LICITACOES')) {
    define('VIA_LICITACOES', true);
}

// Ambiente
define('APP_ENV', 'development'); // 'production' em produção
define('APP_DEBUG', true);

// URL base (ajuste se mudar de pasta)
define('BASE_URL', 'http://localhost/via-licitacoes/public');

// Caminhos físicos
define('ROOT_PATH', dirname(__DIR__, 2));
define('SRC_PATH', ROOT_PATH . '/src');
define('STORAGE_PATH', ROOT_PATH . '/storage');
define('PDFS_PATH', STORAGE_PATH . '/pdfs');
define('LOGS_PATH', STORAGE_PATH . '/logs');

// Timezone
date_default_timezone_set('America/Sao_Paulo');

// Exibição de erros em dev
if (APP_DEBUG) {
    ini_set('display_errors', 1);
    ini_set('display_startup_errors', 1);
    error_reporting(E_ALL);
} else {
    ini_set('display_errors', 0);
    error_reporting(0);
}

// Sessão
if (session_status() === PHP_SESSION_NONE) {
    session_start();
}
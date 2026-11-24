<?php
/**
 * Admin hardcoded (conforme solicitado)
 * Não depende do banco — reseta o banco e continua funcionando.
 */

if (!defined('VIA_LICITACOES')) {
    define('VIA_LICITACOES', true);
}

// Credenciais do admin master
define('ADMIN_EMAIL', 'admin@vialicitacoes.com.br');
// Senha em texto puro: Admin@123
// Hash gerado com password_hash('Admin@123', PASSWORD_DEFAULT)
define('ADMIN_SENHA_HASH', '$2y$10$FrtWGjX.vD9f2Y6BcaAl5u3.fsGYC4SVJjFU1XzhsJB1.SM0oLIDy');

// Nome exibido
define('ADMIN_NOME', 'Administrador Via Licitações');

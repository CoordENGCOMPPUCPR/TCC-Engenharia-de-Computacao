<?php
/**
 * Helper para respostas JSON padronizadas
 */

if (!defined('VIA_LICITACOES')) {
    define('VIA_LICITACOES', true);
}

class Response
{
    public static function json(array $data, int $status = 200): void
    {
        http_response_code($status);
        header('Content-Type: application/json; charset=utf-8');
        echo json_encode($data, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
        exit;
    }

    public static function success($message = 'OK', array $extra = []): void
    {
        self::json(array_merge(['success' => true, 'message' => $message], $extra));
    }

    public static function error($message = 'Erro', int $status = 400, array $extra = []): void
    {
        self::json(array_merge(['success' => false, 'message' => $message], $extra), $status);
    }
}
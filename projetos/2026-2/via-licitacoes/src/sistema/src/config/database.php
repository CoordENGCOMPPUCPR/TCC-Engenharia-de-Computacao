<?php
/**
 * Conexão PDO com MySQL
 */

require_once __DIR__ . '/config.php';

class Database
{
    private static ?PDO $instance = null;

    public static function getConnection(): PDO
    {
        if (self::$instance === null) {
            $host = 'localhost';
            $dbname = 'via_licitacoes';
            $user = 'root';
            $pass = ''; // XAMPP padrão
            $charset = 'utf8mb4';

            $dsn = "mysql:host={$host};dbname={$dbname};charset={$charset}";

            try {
                self::$instance = new PDO($dsn, $user, $pass, [
                    PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
                    PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
                    PDO::ATTR_EMULATE_PREPARES => false,
                ]);
            } catch (PDOException $e) {
                if (APP_DEBUG) {
                    die('Erro de conexão: ' . $e->getMessage());
                }
                die('Erro ao conectar ao banco de dados.');
            }
        }

        return self::$instance;
    }
}
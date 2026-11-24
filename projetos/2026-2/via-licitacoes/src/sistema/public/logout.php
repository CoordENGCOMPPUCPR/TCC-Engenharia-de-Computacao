<?php
require_once __DIR__ . '/../src/config/config.php';
require_once __DIR__ . '/../src/core/Auth.php';

Auth::logout();
header('Location: ' . BASE_URL . '/index.php');
exit;
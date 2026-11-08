<?php
declare(strict_types=1);

use App\Env;

require_once __DIR__ . '/autoload.php';

define('APP_ROOT', dirname(__DIR__));

mb_internal_encoding('UTF-8');
date_default_timezone_set('UTC');   // همه زمان‌ها در دیتابیس به وقت UTC ذخیره می‌شوند

Env::load(APP_ROOT . '/.env');

if (Env::bool('APP_DEBUG', false)) {
    ini_set('display_errors', '1');
    error_reporting(E_ALL);
} else {
    ini_set('display_errors', '0');
}

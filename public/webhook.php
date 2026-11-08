<?php
declare(strict_types=1);

/**
 * نقطه ورود وب‌هوک تلگرام (فقط برای هاست؛ روی کامپیوتر خودتان از bin/poll.php استفاده کنید).
 */

require __DIR__ . '/../src/bootstrap.php';

use App\Bot\Bot;
use App\Env;
use App\Telegram\Api;

// فقط درخواست‌هایی که کلید مخفی درست دارند (همان WEBHOOK_SECRET) پردازش می‌شوند
$secret = (string) Env::get('WEBHOOK_SECRET', '');

if ($secret === '') {
    http_response_code(503);
    exit('webhook secret is not configured');
}

$header = (string) ($_SERVER['HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN'] ?? '');

if (!hash_equals($secret, $header)) {
    http_response_code(403);
    exit('forbidden');
}

$update = json_decode((string) file_get_contents('php://input'), true);

if (!is_array($update)) {
    http_response_code(400);
    exit('bad request');
}

try {
    (new Bot(Api::fromEnv()))->handle($update);
} catch (Throwable $e) {
    // همیشه 200 برمی‌گردانیم تا تلگرام همان پیام را بی‌نهایت دوباره نفرستد.
    // فقط اگر APP_DEBUG=1 باشد خطا در storage/error.log نوشته می‌شود.
    if (Env::bool('APP_DEBUG', false)) {
        @file_put_contents(
            APP_ROOT . '/storage/error.log',
            gmdate('c') . ' ' . $e->getMessage() . ' @ ' . basename($e->getFile()) . ':' . $e->getLine() . "\n",
            FILE_APPEND
        );
    }
}

echo 'OK';

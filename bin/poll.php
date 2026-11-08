<?php
declare(strict_types=1);

/**
 * اجرای ربات به روش polling (برای تست روی کامپیوتر خودتان، بدون هاست و HTTPS).
 * اجرا:  php bin/poll.php      توقف: Ctrl+C
 *
 * نکته: وب‌هوک و polling هم‌زمان نمی‌شوند؛ این اسکریپت در شروع، وب‌هوک را حذف می‌کند.
 */

require __DIR__ . '/../src/bootstrap.php';

use App\Bot\Bot;
use App\Telegram\Api;
use App\Telegram\TelegramNetworkException;

set_time_limit(0);

$api = Api::fromEnv();
$bot = new Bot($api);

try {
    $me = $api->getMe();
    $api->deleteWebhook(false);
} catch (Throwable $e) {
    fwrite(STDERR, "❌ اتصال به تلگرام ناموفق بود: " . $e->getMessage() . "\n");
    fwrite(STDERR, "   اگر فیلترشکن دارید روشن کنید، یا TELEGRAM_PROXY را در .env تنظیم کنید.\n");
    exit(1);
}

echo "✅ ربات @" . ($me['username'] ?? '?') . " فعال شد (polling). برای توقف Ctrl+C بزنید.\n";

$offset = 0;

while (true) {
    try {
        $updates = $api->getUpdates($offset, 25);
    } catch (TelegramNetworkException $e) {
        fwrite(STDERR, "⚠️ " . $e->getMessage() . " (۳ ثانیه بعد دوباره تلاش می‌شود)\n");
        sleep(3);
        continue;
    } catch (Throwable $e) {
        fwrite(STDERR, "⚠️ " . $e->getMessage() . "\n");
        sleep(3);
        continue;
    }

    foreach ($updates as $update) {
        $offset = (int) $update['update_id'] + 1;

        try {
            $bot->handle($update);
        } catch (Throwable $e) {
            fwrite(STDERR, "❌ خطا در پردازش پیام: " . $e->getMessage()
                . " (" . basename($e->getFile()) . ":" . $e->getLine() . ")\n");
        }
    }
}

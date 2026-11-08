<?php
declare(strict_types=1);

/** حذف وب‌هوک (برای برگشت به polling). اجرا:  php bin/delete_webhook.php */

require __DIR__ . '/../src/bootstrap.php';

use App\Telegram\Api;

try {
    Api::fromEnv()->deleteWebhook(false);
    echo "✅ وب‌هوک حذف شد.\n";
} catch (Throwable $e) {
    fwrite(STDERR, "❌ " . $e->getMessage() . "\n");
    exit(1);
}

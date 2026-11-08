<?php
declare(strict_types=1);

/**
 * ثبت وب‌هوک روی هاست (برای زمان انتقال نهایی).
 * قبلش در .env مقدار WEBHOOK_URL (آدرس https فایل webhook.php) و WEBHOOK_SECRET را بگذارید.
 * اجرا:  php bin/set_webhook.php
 */

require __DIR__ . '/../src/bootstrap.php';

use App\Env;
use App\Telegram\Api;

$url = trim((string) Env::get('WEBHOOK_URL', ''));
$secret = trim((string) Env::get('WEBHOOK_SECRET', ''));

if ($url === '' || !str_starts_with($url, 'https://')) {
    fwrite(STDERR, "❌ WEBHOOK_URL باید با https:// شروع شود.\n");
    exit(1);
}

if ($secret === '' || preg_match('/^[A-Za-z0-9_-]{16,256}$/', $secret) !== 1) {
    fwrite(STDERR, "❌ WEBHOOK_SECRET باید ۱۶ تا ۲۵۶ کاراکتر از حروف لاتین، عدد، _ و - باشد.\n");
    exit(1);
}

try {
    Api::fromEnv()->setWebhook($url, $secret);
    echo "✅ وب‌هوک ثبت شد: {$url}\n";
} catch (Throwable $e) {
    fwrite(STDERR, "❌ " . $e->getMessage() . "\n");
    exit(1);
}

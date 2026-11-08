<?php
declare(strict_types=1);

/**
 * اجرای فایل‌های SQL پوشه migrations (به ترتیب نام) که هنوز اجرا نشده‌اند.
 * اجرا:  php bin/migrate.php
 */

require __DIR__ . '/../src/bootstrap.php';

use App\Db;

/** @return list<string> */
function splitSql(string $sql): array
{
    $lines = [];

    foreach (preg_split('/\r\n|\r|\n/', $sql) ?: [] as $line) {
        if (str_starts_with(trim($line), '--')) {
            continue;   // خط توضیح
        }

        $lines[] = $line;
    }

    $statements = [];

    foreach (explode(';', implode("\n", $lines)) as $part) {
        $part = trim($part);

        if ($part !== '') {
            $statements[] = $part;
        }
    }

    return $statements;
}

try {
    $pdo = Db::connect(false);
} catch (Throwable $e) {
    fwrite(STDERR, "❌ اتصال به دیتابیس ناموفق بود: " . $e->getMessage() . "\n");
    fwrite(STDERR, "   مقادیر DB_HOST / DB_NAME / DB_USER / DB_PASS را در .env بررسی کنید.\n");
    exit(1);
}

$pdo->exec(
    'CREATE TABLE IF NOT EXISTS schema_migrations (
        name VARCHAR(190) NOT NULL,
        applied_at DATETIME NOT NULL,
        PRIMARY KEY (name)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci'
);

$applied = [];

foreach ($pdo->query('SELECT name FROM schema_migrations')->fetchAll() as $row) {
    $applied[(string) $row['name']] = true;
}

$files = glob(APP_ROOT . '/migrations/*.sql') ?: [];
sort($files);

$count = 0;

foreach ($files as $file) {
    $name = basename($file);

    if (isset($applied[$name])) {
        continue;
    }

    echo "▶ اجرای {$name} ...\n";

    foreach (splitSql((string) file_get_contents($file)) as $statement) {
        $pdo->exec($statement);
    }

    $stmt = $pdo->prepare('INSERT INTO schema_migrations (name, applied_at) VALUES (?, ?)');
    $stmt->execute([$name, gmdate('Y-m-d H:i:s')]);

    $count++;
}

echo $count === 0
    ? "✅ دیتابیس به‌روز است (مهاجرت جدیدی نبود).\n"
    : "✅ {$count} مهاجرت اجرا شد.\n";

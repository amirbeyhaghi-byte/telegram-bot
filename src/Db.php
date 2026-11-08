<?php
declare(strict_types=1);

namespace App;

use PDO;

/** اتصال PDO به MySQL/MariaDB و چند تابع کمکی ساده */
final class Db
{
    private static ?PDO $pdo = null;

    public static function pdo(): PDO
    {
        if (self::$pdo === null) {
            self::$pdo = self::connect(false);
        }

        return self::$pdo;
    }

    /** $emulatePrepares=true فقط برای اسکریپت migrate (اجرای فایل‌های SQL) */
    public static function connect(bool $emulatePrepares): PDO
    {
        $dsn = sprintf(
            'mysql:host=%s;port=%d;dbname=%s;charset=utf8mb4',
            Env::get('DB_HOST', 'localhost'),
            Env::int('DB_PORT', 3306),
            Env::get('DB_NAME', '')
        );

        return new PDO($dsn, (string) Env::get('DB_USER', ''), (string) Env::get('DB_PASS', ''), [
            PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
            PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
            PDO::ATTR_EMULATE_PREPARES => $emulatePrepares,
        ]);
    }

    /** @return array<string,mixed>|null */
    public static function fetchOne(string $sql, array $params = []): ?array
    {
        $stmt = self::pdo()->prepare($sql);
        $stmt->execute($params);
        $row = $stmt->fetch();

        return $row === false ? null : $row;
    }

    /** @return list<array<string,mixed>> */
    public static function fetchAll(string $sql, array $params = []): array
    {
        $stmt = self::pdo()->prepare($sql);
        $stmt->execute($params);

        return $stmt->fetchAll();
    }

    /** تعداد ردیف‌های تغییرکرده */
    public static function execute(string $sql, array $params = []): int
    {
        $stmt = self::pdo()->prepare($sql);
        $stmt->execute($params);

        return $stmt->rowCount();
    }

    /** شناسه ردیف جدید */
    public static function insert(string $sql, array $params = []): int
    {
        $stmt = self::pdo()->prepare($sql);
        $stmt->execute($params);

        return (int) self::pdo()->lastInsertId();
    }
}

<?php
declare(strict_types=1);

namespace App\Services;

use App\Db;
use App\Support\Clock;

final class UserService
{
    public const STATUS_ACTIVE = 'active';
    public const STATUS_DISABLED = 'disabled';
    public const STATUS_MISSING = 'missing';

    /** @return array<string,mixed>|null */
    public static function findByPhone(string $phone): ?array
    {
        return Db::fetchOne(
            'SELECT * FROM users WHERE phone_number = ?',
            [Phone::normalize($phone)]
        );
    }

    /** @return array<string,mixed>|null */
    public static function findById(int $id): ?array
    {
        return Db::fetchOne('SELECT * FROM users WHERE id = ?', [$id]);
    }

    /**
     * کاربر جدید می‌سازد.
     * @throws \PDOException اگر شماره تکراری باشد (کد 23000)
     * @return array<string,mixed>
     */
    public static function create(
        string $firstName,
        string $lastName,
        string $phone,
        string $password
    ): array {
        $id = Db::insert(
            'INSERT INTO users (first_name, last_name, phone_number, password_hash, created_at, status)
             VALUES (?, ?, ?, ?, ?, ?)',
            [
                $firstName,
                $lastName,
                $phone,
                PasswordHasher::hash($password),
                Clock::now(),
                self::STATUS_ACTIVE,
            ]
        );

        $user = self::findById($id);

        if ($user === null) {
            throw new \RuntimeException('ساخت کاربر ناموفق بود.');
        }

        // هدیه ثبت‌نام: اشتراک رایگان ۳۰ روزه، مطابق نسخه پایتون
        $now = Clock::now();
        $end = gmdate('Y-m-d H:i:s', strtotime($now . ' UTC') + 30 * 86400);
        Db::execute(
            'INSERT INTO subscriptions (user_id, type, start_date, end_date, status, created_at) VALUES (?, ?, ?, ?, ?, ?)',
            [$id, 'free', $now, $end, 'active', $now]
        );

        return $user;
    }

    public static function touchLogin(int $userId): void
    {
        Db::execute('UPDATE users SET last_login_at = ? WHERE id = ?', [Clock::now(), $userId]);
    }

    /**
     * رمز عبور کاربر را به‌روزرسانی می‌کند (برای بازیابی رمز عبور).
     */
    public static function updatePassword(int $userId, string $newPassword): void
    {
        Db::execute(
            'UPDATE users SET password_hash = ? WHERE id = ?',
            [PasswordHasher::hash($newPassword), $userId]
        );
    }

    /** active / disabled / missing */
    public static function accountStatus(string $phone): string
    {
        $row = Db::fetchOne(
            'SELECT status FROM users WHERE phone_number = ?',
            [Phone::normalize($phone)]
        );

        if ($row === null) {
            return self::STATUS_MISSING;
        }

        return $row['status'] === self::STATUS_ACTIVE ? self::STATUS_ACTIVE : self::STATUS_DISABLED;
    }
}
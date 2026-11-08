<?php
declare(strict_types=1);

namespace App\Services;

final class PasswordHasher
{
    /** Argon2id (اگر هاست پشتیبانی کند، همان الگوی نسخه پایتون) وگرنه bcrypt */
    public static function hash(string $password): string
    {
        $algorithm = defined('PASSWORD_ARGON2ID') ? PASSWORD_ARGON2ID : PASSWORD_BCRYPT;

        return password_hash($password, $algorithm);
    }

    public static function verify(string $password, string $hash): bool
    {
        return password_verify($password, $hash);
    }
}

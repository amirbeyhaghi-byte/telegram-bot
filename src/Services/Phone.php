<?php
declare(strict_types=1);

namespace App\Services;

use App\Env;
use App\Support\Persian;

final class Phone
{
    /** همه قالب‌های رایج شماره ایرانی را به 09xxxxxxxxx تبدیل می‌کند */
    public static function normalize(?string $phone): string
    {
        $phone = Persian::toAscii($phone ?? '');
        $phone = preg_replace('/[^0-9+]/', '', $phone) ?? '';

        if (str_starts_with($phone, '+98')) {
            $phone = '0' . substr($phone, 3);
        } elseif (str_starts_with($phone, '0098')) {
            $phone = '0' . substr($phone, 4);
        } elseif (str_starts_with($phone, '98') && strlen($phone) === 12) {
            $phone = '0' . substr($phone, 2);
        } elseif (str_starts_with($phone, '9') && strlen($phone) === 10) {
            $phone = '0' . $phone;
        }

        return str_replace('+', '', $phone);
    }

    /** موبایل ایران: 09xxxxxxxxx (۱۱ رقم)؛ سایر شماره‌ها: ۸ تا ۱۵ رقم */
    public static function isValid(?string $phone): bool
    {
        $phone = $phone ?? '';

        if ($phone === '' || !ctype_digit($phone)) {
            return false;
        }

        if (str_starts_with($phone, '09')) {
            return strlen($phone) === 11;
        }

        return strlen($phone) >= 8 && strlen($phone) <= 15;
    }

    public static function isAdmin(?string $phone): bool
    {
        $admin = Env::get('ADMIN_PHONE');

        if ($admin === null || $admin === '' || $phone === null || $phone === '') {
            return false;
        }

        return self::normalize($phone) === self::normalize($admin);
    }
}

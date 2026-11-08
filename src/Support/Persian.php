<?php
declare(strict_types=1);

namespace App\Support;

final class Persian
{
    private const LATIN = ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9'];
    private const FARSI = ['۰', '۱', '۲', '۳', '۴', '۵', '۶', '۷', '۸', '۹'];
    private const ARABIC = ['٠', '١', '٢', '٣', '٤', '٥', '٦', '٧', '٨', '٩'];

    /** ارقام لاتین → فارسی (برای نمایش) */
    public static function digits(int|string $value): string
    {
        return str_replace(self::LATIN, self::FARSI, (string) $value);
    }

    /** ارقام فارسی و عربی → لاتین */
    public static function toAscii(string $value): string
    {
        return str_replace(self::ARABIC, self::LATIN, str_replace(self::FARSI, self::LATIN, $value));
    }
}

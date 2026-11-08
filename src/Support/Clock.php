<?php
declare(strict_types=1);

namespace App\Support;

final class Clock
{
    /** زمان فعلی UTC برای ذخیره در DATETIME */
    public static function now(): string
    {
        return gmdate('Y-m-d H:i:s');
    }
}

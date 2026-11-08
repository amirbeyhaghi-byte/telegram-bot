<?php
declare(strict_types=1);

namespace App\Bot;

/** نام وضعیت‌های گفتگو (معادل StatesGroup نسخه پایتون) */
final class States
{
    public const REG_FIRST_NAME = 'reg:first_name';
    public const REG_LAST_NAME = 'reg:last_name';
    public const REG_PHONE = 'reg:phone';
    public const REG_PASSWORD = 'reg:password';

    public const LOGIN_PHONE = 'login:phone';
    public const LOGIN_PASSWORD = 'login:password';

    // وضعیت‌های جدید برای فراموشی رمز
    public const FORGOT_PHONE = 'forgot:phone';
    public const FORGOT_PASSWORD = 'forgot:password';

    /** همه وضعیت‌های «واردشده» با این پیشوند شروع می‌شوند */
    public const MAIN_PREFIX = 'main:';
    public const MAIN_MENU = 'main:menu';
}
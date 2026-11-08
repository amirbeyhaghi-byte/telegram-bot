<?php
declare(strict_types=1);

namespace App\Bot;

use App\Services\Phone;
use App\Telegram\Keyboard;

/** کیبوردهای ربات (معادل app/keyboards نسخه پایتون) */
final class Keyboards
{
    public static function registration(): array
    {
        return Keyboard::reply([
            [Keyboard::text(Texts::BTN_REGISTER)],
            [Keyboard::text(Texts::BTN_LOGIN)],
            [Keyboard::text(Texts::BTN_FORGOT_PASSWORD)],
            [Keyboard::text(Texts::BTN_ABOUT), Keyboard::text(Texts::BTN_CONTACT)],
        ]);
    }

    /** کیبورد ارسال شماره برای ثبت‌نام (فقط Contact) */
    public static function phone(): array
    {
        return Keyboard::reply([[Keyboard::contact(Texts::BTN_SHARE_PHONE)]], true);
    }

    /** کیبورد صفحه ورود: Contact + فراموشی رمز */
    public static function loginPhone(): array
    {
        return Keyboard::reply([
            [Keyboard::contact(Texts::BTN_SHARE_PHONE)],
            [Keyboard::text(Texts::BTN_FORGOT_PASSWORD)],
        ], true);
    }

    /** کیبورد صفحه فراموشی رمز: Contact + بازگشت به ورود */
    public static function forgotPhone(): array
    {
        return Keyboard::reply([
            [Keyboard::contact(Texts::BTN_SHARE_PHONE)],
            [Keyboard::text(Texts::BTN_LOGIN)],
        ], true);
    }

    public static function login(): array
    {
        return Keyboard::reply([
            [Keyboard::text(Texts::BTN_LOGIN)],
            [Keyboard::text(Texts::BTN_REGISTER)],
            [Keyboard::text(Texts::BTN_FORGOT_PASSWORD)],
            [Keyboard::text(Texts::BTN_CONTACT)],
        ]);
    }

    public static function subscriptionMenu(): array
    {
        return Keyboard::reply([
            [Keyboard::text('📅 اشتراک ماهانه - ۱۰۰٬۰۰۰ تومان')],
            [Keyboard::text('📆 اشتراک ۶ ماهه - ۵۰۰٬۰۰۰ تومان')],
            [Keyboard::text('🗓 اشتراک سالیانه - ۸۰۰٬۰۰۰ تومان')],
            [Keyboard::text('🎁 کد اشتراک هدیه')],
            [Keyboard::text('🔙 بازگشت به منوی اصلی')],
        ]);
    }

    public static function mainMenu(?string $phone = null): array
    {
        $rows = [
            [Keyboard::text(Texts::BTN_TEMPERAMENT)],
            [Keyboard::text(Texts::BTN_FOOD)],
            [Keyboard::text(Texts::BTN_ACCOUNT), Keyboard::text(Texts::BTN_SUBSCRIPTION)],
        ];

        if (Phone::isAdmin($phone)) {
            $rows[] = [Keyboard::text(Texts::BTN_ADMIN)];
        }

        $rows[] = [Keyboard::text(Texts::BTN_LOGOUT)];

        return Keyboard::reply($rows);
    }
}
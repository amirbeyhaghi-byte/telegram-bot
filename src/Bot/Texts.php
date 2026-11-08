<?php
declare(strict_types=1);

namespace App\Bot;

/** متن دکمه‌ها و پیام‌های ثابت (همان متن‌های نسخه پایتون) */
final class Texts
{
    public const BTN_REGISTER = "📝 ثبت\u{200C}نام";
    public const BTN_LOGIN = "🔐 ورود به حساب";
    public const BTN_FORGOT_PASSWORD = "🔑 فراموشی رمز عبور";
    public const BTN_ABOUT = "ℹ️ درباره سامانه";
    public const BTN_CONTACT = "📞 ارتباط با ما";
    public const BTN_SHARE_PHONE = "📱 ارسال شماره موبایل";

    public const BTN_TEMPERAMENT = "🌿 مزاج شناسی";
    public const BTN_FOOD = "🍎 طبع شناسی خوراکی ها";
    public const BTN_ACCOUNT = "👤 حساب کاربری";
    public const BTN_SUBSCRIPTION = "💳 اشتراک";
    public const BTN_ADMIN = "🔐 پنل مدیریت";
    public const BTN_LOGOUT = "🚪 خروج از حساب";

    public const START =
        "🌿 به سامانه مزاج شناسی بیهقی خوش آمدید.\n\n"
        . "این سامانه با هدف ارائه خدمات مرتبط با "
        . "مزاج‌شناسی و شناخت طبع خوراکی‌ها طراحی شده است.\n\n"
        . "برای استفاده از خدمات سامانه، ابتدا باید ثبت‌نام کنید.";

    public const ABOUT =
        "ℹ️ <b>درباره سامانه</b>\n\n"
        . "سامانه مزاج‌شناسی بیهقی برای شناخت مزاج افراد "
        . "و طبع خوراکی‌ها بر پایه طب سنتی طراحی شده است.\n\n"
        . "برای استفاده از خدمات، ثبت‌نام کنید یا وارد حساب خود شوید.";

    public const CONTACT =
        "📞 <b>ارتباط با ما</b>\n\n"
        . "جهت ارتباط با مدیر ربات، لطفاً به آیدی زیر پیام دهید:\n\n"
        . "👤 <b>@Amiirbeyhaghi</b>\n\n"
        . "پاسخگویی در اسرع وقت انجام می‌شود. 🙏";

    public const ACCOUNT_DISABLED =
        "⛔ <b>حساب کاربری شما غیرفعال شده است.</b>\n\n"
        . "برای پیگیری با مدیر سامانه تماس بگیرید.";

    public const ACCOUNT_MISSING =
        "⚠️ اطلاعات حساب شما پیدا نشد.\n\n"
        . "لطفاً دوباره وارد حساب شوید.";

    public const COMING_SOON =
        "🚧 این بخش در مرحله‌های بعدیِ نسخه PHP اضافه می‌شود.";

    public const NO_STATE_HINT =
        "برای شروع از دکمه‌های زیر استفاده کنید یا /start را بزنید.";
}
<?php
declare(strict_types=1);

namespace App\Bot;

use App\Services\Phone;
use App\State\StateStore;

/**
 * منوی اصلی. در مرحله ۱ فقط «خروج از حساب» فعال است؛
 * بقیه بخش‌ها در مرحله‌های بعد اضافه می‌شوند.
 */
final class MenuHandler
{
    public function __construct(private StateStore $states)
    {
    }

    /** @param array<string,mixed> $data */
    public function handle(Context $ctx, ?string $text, array $data): void
    {
        $phone = (string) ($data['phone_number'] ?? '');

        switch ($text) {
            case Texts::BTN_LOGOUT:
                $this->states->clear($ctx->userId);

                $ctx->reply(
                    "🚪 <b>با موفقیت از حساب کاربری خارج شدید.</b>\n\n"
                    . 'برای استفاده از سامانه، می‌توانید وارد حساب شوید یا یک حساب جدید ثبت کنید.',
                    ['reply_markup' => Keyboards::registration()]
                );
                return;

            case Texts::BTN_TEMPERAMENT:
            case Texts::BTN_FOOD:
            case Texts::BTN_ACCOUNT:
            case Texts::BTN_SUBSCRIPTION:
                $ctx->reply(Texts::COMING_SOON);
                return;

            case Texts::BTN_ADMIN:
                if (!Phone::isAdmin($phone)) {
                    $ctx->reply('⛔ شما دسترسی به پنل مدیریت ندارید.');
                    return;
                }

                $ctx->reply(Texts::COMING_SOON);
                return;
        }

        $ctx->reply(
            'لطفاً یکی از گزینه‌های منو را انتخاب کنید.',
            ['reply_markup' => Keyboards::mainMenu($phone)]
        );
    }
}

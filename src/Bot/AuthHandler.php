<?php
declare(strict_types=1);

namespace App\Bot;

use App\Services\PasswordHasher;
use App\Services\Phone;
use App\Services\UserService;
use App\Services\Validation;
use App\State\StateStore;

final class AuthHandler
{
    public function __construct(private StateStore $states)
    {
    }

    public static function contactBelongsToSender(Context $ctx): bool
    {
        $contact = $ctx->contact;

        return $contact !== null
            && isset($contact['user_id'])
            && (int) $contact['user_id'] === $ctx->userId;
    }

    public function startRegistration(Context $ctx): void
    {
        $this->states->set($ctx->userId, States::REG_FIRST_NAME, []);
        $ctx->reply("📝 <b>ثبت‌نام در سامانه</b>\n\nلطفاً نام خود را وارد کنید:");
    }

    public function startLogin(Context $ctx): void
    {
        $this->states->set($ctx->userId, States::LOGIN_PHONE, []);

        $ctx->reply(
            "🔐 <b>ورود به حساب</b>\n\n"
            . "برای امنیت حساب شما، ورود فقط با شماره موبایلِ همین حساب تلگرام ممکن است.\n\n"
            . "لطفاً با دکمه زیر شماره خود را ارسال کنید.\n"
            . "اگر رمز عبور خود را فراموش کرده‌اید، از دکمه «" . Texts::BTN_FORGOT_PASSWORD . "» استفاده کنید.\n"
            . "برای انصراف /start را بزنید.",
            ['reply_markup' => Keyboards::loginPhone()]
        );
    }

    public function startForgotPassword(Context $ctx): void
    {
        $this->states->set($ctx->userId, States::FORGOT_PHONE, []);

        $ctx->reply(
            "🔑 <b>فراموشی رمز عبور</b>\n\n"
            . "برای بازیابی رمز عبور، لطفاً شماره موبایل خود را با استفاده از دکمه زیر ارسال کنید.\n\n"
            . "⚠️ شماره باید متعلق به همین حساب تلگرام باشد.\n"
            . "اگر یادتان آمد، از دکمه «" . Texts::BTN_LOGIN . "» به صفحه ورود برگردید.\n"
            . "برای انصراف /start را بزنید.",
            ['reply_markup' => Keyboards::forgotPhone()]
        );
    }

    /** @param array<string,mixed> $data */
    public function handle(Context $ctx, string $state, array $data): void
    {
        switch ($state) {
            case States::REG_FIRST_NAME:
                $this->registrationFirstName($ctx, $data);
                break;
            case States::REG_LAST_NAME:
                $this->registrationLastName($ctx, $data);
                break;
            case States::REG_PHONE:
                $this->registrationPhone($ctx, $data);
                break;
            case States::REG_PASSWORD:
                $this->registrationPassword($ctx, $data);
                break;
            case States::LOGIN_PHONE:
                $this->loginPhone($ctx);
                break;
            case States::LOGIN_PASSWORD:
                $this->loginPassword($ctx, $data);
                break;
            case States::FORGOT_PHONE:
                $this->forgotPhone($ctx);
                break;
            case States::FORGOT_PASSWORD:
                $this->forgotPassword($ctx, $data);
                break;
        }
    }

    /** @param array<string,mixed> $data */
    private function registrationFirstName(Context $ctx, array $data): void
    {
        [$name, $error] = Validation::validateName($ctx->text);

        if ($error !== null) {
            $ctx->reply($error);
            return;
        }

        $this->states->set(
            $ctx->userId,
            States::REG_LAST_NAME,
            array_merge($data, ['first_name' => $name])
        );

        $ctx->reply('لطفاً نام خانوادگی خود را وارد کنید:');
    }

    /** @param array<string,mixed> $data */
    private function registrationLastName(Context $ctx, array $data): void
    {
        [$name, $error] = Validation::validateName($ctx->text);

        if ($error !== null) {
            $ctx->reply($error);
            return;
        }

        $this->states->set(
            $ctx->userId,
            States::REG_PHONE,
            array_merge($data, ['last_name' => $name])
        );

        $ctx->reply(
            "📱 لطفاً شماره موبایل خود را با استفاده از دکمه زیر ارسال کنید.\n\n"
            . "⚠️ شماره باید متعلق به خود شما باشد.",
            ['reply_markup' => Keyboards::phone()]
        );
    }

    /** @param array<string,mixed> $data */
    private function registrationPhone(Context $ctx, array $data): void
    {
        if ($ctx->contact === null) {
            $ctx->reply(
                "⚠️ لطفاً شماره موبایل خود را فقط با دکمه «" . Texts::BTN_SHARE_PHONE . "» ارسال کنید.",
                ['reply_markup' => Keyboards::phone()]
            );
            return;
        }

        if (!self::contactBelongsToSender($ctx)) {
            $ctx->reply(
                "⛔ این شماره متعلق به حساب تلگرام شما نیست.\n\n"
                . "ثبت‌نام فقط با شماره موبایل همین حساب تلگرام ممکن است.",
                ['reply_markup' => Keyboards::phone()]
            );
            return;
        }

        $phone = Phone::normalize((string) ($ctx->contact['phone_number'] ?? ''));

        if (!Phone::isValid($phone)) {
            $ctx->reply('⚠️ شماره موبایل معتبر نیست.', ['reply_markup' => Keyboards::phone()]);
            return;
        }

        if (UserService::findByPhone($phone) !== null) {
            $this->states->clear($ctx->userId);

            $ctx->reply(
                "⚠️ این شماره موبایل قبلاً در سامانه ثبت شده است.\n\n"
                . "لطفاً از گزینه «" . Texts::BTN_LOGIN . "» استفاده کنید.",
                ['reply_markup' => Keyboards::login()]
            );
            return;
        }

        $this->states->set(
            $ctx->userId,
            States::REG_PASSWORD,
            array_merge($data, ['phone_number' => $phone])
        );

        $ctx->reply('🔐 لطفاً یک رمز عبور برای حساب خود انتخاب کنید:');
    }

    /** @param array<string,mixed> $data */
    private function registrationPassword(Context $ctx, array $data): void
    {
        $password = trim($ctx->text ?? '');

        $ctx->deleteIncoming();

        if ($password === '') {
            $ctx->reply('⚠️ لطفاً رمز عبور را وارد کنید.');
            return;
        }

        $phone = (string) ($data['phone_number'] ?? '');

        $passwordError = Validation::validatePassword($password, $phone);

        if ($passwordError !== null) {
            $ctx->reply($passwordError);
            return;
        }

        $firstName = (string) ($data['first_name'] ?? '');
        $lastName = (string) ($data['last_name'] ?? '');

        if ($firstName === '' || $lastName === '' || $phone === '') {
            $this->states->clear($ctx->userId);

            $ctx->reply(
                "⚠️ اطلاعات ثبت‌نام کامل نیست.\n\nلطفاً دوباره ثبت‌نام را شروع کنید.",
                ['reply_markup' => Keyboards::registration()]
            );
            return;
        }

        try {
            if (UserService::findByPhone($phone) !== null) {
                throw new \DomainException('exists');
            }

            $user = UserService::create($firstName, $lastName, $phone, $password);
        } catch (\DomainException | \PDOException $e) {
            $this->states->clear($ctx->userId);

            $ctx->reply(
                '⚠️ این شماره موبایل قبلاً ثبت شده است.',
                ['reply_markup' => Keyboards::login()]
            );
            return;
        }

        $savedPhone = (string) $user['phone_number'];

        $this->states->set($ctx->userId, States::MAIN_MENU, ['phone_number' => $savedPhone]);

        $ctx->reply(
            "<b>🎉 ثبت‌نام با موفقیت انجام شد.</b>\n\n"
            . 'یک دوره رایگان ۳۰روزه برای شما فعال شد و اکنون می‌توانید از خدمات سامانه استفاده کنید.',
            ['reply_markup' => Keyboards::mainMenu($savedPhone)]
        );
    }

    private function loginPhone(Context $ctx): void
    {
        if ($ctx->contact === null) {
            $ctx->reply(
                "⚠️ لطفاً شماره موبایل خود را فقط با دکمه «" . Texts::BTN_SHARE_PHONE . "» ارسال کنید.",
                ['reply_markup' => Keyboards::phone()]
            );
            return;
        }

        if (!self::contactBelongsToSender($ctx)) {
            $ctx->reply(
                "⛔ این شماره متعلق به حساب تلگرام شما نیست.\n\n"
                . 'ورود فقط با شماره موبایل همین حساب تلگرام امکان‌پذیر است.',
                ['reply_markup' => Keyboards::phone()]
            );
            return;
        }

        $phone = Phone::normalize((string) ($ctx->contact['phone_number'] ?? ''));

        $user = UserService::findByPhone($phone);

        if ($user === null) {
            $this->states->clear($ctx->userId);

            $ctx->reply(
                "❌ حسابی با این شماره موبایل پیدا نشد.\n\nلطفاً ابتدا ثبت‌نام کنید.",
                ['reply_markup' => Keyboards::registration()]
            );
            return;
        }

        $this->states->set(
            $ctx->userId,
            States::LOGIN_PASSWORD,
            ['phone_number' => (string) $user['phone_number']]
        );

        $ctx->reply('🔐 لطفاً رمز عبور خود را وارد کنید:');
    }

    /** @param array<string,mixed> $data */
    private function loginPassword(Context $ctx, array $data): void
    {
        $password = trim($ctx->text ?? '');

        $ctx->deleteIncoming();

        if ($password === '') {
            $ctx->reply('⚠️ لطفاً رمز عبور را وارد کنید.');
            return;
        }

        $phone = (string) ($data['phone_number'] ?? '');

        if ($phone === '') {
            $this->states->clear($ctx->userId);

            $ctx->reply(
                "⚠️ اطلاعات ورود پیدا نشد.\n\nلطفاً دوباره وارد حساب شوید.",
                ['reply_markup' => Keyboards::registration()]
            );
            return;
        }

        $user = UserService::findByPhone($phone);

        if ($user === null) {
            $this->states->clear($ctx->userId);

            $ctx->reply('❌ کاربر پیدا نشد.', ['reply_markup' => Keyboards::registration()]);
            return;
        }

        if (!PasswordHasher::verify($password, (string) $user['password_hash'])) {
            $ctx->reply("❌ رمز عبور اشتباه است.\n\nلطفاً دوباره رمز عبور را وارد کنید.");
            return;
        }

        if ($user['status'] !== UserService::STATUS_ACTIVE) {
            $this->states->clear($ctx->userId);

            $ctx->reply(Texts::ACCOUNT_DISABLED, ['reply_markup' => Keyboards::registration()]);
            return;
        }

        UserService::touchLogin((int) $user['id']);

        $savedPhone = (string) $user['phone_number'];

        $this->states->set($ctx->userId, States::MAIN_MENU, ['phone_number' => $savedPhone]);

        $ctx->reply(
            "<b>✅ ورود با موفقیت انجام شد.</b>\n\nلطفاً خدمت موردنظر خود را انتخاب کنید.",
            ['reply_markup' => Keyboards::mainMenu($savedPhone)]
        );
    }

    private function forgotPhone(Context $ctx): void
    {
        if ($ctx->contact === null) {
            $ctx->reply(
                "⚠️ لطفاً شماره موبایل خود را فقط با دکمه «" . Texts::BTN_SHARE_PHONE . "» ارسال کنید.",
                ['reply_markup' => Keyboards::phone()]
            );
            return;
        }

        if (!self::contactBelongsToSender($ctx)) {
            $ctx->reply(
                "⛔ این شماره متعلق به حساب تلگرام شما نیست.\n\n"
                . 'برای امنیت، بازیابی رمز فقط با شماره موبایل همین حساب تلگرام امکان‌پذیر است.',
                ['reply_markup' => Keyboards::phone()]
            );
            return;
        }

        $phone = Phone::normalize((string) ($ctx->contact['phone_number'] ?? ''));
        $user = UserService::findByPhone($phone);

        if ($user === null) {
            $this->states->clear($ctx->userId);
            $ctx->reply(
                "❌ حسابی با این شماره موبایل پیدا نشد.\n\nلطفاً ابتدا ثبت‌نام کنید.",
                ['reply_markup' => Keyboards::registration()]
            );
            return;
        }

        if ($user['status'] !== UserService::STATUS_ACTIVE) {
            $this->states->clear($ctx->userId);
            $ctx->reply(Texts::ACCOUNT_DISABLED, ['reply_markup' => Keyboards::registration()]);
            return;
        }

        $this->states->set(
            $ctx->userId,
            States::FORGOT_PASSWORD,
            ['phone_number' => (string) $user['phone_number'], 'user_id' => (int) $user['id']]
        );

        $ctx->reply('🔐 لطفاً رمز عبور جدید خود را وارد کنید:');
    }

    /** @param array<string,mixed> $data */
    private function forgotPassword(Context $ctx, array $data): void
    {
        $password = trim($ctx->text ?? '');
        $ctx->deleteIncoming();

        if ($password === '') {
            $ctx->reply('⚠️ لطفاً رمز عبور جدید را وارد کنید.');
            return;
        }

        $phone = (string) ($data['phone_number'] ?? '');
        $userId = (int) ($data['user_id'] ?? 0);

        if ($phone === '' || $userId === 0) {
            $this->states->clear($ctx->userId);
            $ctx->reply(
                "⚠️ اطلاعات بازیابی پیدا نشد.\n\nلطفاً دوباره تلاش کنید.",
                ['reply_markup' => Keyboards::registration()]
            );
            return;
        }

        $passwordError = Validation::validatePassword($password, $phone);
        if ($passwordError !== null) {
            $ctx->reply($passwordError);
            return;
        }

        UserService::updatePassword($userId, $password);

        $this->states->clear($ctx->userId);

        $ctx->reply(
            "<b>✅ رمز عبور شما با موفقیت تغییر کرد.</b>\n\n"
            . 'اکنون می‌توانید با رمز جدید وارد حساب خود شوید.',
            ['reply_markup' => Keyboards::registration()]
        );
    }
}
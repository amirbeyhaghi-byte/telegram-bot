<?php
declare(strict_types=1);

namespace App\Bot;

use App\Services\UserService;
use App\State\StateStore;
use App\Telegram\ApiInterface;

final class Bot
{
    private StateStore $states;
    private AuthHandler $auth;
    private MenuHandler $menu;
    private FeatureHandler $features;

    public function __construct(private ApiInterface $api, ?StateStore $states = null)
    {
        $this->states = $states ?? new StateStore();
        $this->auth = new AuthHandler($this->states);
        $this->menu = new MenuHandler($this->states);
        $this->features = new FeatureHandler($this->states);
    }

    /** @param array<string,mixed> $update */
    public function handle(array $update): void
    {
        $ctx = Context::fromUpdate($this->api, $update);

        if ($ctx === null) {
            return;
        }

        $session = $this->states->get($ctx->userId);
        if ($ctx->isCallback()) {
            if (!$this->features->handleCallback($ctx, (string)($session['state'] ?? ''), $session['data'] ?? [])) {
                $ctx->answerCallback();
            }
            return;
        }

        $state = $session['state'];
        $data = $session['data'];

        $text = $ctx->text !== null ? trim($ctx->text) : null;

        // /start
        if ($text === '/start' || ($text !== null && str_starts_with($text, '/start '))) {
            $this->states->clear($ctx->userId);
            $ctx->reply(Texts::START, ['reply_markup' => Keyboards::registration()]);
            return;
        }

        // درباره سامانه
        if ($text === Texts::BTN_ABOUT) {
            $ctx->reply(Texts::ABOUT);
            return;
        }

        // ارتباط با ما (در هر وضعیتی کار می‌کند)
        if ($text === Texts::BTN_CONTACT) {
            $ctx->reply(Texts::CONTACT);
            return;
        }

        // حساب غیرفعال‌شده از همه بخش‌ها بیرون انداخته می‌شود
        if ($state !== null && str_starts_with($state, States::MAIN_PREFIX)) {
            $phone = (string) ($data['phone_number'] ?? '');

            $status = $phone !== ''
                ? UserService::accountStatus($phone)
                : UserService::STATUS_MISSING;

            if ($status !== UserService::STATUS_ACTIVE) {
                $this->states->clear($ctx->userId);

                $ctx->reply(
                    $status === UserService::STATUS_DISABLED ? Texts::ACCOUNT_DISABLED : Texts::ACCOUNT_MISSING,
                    ['reply_markup' => Keyboards::registration()]
                );
                return;
            }
        }

        // دکمه‌های شروع ثبت‌نام / ورود / فراموشی رمز در هر وضعیتی کار می‌کنند
        if ($text === Texts::BTN_REGISTER) {
            $this->auth->startRegistration($ctx);
            return;
        }

        if ($text === Texts::BTN_LOGIN) {
            $this->auth->startLogin($ctx);
            return;
        }

        if ($text === Texts::BTN_FORGOT_PASSWORD) {
            $this->auth->startForgotPassword($ctx);
            return;
        }

        if ($state !== null) {
            if (str_starts_with($state, 'reg:') || str_starts_with($state, 'login:') || str_starts_with($state, 'forgot:')) {
                $this->auth->handle($ctx, $state, $data);
                return;
            }

            if (str_starts_with($state, 'feature:')) {
                if ($this->features->handleMessage($ctx, $state, $data)) return;
            }

            if ($state === States::MAIN_MENU) {
                if ($this->features->handleMenu($ctx, $text, $data)) return;
                $this->menu->handle($ctx, $text, $data);
                return;
            }
        }

        $ctx->reply(Texts::NO_STATE_HINT, ['reply_markup' => Keyboards::registration()]);
    }
}
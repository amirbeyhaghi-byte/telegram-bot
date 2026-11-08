<?php
declare(strict_types=1);

/**
 * خودآزمایی پروژه — بدون نیاز به تلگرام.
 *   php bin/selftest.php          آزمون توابع (بدون دیتابیس)
 *   php bin/selftest.php --db     + آزمون کامل ثبت‌نام/ورود روی دیتابیس (ابتدا php bin/migrate.php)
 *
 * آزمون --db فقط ردیف‌های تستی (شماره 0999000...) را می‌سازد و در پایان پاک می‌کند.
 */

require __DIR__ . '/../src/autoload.php';

define('APP_ROOT', dirname(__DIR__));
mb_internal_encoding('UTF-8');
date_default_timezone_set('UTC');

use App\Bot\Bot;
use App\Bot\Context;
use App\Bot\Keyboards;
use App\Bot\States;
use App\Bot\Texts;
use App\Db;
use App\Env;
use App\Services\PasswordHasher;
use App\Services\Phone;
use App\Services\Validation;
use App\State\StateStore;
use App\Support\Persian;
use App\Testing\FakeApi;

if (is_file(APP_ROOT . '/.env')) {
    Env::load(APP_ROOT . '/.env');
}

$passed = 0;
$failed = 0;

function check(string $name, bool $condition, string $detail = ''): void
{
    global $passed, $failed;

    if ($condition) {
        $passed++;
        echo "  ✅ {$name}\n";
    } else {
        $failed++;
        echo "  ❌ {$name}" . ($detail !== '' ? " — {$detail}" : '') . "\n";
    }
}

function section(string $title): void
{
    echo "\n== {$title} ==\n";
}

/** @param list<array<string,mixed>> $rows @return list<string> */
function keyboardTexts(array $markup): array
{
    $texts = [];

    foreach ($markup['keyboard'] ?? [] as $row) {
        foreach ($row as $button) {
            $texts[] = (string) $button['text'];
        }
    }

    return $texts;
}

// =====================================================================
// الف) آزمون توابع
// =====================================================================

section('Env');
Env::parse("# comment\nA=1\nB=\"x y\"\nC='z'\n\nD = spaced value \nNOEQUALS\n");
check('خواندن مقدار ساده', Env::get('A') === '1');
check('حذف کوتیشن دوتایی', Env::get('B') === 'x y');
check('حذف کوتیشن تکی', Env::get('C') === 'z');
check('فاصله اطراف کلید و مقدار', Env::get('D') === 'spaced value');
check('مقدار پیش‌فرض', Env::get('MISSING', 'def') === 'def');
Env::parse("\xEF\xBB\xBFBOM_KEY=ok");
check('حذف BOM ابتدای فایل', Env::get('BOM_KEY') === 'ok');
Env::set('T_BOOL', 'yes');
Env::set('T_INT', '42');
check('Env::bool', Env::bool('T_BOOL') === true && Env::bool('NOPE', true) === true);
check('Env::int', Env::int('T_INT') === 42 && Env::int('NOPE', 7) === 7);

section('Persian');
check('ارقام فارسی', Persian::digits(1234) === '۱۲۳۴');
check('تبدیل به لاتین', Persian::toAscii('۰۹۱٢٣') === '09123');


section('Phone');
$phoneCases = [
    ['+989121234567', '09121234567'],
    ['989121234567', '09121234567'],
    ['00989121234567', '09121234567'],
    ['09121234567', '09121234567'],
    ['9121234567', '09121234567'],
    ['۰۹۱۲۱۲۳۴۵۶۷', '09121234567'],
    ['0912 123-4567', '09121234567'],
    [' +98 912 123 4567 ', '09121234567'],
];

foreach ($phoneCases as [$input, $expected]) {
    $actual = Phone::normalize($input);
    check("normalize({$input})", $actual === $expected, (string) $actual);
}

check('isValid ایران', Phone::isValid('09121234567') && !Phone::isValid('0912123456'));
check('isValid شماره با +', !Phone::isValid('+989121234567'));
check('isValid شماره خارجی', Phone::isValid('994501234567') && !Phone::isValid('12') && !Phone::isValid('09ab'));
Env::set('ADMIN_PHONE', '989121234567');
check('isAdmin', Phone::isAdmin('09121234567') && Phone::isAdmin('+989121234567')
    && !Phone::isAdmin('09120000000') && !Phone::isAdmin(null) && !Phone::isAdmin(''));

section('Validation: نام');
[$clean] = Validation::validateName('علي  رضا');
check('«ي» عربی و فاصله اضافه', $clean === 'علی رضا', (string) $clean);
foreach (['علی', 'Mary-Ann', "نیم\u{200C}فاصله"] as $good) {
    check("نام درست: {$good}", Validation::validateName($good)[1] === null);
}
foreach (['ali123', '<b>x', 'ا', '', '۱۲۳', 'علی؟', str_repeat('a', 41), '-علی', "علی\n<script>"] as $bad) {
    $result = Validation::validateName($bad);
    check('نام نامعتبر: ' . str_replace("\n", ' ', $bad), $result[0] === null && $result[1] !== null);
}

section('Validation: رمز عبور');
foreach (['123456', 'aaaaaa', 'abcdef', 'رمز۱۲۳', '!@#$%^', '111111', 'a b c d e f'] as $good) {
    check("رمز آزاد: {$good}", Validation::validatePassword($good, '09121234567') === null);
}
foreach (['12345', '', 'ab', 'رمز۱۲'] as $short) {
    $error = Validation::validatePassword($short, '09121234567');
    check("رمز کوتاه: {$short}", $error !== null && str_contains($error, 'حداقل ۶'));
}
foreach (['09121234567', '+989121234567', '989121234567', '9121234567', '۰۹۱۲۱۲۳۴۵۶۷', '0912-123-4567'] as $phonePw) {
    $error = Validation::validatePassword($phonePw, '09121234567');
    check("رمز برابر شماره: {$phonePw}", $error !== null && str_contains($error, 'شماره موبایل'));
}
check('رمزِ شامل شماره (ولی برابر آن نیست) مجاز است', Validation::validatePassword('a09121234567', '09121234567') === null);
check('سقف ۱۲۸ کاراکتر', Validation::validatePassword(str_repeat('x', 129)) !== null
    && Validation::validatePassword(str_repeat('x', 128)) === null);

section('PasswordHasher');
$hash = PasswordHasher::hash('Secret-123');
check('بررسی رمز درست', PasswordHasher::verify('Secret-123', $hash));
check('رد رمز اشتباه', !PasswordHasher::verify('secret-123', $hash));
check('هش تصادفی (salt)', $hash !== PasswordHasher::hash('Secret-123'));
echo '  ℹ️ الگوریتم: ' . (defined('PASSWORD_ARGON2ID') ? 'Argon2id' : 'bcrypt (Argon2 در این PHP نیست)') . "\n";

section('Keyboards');
$normal = keyboardTexts(Keyboards::mainMenu('09125550000'));
$admin = keyboardTexts(Keyboards::mainMenu('09121234567'));
check('دکمه مدیر برای کاربر عادی نیست', !in_array(Texts::BTN_ADMIN, $normal, true));
check('دکمه مدیر برای مدیر هست', in_array(Texts::BTN_ADMIN, $admin, true));
check('کیبورد ثبت‌نام ۳ دکمه دارد', count(keyboardTexts(Keyboards::registration())) === 3);
check('کیبورد شماره: request_contact', (Keyboards::phone()['keyboard'][0][0]['request_contact'] ?? false) === true);

section('Context::fromUpdate');
$api = new FakeApi();
$private = ['message' => ['message_id' => 5, 'from' => ['id' => 11, 'is_bot' => false],
    'chat' => ['id' => 11, 'type' => 'private'], 'text' => 'سلام']];
$ctx = Context::fromUpdate($api, $private);
check('پیام خصوصی', $ctx !== null && $ctx->userId === 11 && $ctx->text === 'سلام' && $ctx->messageId === 5);
$group = $private;
$group['message']['chat']['type'] = 'group';
check('گروه نادیده گرفته می‌شود', Context::fromUpdate($api, $group) === null);
$bot = $private;
$bot['message']['from']['is_bot'] = true;
check('فرستنده ربات نادیده گرفته می‌شود', Context::fromUpdate($api, $bot) === null);
$withContact = $private;
$withContact['message']['contact'] = ['phone_number' => '+98912', 'user_id' => 11];
$ctx = Context::fromUpdate($api, $withContact);
check('شماره تماس خوانده می‌شود', $ctx !== null && ($ctx->contact['user_id'] ?? 0) === 11);
$callback = ['callback_query' => ['id' => 'cb1', 'data' => 'x:y', 'from' => ['id' => 11, 'is_bot' => false],
    'message' => ['message_id' => 9, 'chat' => ['id' => 11, 'type' => 'private']]]];
$ctx = Context::fromUpdate($api, $callback);
check('دکمه inline', $ctx !== null && $ctx->isCallback() && $ctx->callbackData === 'x:y' && $ctx->messageId === 9);
check('Update ناشناخته', Context::fromUpdate($api, ['edited_message' => []]) === null);

// =====================================================================
// ب) آزمون کامل ثبت‌نام و ورود روی دیتابیس
// =====================================================================

if (in_array('--db', $argv, true)) {
    section('آزمون کامل روی دیتابیس (ثبت‌نام ← خروج ← ورود ← غیرفعال‌سازی)');

    $uid = 900000001;
    $stranger = 900000002;
    $phone = '09990000001';

    $cleanup = static function () use ($phone, $uid): void {
        $user = Db::fetchOne('SELECT id FROM users WHERE phone_number = ?', [$phone]);
        if ($user !== null) {
            Db::execute('DELETE FROM payments WHERE user_id = ?', [(int)$user['id']]);
            Db::execute('DELETE FROM subscription_codes WHERE used_by_user_id = ?', [(int)$user['id']]);
            Db::execute('DELETE FROM subscriptions WHERE user_id = ?', [(int)$user['id']]);
        }
        Db::execute('DELETE FROM users WHERE phone_number = ?', [$phone]);
        Db::execute('DELETE FROM user_states WHERE telegram_id = ?', [$uid]);
    };

    try {
        $cleanup();
    } catch (Throwable $e) {
        check('اتصال به دیتابیس و وجود جدول‌ها', false, $e->getMessage() . ' — ابتدا php bin/migrate.php را اجرا کنید');
        echo "\nنتیجه: {$passed} موفق، {$failed} ناموفق\n";
        exit(1);
    }

    Env::set('ADMIN_PHONE', '09120000000');   // کاربر تستی مدیر نیست

    $api = new FakeApi();
    $bot = new Bot($api);
    $states = new StateStore();
    $n = 0;

    $send = static function (array $message) use ($bot, &$n, $uid): void {
        $n++;
        $message = array_merge(
            ['message_id' => $n, 'from' => ['id' => $uid, 'is_bot' => false], 'chat' => ['id' => $uid, 'type' => 'private']],
            $message
        );
        $bot->handle(['update_id' => $n, 'message' => $message]);
    };

    $text = static fn (string $value) => $send(['text' => $value]);
    $contact = static fn (string $number, int $owner) => $send(
        ['contact' => ['phone_number' => $number, 'user_id' => $owner]]
    );
    $state = static fn (): ?string => $states->get($uid)['state'];
    $said = static fn (string $needle): bool => str_contains($api->lastText(), $needle);

    $text('/start');
    check('/start: خوش‌آمدگویی', $said('خوش آمدید') && $state() === null);

    $text(Texts::BTN_REGISTER);
    check('شروع ثبت‌نام: پرسیدن نام', $said('نام خود را وارد کنید') && $state() === States::REG_FIRST_NAME);

    $text('ali123');
    check('نام با عدد رد می‌شود', $said('فقط از حروف') && $state() === States::REG_FIRST_NAME);

    $text('علی');
    check('نام پذیرفته شد → نام خانوادگی', $said('نام خانوادگی') && $state() === States::REG_LAST_NAME);

    $text('رضایی');
    check('نام خانوادگی پذیرفته شد → درخواست شماره',
        $said('شماره موبایل') && $state() === States::REG_PHONE
        && (Keyboards::phone() === $api->lastExtra()['reply_markup']));

    $text($phone);
    check('شماره تایپی پذیرفته نمی‌شود', $said('فقط با دکمه') && $state() === States::REG_PHONE);

    $contact('+98' . substr($phone, 1), $stranger);
    check('شماره متعلق به دیگری رد می‌شود',
        $said('متعلق به حساب تلگرام شما نیست') && Db::fetchOne('SELECT id FROM users WHERE phone_number = ?', [$phone]) === null);

    $contact('+98' . substr($phone, 1), $uid);
    check('شماره خودِ کاربر پذیرفته شد → رمز', $said('رمز عبور') && $state() === States::REG_PASSWORD);

    $before = count($api->deleted);
    $text('12345');
    check('رمز کوتاه رد می‌شود و پیام رمز پاک می‌شود', $said('حداقل') && count($api->deleted) === $before + 1);

    $text($phone);
    check('رمز برابر شماره رد می‌شود', $said('شماره موبایل'));

    $text('abc123');
    $row = Db::fetchOne('SELECT * FROM users WHERE phone_number = ?', [$phone]);
    check('ثبت‌نام موفق', $said('با موفقیت انجام شد') && $state() === States::MAIN_MENU && $row !== null);
    check('نام در دیتابیس', $row !== null && $row['first_name'] === 'علی' && $row['last_name'] === 'رضایی');
    check('رمز هش‌شده ذخیره شد', $row !== null && $row['password_hash'] !== 'abc123' && PasswordHasher::verify('abc123', (string) $row['password_hash']));
    check('کاربر عادی دکمه مدیر ندارد', !in_array(Texts::BTN_ADMIN, keyboardTexts($api->lastExtra()['reply_markup'] ?? []), true));
    $freeSub = $row !== null ? Db::fetchOne("SELECT * FROM subscriptions WHERE user_id = ? AND type = 'free' ORDER BY id DESC LIMIT 1", [(int)$row['id']]) : null;
    check('اشتراک رایگان پس از ثبت‌نام ساخته شد', $freeSub !== null && strtotime((string)$freeSub['end_date']) > strtotime((string)$freeSub['start_date']));

    $text(Texts::BTN_TEMPERAMENT);
    check('ورود به آزمون مزاج‌شناسی', $said('پرسش') && str_contains($api->lastText(), 'مزاج‌شناسی'));

    $text(Texts::BTN_LOGOUT);
    check('خروج از حساب', $said('خارج شدید') && $state() === null);

    $text(Texts::BTN_LOGIN);
    check('شروع ورود', $state() === States::LOGIN_PHONE);

    $contact($phone, $stranger);
    check('ورود با شماره دیگری رد می‌شود', $said('متعلق به حساب تلگرام شما نیست') && $state() === States::LOGIN_PHONE);

    $contact('+98' . substr($phone, 1), $uid);
    check('شماره درست → رمز', $state() === States::LOGIN_PASSWORD);

    $text('bad-pass');
    check('رمز اشتباه', $said('رمز عبور اشتباه است') && $state() === States::LOGIN_PASSWORD);

    $text('abc123');
    $row = Db::fetchOne('SELECT last_login_at FROM users WHERE phone_number = ?', [$phone]);
    check('ورود موفق', $said('ورود با موفقیت') && $state() === States::MAIN_MENU && ($row['last_login_at'] ?? null) !== null);

    Db::execute("UPDATE users SET status = 'disabled' WHERE phone_number = ?", [$phone]);
    $text(Texts::BTN_TEMPERAMENT);
    check('حساب غیرفعال‌شده فوراً بیرون انداخته می‌شود', $said('غیرفعال شده') && $state() === null);

    $text(Texts::BTN_LOGIN);
    $contact('+98' . substr($phone, 1), $uid);
    $text('abc123');
    check('ورود حساب غیرفعال ممکن نیست', $said('غیرفعال شده') && $state() === null);

    Db::execute("UPDATE users SET status = 'active' WHERE phone_number = ?", [$phone]);
    $text(Texts::BTN_REGISTER);
    $text('علی');
    $text('رضایی');
    $contact('+98' . substr($phone, 1), $uid);
    check('ثبت‌نام دوباره با شماره موجود', $said('قبلاً در سامانه ثبت شده') && $state() === null);

    $cleanup();
    check('پاک‌سازی داده‌های تستی', Db::fetchOne('SELECT id FROM users WHERE phone_number = ?', [$phone]) === null);
}

echo "\nنتیجه: {$passed} موفق، {$failed} ناموفق\n";
exit($failed > 0 ? 1 : 0);

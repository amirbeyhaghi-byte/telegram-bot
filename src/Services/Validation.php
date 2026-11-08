<?php
declare(strict_types=1);

namespace App\Services;

use App\Support\Persian;

final class Validation
{
    public const NAME_MIN = 2;
    public const NAME_MAX = 40;
    public const PASSWORD_MIN = 6;
    public const PASSWORD_MAX = 128;

    /** حروف فارسی/عربی (بدون ارقام و علائم نگارشی) + حروف لاتین */
    private const LETTERS = 'A-Za-z\x{0621}-\x{063A}\x{0641}-\x{064A}\x{067E}\x{0686}\x{0698}\x{06AF}\x{06A9}\x{06CC}\x{06C0}';

    /**
     * @return array{0:?string,1:?string}  [نام تمیزشده، پیام خطا]
     */
    public static function validateName(?string $text): array
    {
        $name = strtr($text ?? '', ['ي' => 'ی', 'ى' => 'ی', 'ك' => 'ک']);
        $name = trim((string) preg_replace('/\s+/u', ' ', $name));

        $length = mb_strlen($name);

        if ($length < self::NAME_MIN || $length > self::NAME_MAX) {
            return [null, '⚠️ طول نام باید بین ' . Persian::digits(self::NAME_MIN)
                . ' تا ' . Persian::digits(self::NAME_MAX) . ' حرف باشد.'];
        }

        $pattern = '/^[' . self::LETTERS . '][' . self::LETTERS . '\x{200C} \'\-]*$/u';

        if (preg_match($pattern, $name) !== 1) {
            return [null, '⚠️ فقط از حروف فارسی یا انگلیسی استفاده کنید (بدون عدد و علامت).'];
        }

        return [$name, null];
    }

    /** پیام خطا یا null اگر رمز مناسب است (فقط: حداقل ۶ کاراکتر و برابر شماره موبایل نبودن) */
    public static function validatePassword(?string $password, ?string $phone = null): ?string
    {
        $password = $password ?? '';
        $length = mb_strlen($password);

        if ($length < self::PASSWORD_MIN) {
            return '⚠️ رمز عبور باید حداقل ' . Persian::digits(self::PASSWORD_MIN) . ' کاراکتر باشد.';
        }

        if ($length > self::PASSWORD_MAX) {
            return '⚠️ رمز عبور نباید بیشتر از ' . Persian::digits(self::PASSWORD_MAX) . ' کاراکتر باشد.';
        }

        if ($phone !== null && $phone !== '' && self::looksLikePhone($password, $phone)) {
            return '⚠️ رمز عبور نباید همان شماره موبایل شما باشد.';
        }

        return null;
    }

    /** رمزی که فقط ارقام (و + - فاصله) است و پس از نرمال‌سازی همان شماره است */
    private static function looksLikePhone(string $password, string $phone): bool
    {
        $ascii = Persian::toAscii($password);

        if (preg_match('/^[0-9+\- ]+$/', $ascii) !== 1) {
            return false;
        }

        return Phone::normalize($password) === Phone::normalize($phone);
    }
}

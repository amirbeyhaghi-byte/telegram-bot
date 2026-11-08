<?php
declare(strict_types=1);

namespace App\Telegram;

/** سازنده ساختار دکمه‌های تلگرام (آرایه‌هایی که به JSON تبدیل می‌شوند) */
final class Keyboard
{
    /** @param list<list<array<string,mixed>>> $rows */
    public static function reply(array $rows, bool $oneTime = false): array
    {
        return [
            'keyboard' => $rows,
            'resize_keyboard' => true,
            'one_time_keyboard' => $oneTime,
        ];
    }

    public static function text(string $text): array
    {
        return ['text' => $text];
    }

    public static function contact(string $text): array
    {
        return ['text' => $text, 'request_contact' => true];
    }

    /** @param list<list<array<string,mixed>>> $rows */
    public static function inline(array $rows): array
    {
        return ['inline_keyboard' => $rows];
    }

    public static function button(string $text, string $callbackData): array
    {
        return ['text' => $text, 'callback_data' => $callbackData];
    }

    /** دکمه کپی متن؛ پشتیبانی از CopyTextButton در Bot API */
    public static function copyTextButton(string $text, string $copyText): array
    {
        return ['text' => $text, 'copy_text' => ['text' => $copyText]];
    }

    public static function remove(): array
    {
        return ['remove_keyboard' => true];
    }
}

<?php
declare(strict_types=1);

namespace App\Telegram;

/** فقط متدهایی که منطق ربات لازم دارد؛ برای تست بدون تلگرام (FakeApi) */
interface ApiInterface
{
    /** @return array<string,mixed> */
    public function sendMessage(int|string $chatId, string $text, array $extra = []): array;

    /** @return array<string,mixed>|null */
    public function editMessageText(int|string $chatId, int $messageId, string $text, array $extra = []): ?array;

    public function answerCallbackQuery(string $callbackId, ?string $text = null, bool $alert = false): void;

    public function deleteMessage(int|string $chatId, int $messageId): void;

    /** @return array<string,mixed> */
    public function sendPhoto(int|string $chatId, string $photo, string $caption = '', array $extra = []): array;

    /** @return array<string,mixed> */
    public function sendDocument(int|string $chatId, string $document, string $caption = '', array $extra = []): array;
}

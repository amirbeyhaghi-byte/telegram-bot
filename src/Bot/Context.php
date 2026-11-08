<?php
declare(strict_types=1);

namespace App\Bot;

use App\Telegram\ApiInterface;

/** اطلاعات یک پیام یا دکمه ورودی + میانبر پاسخ‌دادن */
final class Context
{
    private function __construct(
        public readonly ApiInterface $api,
        public readonly int $chatId,
        public readonly int $userId,
        public readonly ?string $text,
        public readonly ?array $contact,
        public readonly ?string $callbackId,
        public readonly ?string $callbackData,
        public readonly ?int $messageId,
        public readonly ?string $photoFileId = null,
        public readonly ?string $documentFileId = null,
        public readonly ?string $documentMimeType = null
    ) {
    }

    /**
     * فقط گفتگوی خصوصی با کاربر واقعی پردازش می‌شود؛ بقیه null.
     * @param array<string,mixed> $update
     */
    public static function fromUpdate(ApiInterface $api, array $update): ?self
    {
        if (isset($update['callback_query']) && is_array($update['callback_query'])) {
            $callback = $update['callback_query'];
            $message = $callback['message'] ?? null;
            $from = $callback['from'] ?? null;

            if (!is_array($message) || !is_array($from) || !self::isPrivateHuman($message, $from)) {
                return null;
            }

            return new self(
                $api,
                (int) $message['chat']['id'],
                (int) $from['id'],
                null,
                null,
                isset($callback['id']) ? (string) $callback['id'] : null,
                isset($callback['data']) ? (string) $callback['data'] : null,
                isset($message['message_id']) ? (int) $message['message_id'] : null
            );
        }

        if (isset($update['message']) && is_array($update['message'])) {
            $message = $update['message'];
            $from = $message['from'] ?? null;

            if (!is_array($from) || !self::isPrivateHuman($message, $from)) {
                return null;
            }

            return new self(
                $api,
                (int) $message['chat']['id'],
                (int) $from['id'],
                isset($message['text']) ? (string) $message['text'] : null,
                (isset($message['contact']) && is_array($message['contact'])) ? $message['contact'] : null,
                null,
                null,
                isset($message['message_id']) ? (int) $message['message_id'] : null,
                isset($message['photo']) && is_array($message['photo']) && $message['photo'] !== []
                    ? (string) ($message['photo'][array_key_last($message['photo'])]['file_id'] ?? '')
                    : null,
                isset($message['document']['file_id']) ? (string) $message['document']['file_id'] : null,
                isset($message['document']['mime_type']) ? (string) $message['document']['mime_type'] : null
            );
        }

        return null;
    }

    /** @param array<string,mixed> $message @param array<string,mixed> $from */
    private static function isPrivateHuman(array $message, array $from): bool
    {
        return (($message['chat']['type'] ?? '') === 'private')
            && isset($message['chat']['id'], $from['id'])
            && empty($from['is_bot']);
    }

    public function isCallback(): bool
    {
        return $this->callbackId !== null;
    }

    public function reply(string $text, array $extra = []): void
    {
        $this->api->sendMessage($this->chatId, $text, $extra);
    }

    public function edit(string $text, array $extra = []): void
    {
        if ($this->messageId !== null) {
            $this->api->editMessageText($this->chatId, $this->messageId, $text, $extra);
        }
    }

    public function answerCallback(?string $text = null, bool $alert = false): void
    {
        if ($this->callbackId !== null) {
            $this->api->answerCallbackQuery($this->callbackId, $text, $alert);
        }
    }

    /** پیام ورودی کاربر را پاک می‌کند (مثلاً پیام حاوی رمز عبور)؛ خطا نادیده گرفته می‌شود */
    public function deleteIncoming(): void
    {
        if ($this->messageId === null || $this->isCallback()) {
            return;
        }

        try {
            $this->api->deleteMessage($this->chatId, $this->messageId);
        } catch (\Throwable) {
            // اهمیتی ندارد
        }
    }
}

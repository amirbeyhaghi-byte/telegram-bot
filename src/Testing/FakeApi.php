<?php
declare(strict_types=1);

namespace App\Testing;

use App\Telegram\ApiInterface;

/** جایگزین Api برای تست بدون تلگرام: فقط ثبت می‌کند چه چیزی ارسال شده */
final class FakeApi implements ApiInterface
{
    /** @var list<array<string,mixed>> */
    public array $messages = [];

    /** @var list<int> */
    public array $deleted = [];

    /** @var list<array<string,mixed>> */
    public array $edits = [];

    public function sendMessage(int|string $chatId, string $text, array $extra = []): array
    {
        $this->messages[] = ['chat' => $chatId, 'text' => $text, 'extra' => $extra];

        return ['message_id' => count($this->messages)];
    }

    public function editMessageText(int|string $chatId, int $messageId, string $text, array $extra = []): ?array
    {
        $this->edits[] = ['chat' => $chatId, 'message_id' => $messageId, 'text' => $text, 'extra' => $extra];

        return null;
    }

    public function answerCallbackQuery(string $callbackId, ?string $text = null, bool $alert = false): void
    {
    }

    public function deleteMessage(int|string $chatId, int $messageId): void
    {
        $this->deleted[] = $messageId;
    }

    public function sendPhoto(int|string $chatId, string $photo, string $caption = '', array $extra = []): array
    {
        $this->messages[] = ['chat' => $chatId, 'text' => $caption, 'photo' => $photo, 'extra' => $extra];
        return ['message_id' => count($this->messages)];
    }

    public function sendDocument(int|string $chatId, string $document, string $caption = '', array $extra = []): array
    {
        $this->messages[] = ['chat' => $chatId, 'text' => $caption, 'document' => $document, 'extra' => $extra];
        return ['message_id' => count($this->messages)];
    }

    public function lastText(): string
    {
        $last = end($this->messages);

        return $last === false ? '' : (string) $last['text'];
    }

    /** @return array<string,mixed> */
    public function lastExtra(): array
    {
        $last = end($this->messages);

        return $last === false ? [] : (array) $last['extra'];
    }

    public function reset(): void
    {
        $this->messages = [];
        $this->deleted = [];
        $this->edits = [];
    }
}

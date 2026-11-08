<?php
declare(strict_types=1);

namespace App\Telegram;

use App\Env;

/** کلاینت ساده Bot API با cURL (پشتیبانی از پروکسی و IPv4 برای شبکه‌های فیلترشده) */
final class Api implements ApiInterface
{
    public function __construct(
        private string $token,
        private ?string $proxy = null,
        private bool $ipv4 = true,
        private bool $verifySsl = true,
        private ?string $caBundle = null
    ) {
    }

    public static function fromEnv(): self
    {
        $token = trim((string) Env::get('BOT_TOKEN', ''));

        if ($token === '') {
            throw new \RuntimeException('BOT_TOKEN در فایل .env تنظیم نشده است.');
        }

        $proxy = trim((string) Env::get('TELEGRAM_PROXY', ''));
        $ca = trim((string) Env::get('TELEGRAM_CA_BUNDLE', ''));

        return new self(
            $token,
            $proxy !== '' ? $proxy : null,
            Env::bool('TELEGRAM_IPV4', true),
            Env::bool('TELEGRAM_VERIFY_SSL', true),
            $ca !== '' ? $ca : null
        );
    }

    /**
     * @return mixed مقدار result پاسخ تلگرام
     * @throws TelegramNetworkException
     * @throws TelegramApiException
     */
    public function call(string $method, array $params = [], int $timeout = 30): mixed
    {
        $ch = curl_init('https://api.telegram.org/bot' . $this->token . '/' . $method);

        $options = [
            CURLOPT_POST => true,
            CURLOPT_POSTFIELDS => json_encode($params, JSON_UNESCAPED_UNICODE),
            CURLOPT_HTTPHEADER => ['Content-Type: application/json'],
            CURLOPT_RETURNTRANSFER => true,
            CURLOPT_CONNECTTIMEOUT => 10,
            CURLOPT_TIMEOUT => $timeout,
        ];

        if ($this->proxy !== null) {
            $options[CURLOPT_PROXY] = $this->proxy;
        }

        if ($this->ipv4) {
            $options[CURLOPT_IPRESOLVE] = CURL_IPRESOLVE_V4;
        }

        if (!$this->verifySsl) {
            $options[CURLOPT_SSL_VERIFYPEER] = false;
            $options[CURLOPT_SSL_VERIFYHOST] = 0;
        } elseif ($this->caBundle !== null) {
            $options[CURLOPT_CAINFO] = $this->caBundle;
        }

        curl_setopt_array($ch, $options);

        $body = curl_exec($ch);
        $errno = curl_errno($ch);
        $error = curl_error($ch);

        if ($body === false) {
            throw new TelegramNetworkException("خطای شبکه ({$errno}): {$error}");
        }

        $data = json_decode((string) $body, true);

        if (!is_array($data)) {
            throw new TelegramNetworkException('پاسخ نامعتبر از تلگرام دریافت شد.');
        }

        if (empty($data['ok'])) {
            throw new TelegramApiException(
                (string) ($data['description'] ?? 'unknown error'),
                (int) ($data['error_code'] ?? 0)
            );
        }

        return $data['result'] ?? null;
    }

    public function sendMessage(int|string $chatId, string $text, array $extra = []): array
    {
        $params = array_merge(
            ['chat_id' => $chatId, 'text' => $text, 'parse_mode' => 'HTML'],
            $extra
        );

        $result = $this->call('sendMessage', $params);

        return is_array($result) ? $result : [];
    }

    public function editMessageText(int|string $chatId, int $messageId, string $text, array $extra = []): ?array
    {
        $params = array_merge(
            ['chat_id' => $chatId, 'message_id' => $messageId, 'text' => $text, 'parse_mode' => 'HTML'],
            $extra
        );

        try {
            $result = $this->call('editMessageText', $params);
        } catch (TelegramApiException $e) {
            // اگر متن و دکمه‌ها تغییری نکرده باشند، خطا نیست
            if (str_contains($e->getMessage(), 'message is not modified')) {
                return null;
            }

            throw $e;
        }

        return is_array($result) ? $result : null;
    }

    public function answerCallbackQuery(string $callbackId, ?string $text = null, bool $alert = false): void
    {
        $params = ['callback_query_id' => $callbackId];

        if ($text !== null) {
            $params['text'] = $text;
            $params['show_alert'] = $alert;
        }

        $this->call('answerCallbackQuery', $params);
    }

    public function deleteMessage(int|string $chatId, int $messageId): void
    {
        $this->call('deleteMessage', ['chat_id' => $chatId, 'message_id' => $messageId]);
    }


    public function sendPhoto(int|string $chatId, string $photo, string $caption = '', array $extra = []): array
    {
        $params = array_merge([
            'chat_id' => $chatId,
            'photo' => $photo,
            'caption' => $caption,
            'parse_mode' => 'HTML',
        ], $extra);
        $result = $this->call('sendPhoto', $params);
        return is_array($result) ? $result : [];
    }

    public function sendDocument(int|string $chatId, string $document, string $caption = '', array $extra = []): array
    {
        $params = array_merge([
            'chat_id' => $chatId,
            'document' => $document,
            'caption' => $caption,
            'parse_mode' => 'HTML',
        ], $extra);
        $result = $this->call('sendDocument', $params);
        return is_array($result) ? $result : [];
    }

    /** @return list<array<string,mixed>> */
    public function getUpdates(int $offset, int $timeout = 25): array
    {
        $result = $this->call(
            'getUpdates',
            [
                'offset' => $offset,
                'timeout' => $timeout,
                'allowed_updates' => ['message', 'callback_query'],
            ],
            $timeout + 15
        );

        return is_array($result) ? $result : [];
    }

    /** @return array<string,mixed> */
    public function getMe(): array
    {
        $result = $this->call('getMe');

        return is_array($result) ? $result : [];
    }

    public function setWebhook(string $url, string $secretToken = ''): void
    {
        $params = [
            'url' => $url,
            'allowed_updates' => ['message', 'callback_query'],
            'drop_pending_updates' => false,
        ];

        if ($secretToken !== '') {
            $params['secret_token'] = $secretToken;
        }

        $this->call('setWebhook', $params);
    }

    public function deleteWebhook(bool $dropPending = false): void
    {
        $this->call('deleteWebhook', ['drop_pending_updates' => $dropPending]);
    }
}

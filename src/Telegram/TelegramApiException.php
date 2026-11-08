<?php
declare(strict_types=1);

namespace App\Telegram;

/** تلگرام درخواست را رد کرد (توکن اشتباه، پیام نامعتبر، ...) */
class TelegramApiException extends TelegramException
{
    public function __construct(string $message, private int $errorCode = 0)
    {
        parent::__construct($message, $errorCode);
    }

    public function errorCode(): int
    {
        return $this->errorCode;
    }
}

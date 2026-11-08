<?php
declare(strict_types=1);

namespace App\Telegram;

/** خطای شبکه (قطع اینترنت، نیاز به فیلترشکن، timeout، مشکل SSL) */
class TelegramNetworkException extends TelegramException
{
}

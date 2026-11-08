<?php
declare(strict_types=1);

namespace App\State;

use App\Db;
use App\Support\Clock;

/** ذخیره وضعیت گفتگوی هر کاربر در دیتابیس (معادل FSM نسخه پایتون) */
class StateStore
{
    /** @return array{state:?string,data:array<string,mixed>} */
    public function get(int $userId): array
    {
        $row = Db::fetchOne('SELECT state, data FROM user_states WHERE telegram_id = ?', [$userId]);

        if ($row === null) {
            return ['state' => null, 'data' => []];
        }

        $data = json_decode((string) ($row['data'] ?? ''), true);

        return [
            'state' => ($row['state'] === null || $row['state'] === '') ? null : (string) $row['state'],
            'data' => is_array($data) ? $data : [],
        ];
    }

    /** وضعیت و داده را کامل جایگزین می‌کند */
    public function set(int $userId, ?string $state, array $data = []): void
    {
        Db::execute(
            'INSERT INTO user_states (telegram_id, state, data, updated_at) VALUES (?, ?, ?, ?)
             ON DUPLICATE KEY UPDATE state = VALUES(state), data = VALUES(data), updated_at = VALUES(updated_at)',
            [$userId, $state, json_encode($data, JSON_UNESCAPED_UNICODE), Clock::now()]
        );
    }

    /** فقط وضعیت را عوض می‌کند و داده‌های قبلی می‌مانند */
    public function setState(int $userId, ?string $state): void
    {
        $current = $this->get($userId);

        $this->set($userId, $state, $current['data']);
    }

    /** چند کلید را به داده‌های فعلی اضافه یا جایگزین می‌کند */
    public function mergeData(int $userId, array $values): void
    {
        $current = $this->get($userId);

        $this->set($userId, $current['state'], array_merge($current['data'], $values));
    }

    public function clear(int $userId): void
    {
        Db::execute('DELETE FROM user_states WHERE telegram_id = ?', [$userId]);
    }
}

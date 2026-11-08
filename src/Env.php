<?php
declare(strict_types=1);

namespace App;

/** خواندن تنظیمات از فایل .env (فرمت KEY=VALUE) */
final class Env
{
    /** @var array<string,string> */
    private static array $values = [];

    public static function load(string $path): void
    {
        if (!is_file($path)) {
            throw new \RuntimeException("فایل .env پیدا نشد: {$path}");
        }

        self::parse((string) file_get_contents($path));
    }

    public static function parse(string $content): void
    {
        $content = preg_replace('/^\xEF\xBB\xBF/', '', $content) ?? $content;   // BOM

        foreach (preg_split('/\r\n|\r|\n/', $content) ?: [] as $line) {
            $line = trim($line);

            if ($line === '' || $line[0] === '#') {
                continue;
            }

            $pos = strpos($line, '=');

            if ($pos === false) {
                continue;
            }

            $key = trim(substr($line, 0, $pos));
            $value = trim(substr($line, $pos + 1));

            if (strlen($value) >= 2) {
                $first = $value[0];
                $last = $value[strlen($value) - 1];

                if (($first === '"' && $last === '"') || ($first === "'" && $last === "'")) {
                    $value = substr($value, 1, -1);
                }
            }

            if ($key !== '') {
                self::$values[$key] = $value;
            }
        }
    }

    public static function set(string $key, string $value): void
    {
        self::$values[$key] = $value;
    }

    public static function get(string $key, ?string $default = null): ?string
    {
        return self::$values[$key] ?? $default;
    }

    public static function int(string $key, int $default = 0): int
    {
        $value = self::get($key);

        return ($value !== null && is_numeric($value)) ? (int) $value : $default;
    }

    public static function bool(string $key, bool $default = false): bool
    {
        $value = self::get($key);

        if ($value === null || $value === '') {
            return $default;
        }

        return in_array(strtolower($value), ['1', 'true', 'yes', 'on'], true);
    }
}

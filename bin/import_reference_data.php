<?php
declare(strict_types=1);
require __DIR__ . '/../src/bootstrap.php';

use App\Db;
use App\Support\Clock;

try {
    $foodFile = APP_ROOT . '/data/foods.json';
    $foods = json_decode((string)file_get_contents($foodFile), true, 512, JSON_THROW_ON_ERROR);
    $count = (int)(Db::fetchOne('SELECT COUNT(*) n FROM food_items')['n'] ?? 0);
    if ($count > 0) {
        echo "جدول خوراکی‌ها از قبل {$count} ردیف دارد؛ برای جلوگیری از ایجاد داده تکراری، واردسازی انجام نشد.\n";
        echo "اگر می‌خواهید از نو وارد کنید، ابتدا جدول food_items را خالی کنید و دوباره این دستور را اجرا کنید.\n";
        exit(0);
    }
    $inserted=0;
    foreach($foods as $food) {
        $temperament=(string)$food['temperament'];
        if($temperament==='معتدل') {$warmth='معتدل';$moisture='معتدل';}
        else {
            $parts=explode(' و ',$temperament,2);
            $warmth=$parts[0]??'ثبت نشده';$moisture=$parts[1]??'ثبت نشده';
        }
        Db::execute(
            'INSERT INTO food_items (category,name,variety,temperament,warmth,moisture,description,active) VALUES (?,?,?,?,?,?,?,1)',
            [$food['category'],$food['name'],$food['variety'],$temperament,$warmth,$moisture,null]
        );
        $inserted++;
    }
    echo "✅ {$inserted} خوراکی از داده‌های نسخه پایتون وارد شد.\n";
} catch(Throwable $e) {
    fwrite(STDERR,"❌ خطا در واردسازی خوراکی‌ها: ".$e->getMessage()."\n");
    exit(1);
}

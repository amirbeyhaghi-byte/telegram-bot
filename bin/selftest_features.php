<?php
declare(strict_types=1);
require __DIR__ . '/../src/bootstrap.php';

$checks=0;$failed=0;
$check=static function(string $label,bool $ok) use (&$checks,&$failed): void {
    $checks++; echo ($ok?'✅ ':'❌ ').$label."\n"; if(!$ok)$failed++;
};
try {
    $questions=json_decode((string)file_get_contents(APP_ROOT.'/data/temperament_questions.json'),true,512,JSON_THROW_ON_ERROR);
    $temperaments=json_decode((string)file_get_contents(APP_ROOT.'/data/temperaments.json'),true,512,JSON_THROW_ON_ERROR);
    $foods=json_decode((string)file_get_contents(APP_ROOT.'/data/foods.json'),true,512,JSON_THROW_ON_ERROR);
    $check('فایل پرسش‌ها خوانده شد',is_array($questions));
    $check('تعداد پرسش‌های آزمون برابر نسخه پایتون است (۳۰)',count($questions)===30);
    $check('هر پرسش چهار گزینه دارد',count(array_filter($questions,static fn($q)=>isset($q['text'],$q['options'])&&count($q['options'])===4))===count($questions));
    $check('چهار مزاج تعریف شده است',count($temperaments)===4);
    $check('فهرست خوراکی‌های نسخه پایتون خوانده شد',is_array($foods));
    $check('تعداد خوراکی‌ها برابر seed نسخه پایتون است (۲۳۶)',count($foods)===236);
    $valid=['معتدل','گرم و تر','گرم و خشک','سرد و تر','سرد و خشک'];
    $check('طبع همه خوراکی‌ها معتبر است',count(array_filter($foods,static fn($f)=>in_array($f['temperament']??null,$valid,true)))===count($foods));
} catch(Throwable $e) {
    echo '❌ خطای خواندن داده‌ها: '.$e->getMessage()."\n";$failed++;
}
echo "\nنتیجه بررسی داده‌ها: ".($checks-$failed)." موفق، {$failed} ناموفق\n";
exit($failed?1:0);

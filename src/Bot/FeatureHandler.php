<?php
declare(strict_types=1);

namespace App\Bot;

use App\Db;
use App\Env;
use App\Services\Phone;
use App\Services\UserService;
use App\State\StateStore;
use App\Telegram\Keyboard;
use App\Support\Clock;

/**
 * قابلیت‌های منتقل‌شده از نسخه Python:
 * پرسش‌نامه مزاج، خوراکی‌ها، حساب/اشتراک، کد هدیه، پرداخت کارت‌به‌کارت و بررسی مدیر.
 */
final class FeatureHandler
{
    private array $questions;
    private array $temperaments;

    private const PLANS = [
        'monthly' => ['name' => 'ماهانه', 'days' => 30, 'toman' => 100000],
        'six_months' => ['name' => '۶ ماهه', 'days' => 180, 'toman' => 500000],
        'yearly' => ['name' => 'سالیانه', 'days' => 365, 'toman' => 800000],
    ];
    private const CATEGORIES = [
        'meat' => 'گوشت و فرآورده‌های گوشتی',
        'fish' => 'آبزیان',
        'dairy' => 'لبنیات و تخم‌مرغ',
        'grains' => 'غلات و حبوبات',
        'vegetables' => 'سبزیجات',
        'fruits' => 'میوه‌ها',
        'nuts' => 'مغزها و دانه‌ها',
        'spices' => 'ادویه‌ها و چاشنی‌ها',
        'drinks' => 'نوشیدنی‌ها',
        'other' => 'سایر خوراکی‌ها',
    ];

    public function __construct(private StateStore $states)
    {
        $q = json_decode((string) file_get_contents(APP_ROOT . '/data/temperament_questions.json'), true);
        $t = json_decode((string) file_get_contents(APP_ROOT . '/data/temperaments.json'), true);
        $this->questions = is_array($q) ? $q : [];
        $this->temperaments = is_array($t) ? $t : [];
    }

    private function state(Context $ctx, string $state, array $data): void
    {
        $this->states->set($ctx->userId, $state, $data);
    }

    private function menu(Context $ctx, ?string $phone): void
    {
        $this->states->set($ctx->userId, States::MAIN_MENU, ['phone_number' => $phone]);
        $ctx->reply('لطفاً خدمت موردنظر خود را انتخاب کنید:', ['reply_markup' => Keyboards::mainMenu($phone)]);
    }

    private function user(Context $ctx, array $data = []): ?array
    {
        $phone = (string) ($data['phone_number'] ?? '');
        if ($phone !== '') {
            $user = UserService::findByPhone($phone);
            if ($user) return $user;
        }
        return Db::fetchOne('SELECT * FROM users WHERE id = (SELECT id FROM users WHERE phone_number = ? LIMIT 1)', [$phone]);
    }

    private function isAdministrator(Context $ctx, array $data): bool
    {
        return Phone::isAdmin((string)($data['phone_number'] ?? ''))
            || ($ctx->userId > 0 && $ctx->userId === Env::int('ADMIN_TELEGRAM_ID', 0));
    }

    private function activeSubscription(int $userId, bool $administrator = false): ?array
    {
        if ($administrator) {
            return Db::fetchOne(
                "SELECT * FROM subscriptions WHERE user_id = ? AND status = 'active' ORDER BY end_date DESC LIMIT 1",
                [$userId]
            );
        }
        return Db::fetchOne(
            "SELECT * FROM subscriptions WHERE user_id = ? AND status = 'active' AND end_date > ? ORDER BY end_date DESC LIMIT 1",
            [$userId, Clock::now()]
        );
    }

    private function hasAccess(Context $ctx, array $data, string $service): bool
    {
        $user = $this->user($ctx, $data);
        if (!$user) {
            $ctx->reply(Texts::ACCOUNT_MISSING, ['reply_markup' => Keyboards::registration()]);
            $this->states->clear($ctx->userId);
            return false;
        }
        if ($user['status'] !== 'active') {
            $ctx->reply(Texts::ACCOUNT_DISABLED, ['reply_markup' => Keyboards::registration()]);
            $this->states->clear($ctx->userId);
            return false;
        }
        $administrator = $this->isAdministrator($ctx, $data);
        if ($administrator || $this->activeSubscription((int)$user['id'])) return true;
        $ctx->reply(
            "🔴 <b>اشتراک شما منقضی شده است.</b>\n\nبرای استفاده از خدمت «{$service}» لطفاً اشتراک خود را تمدید کنید.",
            ['reply_markup' => Keyboard::inline([[Keyboard::button('💳 مشاهده و خرید اشتراک', 'subscription:open')]])]
        );
        return false;
    }

    public function handleMenu(Context $ctx, ?string $text, array $data): bool
    {
        $phone = (string) ($data['phone_number'] ?? '');
        switch ($text) {
            case '📅 اشتراک ماهانه - ۱۰۰٬۰۰۰ تومان':
                $this->showPaymentTerms($ctx, 'monthly');
                return true;
            case '📆 اشتراک ۶ ماهه - ۵۰۰٬۰۰۰ تومان':
                $this->showPaymentTerms($ctx, 'six_months');
                return true;
            case '🗓 اشتراک سالیانه - ۸۰۰٬۰۰۰ تومان':
                $this->showPaymentTerms($ctx, 'yearly');
                return true;
            case '🎁 کد اشتراک هدیه':
                $this->states->set($ctx->userId, 'feature:gift_code', $data);
                $ctx->reply('🎁 کد اشتراک را وارد کنید:');
                return true;
            case '🔙 بازگشت به منوی اصلی':
                $this->menu($ctx, $phone);
                return true;
            case Texts::BTN_TEMPERAMENT:
                if ($this->hasAccess($ctx, $data, 'مزاج‌شناسی')) $this->showTemperamentIntro($ctx);
                return true;
            case Texts::BTN_FOOD:
                if ($this->hasAccess($ctx, $data, 'طبع‌شناسی خوراکی‌ها')) $this->showFoodCategories($ctx);
                return true;
            case Texts::BTN_ACCOUNT:
                $this->showAccount($ctx, $data);
                return true;
            case Texts::BTN_SUBSCRIPTION:
                $this->showSubscription($ctx, $data);
                return true;
            case Texts::BTN_ADMIN:
                if (!Phone::isAdmin($phone)) {
                    $ctx->reply('⛔ شما دسترسی به پنل مدیریت ندارید.');
                } else {
                    $this->showAdmin($ctx);
                }
                return true;
        }
        return false;
    }

    public function handleMessage(Context $ctx, string $state, array $data): bool
    {
        $text = trim($ctx->text ?? '');
        if ($state === 'feature:food_search') {
            if (in_array($text, [Texts::BTN_TEMPERAMENT, Texts::BTN_FOOD, Texts::BTN_ACCOUNT, Texts::BTN_SUBSCRIPTION, Texts::BTN_ADMIN, Texts::BTN_LOGOUT], true)) {
                $this->states->set($ctx->userId, States::MAIN_MENU, $data);
                return $this->handleMenu($ctx, $text, $data);
            }
            if (!$this->hasAccess($ctx, $data, 'طبع‌شناسی خوراکی‌ها')) {
                $this->states->set($ctx->userId, States::MAIN_MENU, $data);
                return true;
            }
            $query = $this->normalizeSearch($text);
            if (mb_strlen($query, 'UTF-8') < 2 || mb_strlen($query, 'UTF-8') > 40) {
                $ctx->reply('⚠️ عبارت جستجو باید بین ۲ تا ۴۰ حرف باشد.');
                return true;
            }
            $this->states->mergeData($ctx->userId, ['food_query' => $query]);
            $this->showFoodSearch($ctx, $query, 0, false);
            return true;
        }
        if ($state === 'feature:gift_code') {
            if ($text === Texts::BTN_SUBSCRIPTION || $text === '/cancel') {
                $this->states->set($ctx->userId, States::MAIN_MENU, $data);
                $this->showSubscription($ctx, $data);
                return true;
            }
            $this->redeemGiftCode($ctx, $data, $text);
            return true;
        }
        if ($state === 'feature:receipt') {
            if ($ctx->photoFileId === null && !($ctx->documentFileId !== null && str_starts_with((string)$ctx->documentMimeType, 'image/'))) {
                $ctx->reply('⚠️ لطفاً تصویر واضح فیش واریزی را به‌صورت عکس یا فایل تصویری ارسال کنید.');
                return true;
            }
            $paymentId = (int)($data['payment_id'] ?? 0);
            $payment = Db::fetchOne("SELECT * FROM payments WHERE id = ? AND user_id = ? AND status = 'awaiting_receipt'", [$paymentId, (int)($data['user_id'] ?? 0)]);
            if (!$payment) {
                $this->states->set($ctx->userId, States::MAIN_MENU, ['phone_number' => $data['phone_number'] ?? '']);
                $ctx->reply('⚠️ فاکتور فعال پیدا نشد. از بخش اشتراک دوباره اقدام کنید.');
                return true;
            }
            $fileId = $ctx->photoFileId ?? $ctx->documentFileId;
            $kind = $ctx->photoFileId !== null ? 'photo' : 'document';
            Db::execute("UPDATE payments SET receipt_file_id = ?, receipt_kind = ?, status = 'pending_review', receipt_sent_at = ? WHERE id = ?", [$fileId, $kind, Clock::now(), $paymentId]);
            $this->states->set($ctx->userId, States::MAIN_MENU, ['phone_number' => $data['phone_number'] ?? '']);
            $ctx->reply("✅ تصویر فیش دریافت شد و برای بررسی مدیر ارسال شد.\n\nپس از بررسی، نتیجه از طریق همین ربات اعلام می‌شود.", ['reply_markup' => Keyboards::mainMenu((string)($data['phone_number'] ?? ''))]);
            $adminId = Env::int('ADMIN_TELEGRAM_ID', 0);
            $user = UserService::findById((int)$payment['user_id']);
            $plan = self::PLANS[$payment['plan_type']] ?? ['name' => $payment['plan_type']];
            $caption = "🧾 <b>فیش واریزی — فاکتور " . self::fa((string)$paymentId) . "</b>\n"
                . "👤 کاربر: " . htmlspecialchars(($user['first_name'] ?? '') . ' ' . ($user['last_name'] ?? ''), ENT_QUOTES, 'UTF-8') . "\n"
                . "📱 موبایل: " . htmlspecialchars((string)($user['phone_number'] ?? ''), ENT_QUOTES, 'UTF-8') . "\n"
                . "📦 اشتراک: " . htmlspecialchars((string)$plan['name'], ENT_QUOTES, 'UTF-8') . "\n"
                . "💰 مبلغ: " . self::money((int)$payment['amount_rial']) . " ریال";
            if ($adminId > 0) {
                try {
                    if ($kind === 'photo') $ctx->api->sendPhoto($adminId, (string)$fileId, $caption, ['reply_markup' => Keyboard::inline([[Keyboard::button('✅ تأیید', 'pay:ok:' . $paymentId), Keyboard::button('❌ رد', 'pay:no:' . $paymentId)]])]);
                    else $ctx->api->sendDocument($adminId, (string)$fileId, $caption, ['reply_markup' => Keyboard::inline([[Keyboard::button('✅ تأیید', 'pay:ok:' . $paymentId), Keyboard::button('❌ رد', 'pay:no:' . $paymentId)]])]);
                } catch (\Throwable) {}
            }
            return true;
        }
        if ($state === 'feature:admin_user_search') {
            if (!Phone::isAdmin((string)($data['phone_number'] ?? ''))) {
                $ctx->reply('⛔ دسترسی غیرمجاز.');
                return true;
            }
            $phone = Phone::normalize($text);
            $q = '%' . $phone . '%';
            $rows = Db::fetchAll('SELECT id, first_name, last_name, phone_number, status FROM users WHERE phone_number LIKE ? ORDER BY id DESC LIMIT 10', [$q]);
            $buttons = [];
            foreach ($rows as $r) $buttons[] = [Keyboard::button(($r['status']==='active'?'🟢 ':'🔴 ').$r['first_name'].' '.$r['last_name'].' — '.$r['phone_number'], 'admin:user:'.$r['id'])];
            $buttons[] = [Keyboard::button('↩️ مدیریت کاربران', 'admin:users')];
            $ctx->reply($rows ? '📱 <b>نتایج جستجوی شماره موبایل:</b>' : '❌ کاربری با این شماره پیدا نشد.', ['reply_markup' => Keyboard::inline($buttons)]);
            $this->states->set($ctx->userId, States::MAIN_MENU, $data);
            return true;
        }
        return false;
    }

    public function handleCallback(Context $ctx, string $state, array $data): bool
    {
        $cb = (string)$ctx->callbackData;
        if ($cb === '') return false;

        if (str_starts_with($cb, 'tq:')) {
            $this->handleTemperamentCallback($ctx, $data, $cb);
            return true;
        }
        if (str_starts_with($cb, 'food:')) {
            $this->handleFoodCallback($ctx, $data, $cb);
            return true;
        }
        if (str_starts_with($cb, 'subscription:') || str_starts_with($cb, 'payment:') || str_starts_with($cb, 'pay:') || str_starts_with($cb, 'gift:') || str_starts_with($cb, 'admin:')) {
            $this->handleSubscriptionAdminCallback($ctx, $data, $cb);
            return true;
        }
        return false;
    }

    private function showTemperamentIntro(Context $ctx): void
    {
        $total = count($this->questions);
        $ctx->reply("🌿 <b>مزاج‌شناسی</b>\n\nدر این آزمون " . self::fa((string)$total) . " پرسش از شما پرسیده می‌شود و برای هر پرسش چهار گزینه وجود دارد. گزینه‌ای را انتخاب کنید که به حالت طبیعی و همیشگی شما نزدیک‌تر است.\n\n🔹 می‌توانید به پرسش قبلی برگردید و پاسخ را اصلاح کنید.\n🔹 نتیجه‌ها ذخیره نمی‌شوند.", ['reply_markup' => Keyboard::inline([[Keyboard::button('▶️ شروع آزمون', 'tq:start')],[Keyboard::button('↩️ منوی اصلی', 'tq:menu')]])]);
    }

    private function handleTemperamentCallback(Context $ctx, array $data, string $cb): void
    {
        if ($cb === 'tq:menu' || $cb === 'tq:cancel') {
            $this->menu($ctx, (string)($data['phone_number'] ?? ''));
            $ctx->answerCallback('به منوی اصلی برگشتید.');
            return;
        }
        if ($cb === 'tq:start') {
            $order = [];
            foreach ($this->questions as $q) { $keys = array_keys($q['options']); shuffle($keys); $order[] = $keys; }
            $session = ['order'=>$order, 'answers'=>array_fill(0,count($this->questions),null)];
            $this->states->mergeData($ctx->userId, ['tq'=>$session]);
            $this->renderQuestion($ctx, $session, 0);
            $ctx->answerCallback();
            return;
        }
        $session = $data['tq'] ?? null;
        if (!is_array($session) || count($session['answers'] ?? []) !== count($this->questions)) {
            $ctx->answerCallback('آزمون منقضی شده است؛ دوباره شروع کنید.', true);
            $this->showTemperamentIntro($ctx);
            return;
        }
        if (preg_match('/^tq:a:(\d+):([a-z]+)$/', $cb, $m)) {
            $i=(int)$m[1]; $key=$m[2];
            if (!isset($this->questions[$i]['options'][$key]) || !in_array($key,$session['order'][$i] ?? [],true)) { $ctx->answerCallback(); return; }
            $frontier = $this->firstUnanswered($session);
            if ($frontier !== null && $i > $frontier) { $ctx->answerCallback(); return; }
            $session['answers'][$i]=$key;
            $this->states->mergeData($ctx->userId,['tq'=>$session]);
            $next=$this->firstUnanswered($session);
            if ($next === null) {
                $this->showResult($ctx, $session);
                $this->states->mergeData($ctx->userId,['tq'=>null]);
            } else $this->renderQuestion($ctx,$session,$next);
            $ctx->answerCallback();
            return;
        }
        if (preg_match('/^tq:back:(\d+)$/',$cb,$m)) {
            $this->renderQuestion($ctx,$session,max(0,(int)$m[1]-1)); $ctx->answerCallback(); return;
        }
        if (preg_match('/^tq:go:(\d+)$/',$cb,$m)) {
            $frontier=$this->firstUnanswered($session);
            $idx=min(max(0,(int)$m[1]),$frontier ?? count($this->questions)-1);
            $this->renderQuestion($ctx,$session,$idx); $ctx->answerCallback(); return;
        }
        $ctx->answerCallback();
    }

    private function renderQuestion(Context $ctx, array $session, int $i): void
    {
        $q=$this->questions[$i]; $order=$session['order'][$i];
        $answered=count(array_filter($session['answers'],static fn($a)=>$a!==null));
        $bar=str_repeat('▰',(int)round($answered/max(1,count($this->questions))*10)).str_repeat('▱',10-(int)round($answered/max(1,count($this->questions))*10));
        $text="🌿 <b>مزاج‌شناسی</b>\nسؤال ".self::fa((string)($i+1))." از ".self::fa((string)count($this->questions))."  ".$bar."\n\n<b>".htmlspecialchars($q['text'],ENT_QUOTES,'UTF-8')."</b>\n\n";
        $rows=[];
        foreach($order as $pos=>$key) {
            $text .= ['1️⃣','2️⃣','3️⃣','4️⃣'][$pos].' '.htmlspecialchars($q['options'][$key],ENT_QUOTES,'UTF-8')."\n\n";
            $rows[]=[Keyboard::button((['1️⃣','2️⃣','3️⃣','4️⃣'][$pos]).' انتخاب گزینه', 'tq:a:'.$i.':'.$key)];
        }
        $rows[]=[Keyboard::button('⬅️ سؤال قبلی','tq:back:'.$i),Keyboard::button('❌ انصراف','tq:cancel')];
        $ctx->edit($text."یکی از گزینه‌ها را انتخاب کنید:",['reply_markup'=>Keyboard::inline($rows)]);
    }

    private function firstUnanswered(array $session): ?int
    {
        foreach (($session['answers'] ?? []) as $i=>$answer) if ($answer===null) return (int)$i;
        return null;
    }

    private function showResult(Context $ctx, array $session): void
    {
        $keys=['balghami','safravi','damavi','saudavi']; $counts=array_fill_keys($keys,0);
        foreach($session['answers'] as $answer) if(isset($counts[$answer])) $counts[$answer]++;
        $sum=array_sum($counts); $percent=[];
        if($sum===0) $percent=array_fill_keys($keys,0);
        else {
            $exact=[]; foreach($keys as $k){$exact[$k]=$counts[$k]*100/$sum;$percent[$k]=(int)floor($exact[$k]);}
            $left=100-array_sum($percent); $rank=$keys; usort($rank,fn($a,$b)=>(($exact[$b]-$percent[$b])<=>($exact[$a]-$percent[$a])));
            for($j=0;$j<$left;$j++) $percent[$rank[$j]]++;
        }
        usort($keys,fn($a,$b)=>$percent[$b]<=>$percent[$a]);
        $lines=['🌿 <b>نتیجه مزاج‌شناسی</b>','','مزاج شما به نسبت پاسخ‌ها به شرح زیر می‌باشد:',''];
        foreach($keys as $k){$t=$this->temperaments[$k];$lines[]=$t['emoji'].' '.self::fa((string)$percent[$k]).'٪ '.$t['name'].' ('.$t['quality'].')';}
        $highest=max($percent);$dominant=[];foreach($this->temperaments as $k=>$t)if($percent[$k]===$highest)$dominant[]=$t['name'];
        $lines[]='';$lines[]='<b>مزاج غالب: '.implode(' و ',$dominant).'</b>';$lines[]='';$lines[]='⚠️ این نتایج قطعی نیست و به تناسب شرایط فردی و نوع تغذیه هر فرد می‌تواند متفاوت باشد.';
        $ctx->edit(implode("\n",$lines),['reply_markup'=>Keyboard::inline([[Keyboard::button('🔁 آزمون مجدد','tq:start')],[Keyboard::button('↩️ منوی اصلی','tq:menu')]])]);
    }

    private function showFoodCategories(Context $ctx): void
    {
        $categories=Db::fetchAll('SELECT DISTINCT category FROM food_items WHERE active=1 ORDER BY category');
        $rows=[];
        foreach($categories as $i=>$c) $rows[]=[Keyboard::button('📂 '.$c['category'],'food:c:'.$i.':0')];
        $rows[]=[Keyboard::button('🔍 جستجوی خوراکی','food:s')];
        $rows[]=[Keyboard::button('↩️ منوی اصلی','food:menu')];
        $ctx->reply("🍎 <b>طبع‌شناسی خوراکی‌ها</b>\n\nدسته‌بندی موردنظر را انتخاب کنید یا خوراکی را جستجو کنید:",['reply_markup'=>Keyboard::inline($rows)]);
    }

    private function categoryByIndex(int $index): ?string
    {
        $rows=Db::fetchAll('SELECT DISTINCT category FROM food_items WHERE active=1 ORDER BY category');
        return isset($rows[$index]['category']) ? (string)$rows[$index]['category'] : null;
    }

    private function categoryIndex(string $category): int
    {
        $rows=Db::fetchAll('SELECT DISTINCT category FROM food_items WHERE active=1 ORDER BY category');
        foreach($rows as $i=>$row) if((string)$row['category']===$category) return (int)$i;
        return 0;
    }

    private function normalizeSearch(string $q): string
    {
        $q=str_replace(["ي","ى","ك","\u{200C}"],["ی","ی","ک",""],$q);
        return trim(preg_replace('/\s+/u',' ',$q) ?? $q);
    }

    private function handleFoodCallback(Context $ctx, array $data, string $cb): void
    {
        if ($cb==='food:menu' || $cb==='food_back_main') { $this->menu($ctx,(string)($data['phone_number']??''));$ctx->answerCallback();return; }
        if ($cb==='food:cats') {$this->showFoodCategories($ctx);$ctx->answerCallback();return;}
        if ($cb==='food:s') {$this->states->set($ctx->userId,'feature:food_search',$data);$ctx->reply('🔍 نام خوراکی یا نوع آن را بنویسید (حداقل ۲ حرف).');$ctx->answerCallback();return;}
        if (preg_match('/^food:c:(\d+):(\d+)$/',$cb,$m)) {
            $category=$this->categoryByIndex((int)$m[1]);$page=(int)$m[2];
            if($category===null){$ctx->answerCallback('دسته نامعتبر است.',true);return;}
            $this->showFoodCategoryPage($ctx,$category,$page);$ctx->answerCallback();return;
        }
        if (preg_match('/^food:i:(\d+):([0-9]+)$/',$cb,$m)) {$this->showFoodDetail($ctx,(int)$m[1],(int)$m[2]);$ctx->answerCallback();return;}
        // انتخاب یکی از گونه‌های یک خوراکی؛ این callback در صفحه فهرست گونه‌ها ساخته می‌شود.
        if (preg_match('/^food:v:(\d+):(\d+)$/',$cb,$m)) {$this->showFoodVariety($ctx,(int)$m[1],(int)$m[2]);$ctx->answerCallback();return;}
        if (preg_match('/^food:q:(\d+)$/',$cb,$m)) {$q=(string)($data['food_query']??'');$this->showFoodSearch($ctx,$q,(int)$m[1],true);$ctx->answerCallback();return;}
        $ctx->answerCallback();
    }

    private function showFoodCategoryPage(Context $ctx,string $category,int $page): void
    {
        $page=max(0,$page);$size=10;
        $total=(int)(Db::fetchOne('SELECT COUNT(DISTINCT name) n FROM food_items WHERE active=1 AND category=?',[$category])['n']??0);
        $pages=max(1,(int)ceil($total/$size));$page=min($page,$pages-1);
        $items=Db::fetchAll('SELECT MIN(id) id,name,COUNT(*) variants FROM food_items WHERE active=1 AND category=? GROUP BY name ORDER BY name LIMIT '.$size.' OFFSET '.($page*$size),[$category]);
        $rows=[];
        foreach($items as $it)$rows[]=[Keyboard::button($it['name'].((int)$it['variants']>1?' ('.self::fa((string)$it['variants']).' نوع)':''),'food:i:'.(int)$it['id'].':'.$page)];
        $nav=[];if($page>0)$nav[]=Keyboard::button('⬅️ قبلی','food:c:'.$this->categoryIndex($category).':'.($page-1));if($page<$pages-1)$nav[]=Keyboard::button('بعدی ➡️','food:c:'.$this->categoryIndex($category).':'.($page+1));if($nav)$rows[]=$nav;
        $rows[]=[Keyboard::button('🔍 جستجو','food:s'),Keyboard::button('↩️ دسته‌ها','food:cats')];
        $rows[]=[Keyboard::button('↩️ منوی اصلی','food:menu')];
        $ctx->edit('📂 <b>'.htmlspecialchars($category,ENT_QUOTES,'UTF-8')."</b>\nتعداد: ".self::fa((string)$total)." خوراکی\n\nمورد موردنظر را انتخاب کنید:",['reply_markup'=>Keyboard::inline($rows)]);
    }

    private function showFoodDetail(Context $ctx,int $id,int $page): void
    {
        $item=Db::fetchOne('SELECT * FROM food_items WHERE id=? AND active=1',[$id]);
        if(!$item){$ctx->answerCallback('خوراکی پیدا نشد.',true);return;}
        $siblings=Db::fetchAll('SELECT * FROM food_items WHERE category=? AND name=? AND active=1 ORDER BY variety,id',[$item['category'],$item['name']]);
        if(count($siblings)>1){
            $rows=[];foreach($siblings as $sib)$rows[]=[Keyboard::button(($sib['variety']?:'نوع اصلی'),'food:v:'.(int)$sib['id'].':'.$page)];
            $rows[]=[Keyboard::button('↩️ بازگشت','food:c:'.$this->categoryIndex((string)$item['category']).':'.$page)];
            $ctx->edit('🍎 <b>'.htmlspecialchars($item['name'],ENT_QUOTES,'UTF-8')."</b>\n\nنوع یا گونه موردنظر را انتخاب کنید:",['reply_markup'=>Keyboard::inline($rows)]);return;
        }
        $this->renderFoodItem($ctx,$item,$page);
    }

    /** نمایش جزئیات گونه انتخاب‌شده از فهرست گونه‌های خوراکی. */
    private function showFoodVariety(Context $ctx,int $id,int $page): void
    {
        $item=Db::fetchOne('SELECT * FROM food_items WHERE id=? AND active=1',[$id]);
        if(!$item){$ctx->answerCallback('این نوع خوراکی پیدا نشد.',true);return;}
        $this->renderFoodItem($ctx,$item,$page);
    }

    private function renderFoodItem(Context $ctx,array $item,int $page): void
    {
        $temperament=$item['temperament']?:'ثبت نشده';
        $text="🍎 <b>اطلاعات خوراکی</b>\n\n📌 <b>نام:</b> ".htmlspecialchars($item['name'],ENT_QUOTES,'UTF-8')."\n📂 <b>دسته:</b> ".htmlspecialchars($item['category'],ENT_QUOTES,'UTF-8')."\n";
        if($item['variety'])$text.="🔹 <b>نوع / گونه:</b> ".htmlspecialchars($item['variety'],ENT_QUOTES,'UTF-8')."\n";
        $text.="🌡 <b>طبع:</b> ".htmlspecialchars($temperament,ENT_QUOTES,'UTF-8')."\n";
        if($item['description'])$text.="\n📝 <b>توضیحات:</b>\n".htmlspecialchars($item['description'],ENT_QUOTES,'UTF-8');
        $ctx->edit($text,['reply_markup'=>Keyboard::inline([[Keyboard::button('↩️ بازگشت به فهرست','food:c:'.$this->categoryIndex((string)$item['category']).':'.$page)],[Keyboard::button('🔍 جستجو','food:s')],[Keyboard::button('↩️ منوی اصلی','food:menu')]])]);
    }

    private function showFoodSearch(Context $ctx,string $query,int $page,bool $edit): void
    {
        $query=$this->normalizeSearch($query);$pattern='%'.$query.'%';$size=8;$page=max(0,$page);
        $total=(int)(Db::fetchOne('SELECT COUNT(*) n FROM food_items WHERE active=1 AND (name LIKE ? OR variety LIKE ? OR CONCAT(name," ",COALESCE(variety,"")) LIKE ?)',[$pattern,$pattern,$pattern])['n']??0);
        $pages=max(1,(int)ceil($total/$size));$page=min($page,$pages-1);
        $items=Db::fetchAll('SELECT * FROM food_items WHERE active=1 AND (name LIKE ? OR variety LIKE ? OR CONCAT(name," ",COALESCE(variety,"")) LIKE ?) ORDER BY name,variety,id LIMIT '.$size.' OFFSET '.($page*$size),[$pattern,$pattern,$pattern]);
        $rows=[];foreach($items as $it)$rows[]=[Keyboard::button($it['name'].($it['variety']?' — '.$it['variety']:''),'food:i:'.(int)$it['id'].':'.$page)];
        if($pages>1){$nav=[];if($page>0)$nav[]=Keyboard::button('⬅️ قبلی','food:q:'.($page-1));if($page<$pages-1)$nav[]=Keyboard::button('بعدی ➡️','food:q:'.($page+1));$rows[]=$nav;}
        $rows[]=[Keyboard::button('📂 دسته‌بندی‌ها','food:cats'),Keyboard::button('↩️ منوی اصلی','food:menu')];
        $text=$total ? "🔍 <b>نتایج جستجو برای «".htmlspecialchars($query,ENT_QUOTES,'UTF-8')."»</b>\nتعداد: ".self::fa((string)$total)." مورد\n\nیکی را انتخاب کنید:" : "🔍 نتیجه‌ای برای «".htmlspecialchars($query,ENT_QUOTES,'UTF-8')."» پیدا نشد.\n\nعبارت دیگری بنویسید یا از دسته‌ها انتخاب کنید.";
        $ctx->reply($text,['reply_markup'=>Keyboard::inline($rows)]);
    }

    private function showAccount(Context $ctx,array $data): void
    {
        $user = $this->user($ctx, $data);
        if (!$user) { $ctx->reply(Texts::ACCOUNT_MISSING); return; }

        $administrator = $this->isAdministrator($ctx, $data);
        $sub = Db::fetchOne('SELECT * FROM subscriptions WHERE user_id=? ORDER BY end_date DESC LIMIT 1', [(int)$user['id']]);
        $name = htmlspecialchars((string)$user['first_name'].' '.(string)$user['last_name'], ENT_QUOTES, 'UTF-8');
        $phone = htmlspecialchars((string)$user['phone_number'], ENT_QUOTES, 'UTF-8');
        $registered = self::dateGregorian((string)$user['created_at']);
        $text = "👤 <b>حساب کاربری</b>\n\n👤 <b>نام:</b> {$name}\n📱 <b>شماره موبایل:</b> {$phone}\n📅 <b>تاریخ ثبت‌نام:</b> {$registered}\n";

        if ($sub) {
            $isActive = $administrator || ($sub['status'] === 'active' && $sub['end_date'] > Clock::now());
            $type = self::subscriptionTypeName((string)$sub['type']);
            $start = self::dateGregorian((string)$sub['start_date']);
            $end = self::dateGregorian((string)$sub['end_date']);
            if ($isActive) {
                // تغییر یافته: استفاده از تابع محاسبه دقیق زمان
                $remaining = $administrator ? 'نامحدود (مدیر سامانه)' : self::formatRemainingTime((string)$sub['end_date']);
                $text .= "\n<b>💳 اشتراک</b>\n📌 <b>نوع:</b> {$type}\n🟢 <b>وضعیت:</b> 🟢 فعال\n📅 <b>شروع:</b> {$start}\n📅 <b>پایان:</b> {$end}\n⏳ <b>مدت باقی‌مانده:</b> {$remaining}\n";
            } else {
                $text .= "\n<b>💳 اشتراک</b>\n📌 <b>نوع:</b> {$type}\n🔴 <b>وضعیت:</b> منقضی شده\n📅 <b>تاریخ پایان:</b> {$end}\n";
            }
        } elseif ($administrator) {
            $text .= "\n<b>💳 اشتراک</b>\n📌 <b>نوع:</b> مدیر سامانه\n🟢 <b>وضعیت:</b> 🟢 فعال\n⏳ <b>مدت باقی‌مانده:</b> نامحدود\n";
        } else {
            $text .= "\n<b>💳 اشتراک</b>\n🔴 <b>وضعیت:</b> اشتراکی ثبت نشده است.\n";
        }

        $ctx->reply($text, ['reply_markup'=>Keyboard::inline([
            [Keyboard::button('💳 اشتراک من','subscription:open')],
            [Keyboard::button('↩️ منوی اصلی','subscription:back_main')],
        ])]);
    }

    private function showSubscription(Context $ctx,array $data): void
    {
        $user = $this->user($ctx, $data);
        if (!$user) { $ctx->reply(Texts::ACCOUNT_MISSING); return; }

        $administrator = $this->isAdministrator($ctx, $data);
        $sub = Db::fetchOne('SELECT * FROM subscriptions WHERE user_id=? ORDER BY end_date DESC LIMIT 1', [(int)$user['id']]);
        $text = "💳 <b>اشتراک</b>\n\n";

        if ($sub) {
            $isActive = $administrator || ($sub['status'] === 'active' && $sub['end_date'] > Clock::now());
            $type = self::subscriptionTypeName((string)$sub['type']);
            $start = self::dateJalali((string)$sub['start_date']);
            $end = self::dateJalali((string)$sub['end_date']);

            if ($isActive) {
                // تغییر یافته: استفاده از تابع محاسبه دقیق زمان
                $remaining = $administrator ? 'نامحدود' : self::formatRemainingTime((string)$sub['end_date']);
                $text .= "📌 <b>نوع اشتراک:</b> {$type}\n";
                $text .= "🟢 <b>وضعیت:</b> فعال\n";
                $text .= "📅 <b>تاریخ شروع:</b> {$start}\n";
                $text .= "📅 <b>تاریخ پایان:</b> {$end}\n";
                $text .= "⏳ <b>مدت باقی‌مانده:</b> {$remaining}\n\n";
            } else {
                $text .= "📌 <b>نوع اشتراک:</b> {$type}\n";
                $text .= "🔴 <b>وضعیت:</b> منقضی شده\n";
                $text .= "📅 <b>تاریخ پایان:</b> {$end}\n\n";
            }
        } elseif ($administrator) {
            $text .= "📌 <b>نوع اشتراک:</b> مدیر سامانه\n";
            $text .= "🟢 <b>وضعیت:</b> فعال\n";
            $text .= "⏳ <b>مدت باقی‌مانده:</b> نامحدود\n\n";
        } else {
            $text .= "🔴 <b>وضعیت:</b> اشتراکی ثبت نشده است.\n\n";
        }

        $text .= "برای تمدید یا تغییر اشتراک، یکی از گزینه‌های زیر را انتخاب کنید.";

        $ctx->reply($text, ['reply_markup'=>Keyboards::subscriptionMenu()]);
    }

    private static function subscriptionTypeName(string $type): string
    {
        return match ($type) {
            // تغییر یافته: تغییر نام اشتراک رایگان به وضعیت یک ماهه رایگان
            'free' => '🎁 وضعیت یک ماهه رایگان',
            'monthly' => 'ماهانه',
            'six_months' => '۶ ماهه',
            'yearly' => 'سالیانه',
            default => $type,
        };
    }

    private static function dateGregorian(string $value): string
    {
        $timestamp = strtotime($value);
        return $timestamp === false ? substr($value, 0, 10) : gmdate('Y/m/d', $timestamp);
    }

    /** تبدیل میلادی به شمسی، مطابق قالب تاریخ نسخه پایتون. */
    private static function dateJalali(string $value): string
    {
        $timestamp = strtotime($value);
        if ($timestamp === false) return substr($value, 0, 10);
        $g = array_map('intval', explode('-', gmdate('Y-m-d', $timestamp)));
        [$gy, $gm, $gd] = $g;
        $gdm = [0,31, (($gy%4===0 && $gy%100!==0) || $gy%400===0)?29:28,31,30,31,30,31,31,30,31,30,31];
        $gy2 = $gm > 2 ? $gy + 1 : $gy;
        $days = 355666 + 365*$gy + intdiv($gy2+3,4) - intdiv($gy2+99,100) + intdiv($gy2+399,400) + $gd;
        for ($i=1; $i<$gm; $i++) $days += $gdm[$i];
        $jy = -1595 + 33*intdiv($days,12053); $days %= 12053;
        $jy += 4*intdiv($days,1461); $days %= 1461;
        if ($days > 365) { $jy += intdiv($days-1,365); $days = ($days-1)%365; }
        if ($days < 186) { $jm = 1 + intdiv($days,31); $jd = 1 + ($days%31); }
        else { $jm = 7 + intdiv($days-186,30); $jd = 1 + (($days-186)%30); }
        return sprintf('%04d/%02d/%02d', $jy, $jm, $jd);
    }

    private function handleSubscriptionAdminCallback(Context $ctx,array $data,string $cb): void
    {
        if (str_starts_with($cb, 'admin:') && !Phone::isAdmin((string)($data['phone_number'] ?? '')) && $ctx->userId !== Env::int('ADMIN_TELEGRAM_ID', 0)) {
            $ctx->answerCallback('دسترسی غیرمجاز', true);
            return;
        }

        if ($cb === 'subscription:open') {
            $this->showSubscription($ctx,$data);
            $ctx->answerCallback();
            return;
        }
        if ($cb === 'subscription:back_main') {
            $this->menu($ctx,(string)($data['phone_number']??''));
            $ctx->answerCallback();
            return;
        }
        if ($cb === 'subscription:gift_code') {
            $this->states->set($ctx->userId,'feature:gift_code',$data);
            $ctx->reply('🎁 کد اشتراک را وارد کنید:');
            $ctx->answerCallback();
            return;
        }
        if (preg_match('/^subscription:(monthly|six_months|yearly)$/',$cb,$m)) {
            $this->showPaymentTerms($ctx,$m[1]);
            $ctx->answerCallback();
            return;
        }
        if (preg_match('/^subscription:confirm:(monthly|six_months|yearly)$/',$cb,$m)) {
            $this->createPaymentInvoice($ctx,$data,$m[1]);
            $ctx->answerCallback();
            return;
        }
        if ($cb === 'subscription:terms_back') {
            $this->showSubscription($ctx,$data);
            $ctx->answerCallback();
            return;
        }

        if (preg_match('/^payment:receipt:(\d+)$/',$cb,$m)) {
            $paymentId = (int)$m[1];
            $payment = Db::fetchOne("SELECT * FROM payments WHERE id=? AND user_id=? AND status='awaiting_receipt'", [$paymentId, (int)($data['user_id'] ?? 0)]);
            if (!$payment) {
                $ctx->answerCallback('فاکتور فعال پیدا نشد.', true);
                return;
            }
            $this->states->set($ctx->userId,'feature:receipt',[
                'phone_number'=>$data['phone_number'] ?? '',
                'user_id'=>(int)($data['user_id'] ?? 0),
                'payment_id'=>$paymentId,
            ]);
            $ctx->reply('📤 لطفاً تصویر واضح فیش واریزی را به‌صورت عکس یا فایل تصویری ارسال کنید.');
            $ctx->answerCallback();
            return;
        }
        if (preg_match('/^payment:cancel:(\d+)$/',$cb,$m)) {
            $paymentId = (int)$m[1];
            Db::execute("UPDATE payments SET status='cancelled' WHERE id=? AND user_id=? AND status='awaiting_receipt'", [$paymentId, (int)($data['user_id'] ?? 0)]);
            $this->states->set($ctx->userId,States::MAIN_MENU,['phone_number'=>$data['phone_number'] ?? '']);
            $ctx->reply('❌ پرداخت لغو شد.\n\nدر صورت تمایل می‌توانید دوباره از بخش اشتراک اقدام کنید.', ['reply_markup'=>Keyboards::mainMenu((string)($data['phone_number'] ?? ''))]);
            $ctx->answerCallback('پرداخت لغو شد.');
            return;
        }

        if (preg_match('/^pay:(ok|no):(\d+)$/',$cb,$m)) {
            if(!Phone::isAdmin((string)($data['phone_number']??'')) && $ctx->userId!==Env::int('ADMIN_TELEGRAM_ID',0)){
                $ctx->answerCallback('دسترسی غیرمجاز',true);
                return;
            }
            $this->reviewPayment($ctx,(int)$m[2],$m[1]==='ok');
            $ctx->answerCallback();
            return;
        }

        // پنل مدیریت: مرحله اول دقیقاً پنج گزینه دارد.
        if($cb==='admin:menu'){$this->showAdmin($ctx);$ctx->answerCallback();return;}
        if($cb==='admin:codes'){$this->listCodes($ctx,'all');$ctx->answerCallback();return;}
        if($cb==='admin:create'){$this->showCreateCodePlans($ctx);$ctx->answerCallback();return;}
        if($cb==='admin:users'){$this->showUserManagement($ctx);$ctx->answerCallback();return;}
        if($cb==='admin:userlist:0'){$this->listUsers($ctx,0);$ctx->answerCallback();return;}
        if(preg_match('/^admin:userlist:(\d+)$/',$cb,$m)){$this->listUsers($ctx,(int)$m[1]);$ctx->answerCallback();return;}
        if($cb==='admin:usersearch'){
            $ctx->reply('📱 لطفاً شماره موبایل کاربر را وارد کنید:');
            $this->states->set($ctx->userId,'feature:admin_user_search',$data);
            $ctx->answerCallback();
            return;
        }
        if($cb==='admin:pays'){$this->listPendingPayments($ctx);$ctx->answerCallback();return;}
        if(preg_match('/^admin:pay:(\d+)$/',$cb,$m)){$this->openPendingPayment($ctx,(int)$m[1]);$ctx->answerCallback();return;}

        if (preg_match('/^admin:codes:(all|usable|inactive|used|refresh)$/',$cb,$m)) {
            $filter = $m[1] === 'refresh' ? 'all' : $m[1];
            $this->listCodes($ctx,$filter);
            $ctx->answerCallback();
            return;
        }
        if(preg_match('/^admin:create:(monthly|six_months|yearly)$/',$cb,$m)){
            $this->createSubscriptionCode($ctx,$m[1]);
            $ctx->answerCallback();
            return;
        }
        if(preg_match('/^admin:codeoff:(\d+)$/',$cb,$m)){
            Db::execute('UPDATE subscription_codes SET active=0 WHERE id=? AND used=0',[(int)$m[1]]);
            $this->listCodes($ctx,'all');
            $ctx->answerCallback('کد غیرفعال شد.');
            return;
        }
        if(preg_match('/^admin:user:(\d+)$/',$cb,$m)){
            $u=UserService::findById((int)$m[1]);
            if(!$u){$ctx->answerCallback('کاربر پیدا نشد.',true);return;}
            $this->showUserDetails($ctx,$u);
            $ctx->answerCallback();
            return;
        }
        if(preg_match('/^admin:usertoggle:(\d+)$/',$cb,$m)){
            $u=UserService::findById((int)$m[1]);
            if($u){
                $new=$u['status']==='active'?'disabled':'active';
                Db::execute('UPDATE users SET status=? WHERE id=?',[$new,(int)$u['id']]);
                $updated=UserService::findById((int)$u['id']);
                if($updated) $this->showUserDetails($ctx,$updated);
            }
            $ctx->answerCallback('وضعیت کاربر بروزرسانی شد.');
            return;
        }
        if(preg_match('/^admin:userback:(\d+)$/',$cb,$m)){
            $this->listUsers($ctx,(int)$m[1]);
            $ctx->answerCallback();
            return;
        }

        $ctx->answerCallback();
    }

    private function showPaymentTerms(Context $ctx, string $planKey): void
    {
        $plan = self::PLANS[$planKey] ?? null;
        if (!$plan) {
            $ctx->answerCallback('پلن نامعتبر است.', true);
            return;
        }

        $text = "⭕️ <b>لطفاً قبل از ادامه، موارد زیر را با دقت مطالعه کنید!</b>\n\n"
            . "1. شما موظف به پرداخت دقیق مبلغ درج شده در متن فاکتور هستید! به هیچ عنوان حتی یک قرون هم تغییر ندهید و رند نکنید!\n\n"
            . "2. پس از پرداخت حتماً رسید واریزی را ارسال فرمایید تا به تأیید مدیر سامانه برسد.\n"
            . "3. فرآیند بررسی، تأیید و فعال‌سازی حداکثر 24 ساعت زمان خواهد برد.\n"
            . "4. مبلغ فاکتور به شماره کارت اعلام‌شده در مرحله بعد می‌بایست واریز گردد.\n\n"
            . "با مطالعه موارد فوق، مسئولیت رعایت شرایط و احتیاط را می‌پذیرم و برای ادامه فرآیند پرداخت آماده هستم⬇️";

        $ctx->reply($text,['reply_markup'=>Keyboard::inline([
            [Keyboard::button('✅ مطالعه کردم و می‌پذیرم','subscription:confirm:'.$planKey)],
            [Keyboard::button('↩️ بازگشت به اشتراک','subscription:terms_back')],
        ])]);
    }

    private function createPaymentInvoice(Context $ctx,array $data,string $planKey): void
    {
        $user=$this->user($ctx,$data);
        if(!$user){$ctx->reply(Texts::ACCOUNT_MISSING);return;}

        $plan=self::PLANS[$planKey] ?? null;
        if(!$plan){$ctx->reply('⚠️ پلن انتخاب‌شده معتبر نیست.');return;}

        $cfg=[
            'card'=>preg_replace('/\D/','',Env::get('PAYMENT_CARD_NUMBER','')??''),
            'bank'=>Env::get('PAYMENT_CARD_BANK','')??'',
            'owner'=>Env::get('PAYMENT_CARD_OWNER','')??''
        ];
        if(strlen($cfg['card'])!==16 || $cfg['bank']==='' || $cfg['owner']===''){
            $ctx->reply('⚠️ تنظیمات کارت مقصد کامل نیست. مدیر سامانه باید PAYMENT_CARD_NUMBER، PAYMENT_CARD_BANK و PAYMENT_CARD_OWNER را در فایل .env تنظیم کند.');
            return;
        }

        Db::execute("UPDATE payments SET status='cancelled' WHERE user_id=? AND status='awaiting_receipt'",[(int)$user['id']]);
        $amount=$plan['toman']*10;
        $id=Db::insert(
            'INSERT INTO payments (user_id,telegram_id,plan_type,duration_days,amount_rial,status,created_at) VALUES (?,?,?,?,?,?,?)',
            [(int)$user['id'],$ctx->userId,$planKey,$plan['days'],$amount,'awaiting_receipt',Clock::now()]
        );

        $amountText=self::money($amount).' ریال';
        $text="🧾 <b>فاکتور شماره ".self::fa((string)$id)."</b> — اشتراک {$plan['name']}\n\n"
            ."🆘 <b>مهم: مبلغ را دقیق بزنید، رند نکنید</b>\n\n"
            ."💰 <b>مبلغ قابل پرداخت:</b> <b>{$amountText}</b>\n\n"
            ."💳 <b>شماره کارت:</b> <code>{$cfg['card']}</code>\n"
            ."🏦 <b>بانک:</b> ".htmlspecialchars($cfg['bank'],ENT_QUOTES,'UTF-8')."\n"
            ."👤 <b>صاحب حساب:</b> ".htmlspecialchars($cfg['owner'],ENT_QUOTES,'UTF-8')."\n\n"
            ."❌ <b>واریز پل و پایا ممنوع است!</b>";

        $this->states->set($ctx->userId,'feature:receipt',[
            'phone_number'=>$user['phone_number'],
            'user_id'=>(int)$user['id'],
            'payment_id'=>$id
        ]);

        $ctx->reply($text,['reply_markup'=>Keyboard::inline([
            [Keyboard::copyTextButton('📋 کپی مبلغ', (string)$amount), Keyboard::copyTextButton('📋 کپی شماره کارت', $cfg['card'])],
            [Keyboard::button('📤 ارسال فیش واریزی','payment:receipt:'.$id)],
            [Keyboard::button('❌ انصراف','payment:cancel:'.$id)],
        ])]);
    }

    private function reviewPayment(Context $ctx,int $id,bool $approve): void
    {
        $payment=Db::fetchOne("SELECT * FROM payments WHERE id=? AND status='pending_review'",[$id]);
        if(!$payment){$ctx->answerCallback('این پرداخت قبلاً بررسی شده یا وجود ندارد.',true);return;}
        if($approve){
            $now=Clock::now();$current=Db::fetchOne("SELECT * FROM subscriptions WHERE user_id=? AND status='active' AND end_date>? ORDER BY end_date DESC LIMIT 1",[(int)$payment['user_id'],$now]);
            if($current){$end=gmdate('Y-m-d H:i:s',strtotime($current['end_date'].' UTC')+(int)$payment['duration_days']*86400);$rank=['free'=>0,'monthly'=>1,'six_months'=>2,'yearly'=>3];$type=(($rank[$payment['plan_type']]??0)>($rank[$current['type']]??0))?$payment['plan_type']:$current['type'];Db::execute('UPDATE subscriptions SET end_date=?, type=? WHERE id=?',[$end,$type,(int)$current['id']]);$subId=(int)$current['id'];}
            else {$end=gmdate('Y-m-d H:i:s',strtotime($now.' UTC')+(int)$payment['duration_days']*86400);$subId=Db::insert('INSERT INTO subscriptions (user_id,type,start_date,end_date,status,payment_id,created_at) VALUES (?,?,?,?,?,?,?)',[(int)$payment['user_id'],$payment['plan_type'],$now,$end,'active',$id,$now]);}
            Db::execute("UPDATE payments SET status='approved', reviewed_by=?, reviewed_at=?, subscription_id=? WHERE id=?",[$ctx->userId,$now,$subId,$id]);
            $result='✅ پرداخت شما تأیید شد و اشتراک فعال گردید.';
        } else {
            Db::execute("UPDATE payments SET status='rejected', reviewed_by=?, reviewed_at=? WHERE id=?",[$ctx->userId,Clock::now(),$id]);
            $result='❌ فیش پرداخت شما تأیید نشد. لطفاً با مدیر سامانه پیگیری کنید.';
        }
        try{$ctx->api->sendMessage((int)$payment['telegram_id'],$result);}catch(\Throwable){}
        $ctx->edit(($approve?'✅ پرداخت تأیید شد.':'❌ پرداخت رد شد.')."\nفاکتور: ".self::fa((string)$id));
    }

    private function redeemGiftCode(Context $ctx,array $data,string $code): void
    {
        $user=$this->user($ctx,$data);if(!$user){$ctx->reply(Texts::ACCOUNT_MISSING);return;}
        $code=strtoupper(preg_replace('/\s+/','',$code));
        $gift=Db::fetchOne('SELECT * FROM subscription_codes WHERE code=? AND active=1 AND used=0',[$code]);
        if(!$gift){$ctx->reply('❌ کد هدیه معتبر نیست، غیرفعال شده یا قبلاً استفاده شده است. دوباره تلاش کنید یا /cancel بفرستید.');return;}
        $now=Clock::now();$current=Db::fetchOne("SELECT * FROM subscriptions WHERE user_id=? AND status='active' AND end_date>? ORDER BY end_date DESC LIMIT 1",[(int)$user['id'],$now]);
        if($current){$end=gmdate('Y-m-d H:i:s',strtotime($current['end_date'].' UTC')+(int)$gift['duration_days']*86400);$rank=['free'=>0,'monthly'=>1,'six_months'=>2,'yearly'=>3];$type=($rank[$gift['type']]??0)>($rank[$current['type']]??0)?$gift['type']:$current['type'];Db::execute('UPDATE subscriptions SET end_date=?,type=? WHERE id=?',[$end,$type,(int)$current['id']]);}
        else {$end=gmdate('Y-m-d H:i:s',strtotime($now.' UTC')+(int)$gift['duration_days']*86400);Db::insert('INSERT INTO subscriptions (user_id,type,start_date,end_date,status,created_at) VALUES (?,?,?,?,?,?)',[(int)$user['id'],$gift['type'],$now,$end,'active',$now]);}
        Db::execute('UPDATE subscription_codes SET used=1,used_by_user_id=?,used_at=? WHERE id=? AND used=0',[(int)$user['id'],$now,(int)$gift['id']]);
        $this->states->set($ctx->userId,States::MAIN_MENU,['phone_number'=>$user['phone_number']]);
        $ctx->reply('🎉 کد هدیه با موفقیت ثبت شد و اشتراک شما تمدید گردید.',['reply_markup'=>Keyboards::mainMenu((string)$user['phone_number'])]);
    }

    private function showAdmin(Context $ctx): void
    {
        $ctx->reply('🔐 <b>پنل مدیریت بیهقی</b>\n\nیکی از گزینه‌های زیر را انتخاب کنید:', ['reply_markup'=>Keyboard::inline([
            [Keyboard::button('1️⃣ ساخت کد اشتراک','admin:create')],
            [Keyboard::button('2️⃣ کدهای اشتراک','admin:codes')],
            [Keyboard::button('3️⃣ مدیریت کاربران','admin:users')],
            [Keyboard::button('4️⃣ پرداخت‌های در انتظار','admin:pays')],
            [Keyboard::button('5️⃣ بازگشت به منوی اصلی','subscription:back_main')],
        ])]);
    }

    private function showCreateCodePlans(Context $ctx): void
    {
        $ctx->reply('🎟 <b>ساخت کد اشتراک</b>\n\nپلن موردنظر را انتخاب کنید:', ['reply_markup'=>Keyboard::inline([
            [Keyboard::button('📅 ماهیانه','admin:create:monthly')],
            [Keyboard::button('📆 ۶ ماهه','admin:create:six_months')],
            [Keyboard::button('🗓 سالیانه','admin:create:yearly')],
            [Keyboard::button('↩️ بازگشت به پنل مدیریت','admin:menu')],
        ])]);
    }

    private function createSubscriptionCode(Context $ctx,string $planKey): void
    {
        $plan=self::PLANS[$planKey] ?? null;
        if(!$plan){$ctx->reply('⚠️ پلن نامعتبر است.');return;}

        $code=$this->generateSubscriptionCode();
        Db::insert(
            'INSERT INTO subscription_codes (code,type,duration_days,active,used,created_at) VALUES (?,?,?,?,?,?)',
            [$code,$planKey,$plan['days'],1,0,Clock::now()]
        );

        $ctx->reply(
            "✅ <b>کد اشتراک با موفقیت ساخته شد.</b>\n\n"
            ."🎟 <b>کد:</b> <code>{$code}</code>\n"
            ."📌 <b>نوع:</b> {$plan['name']}\n"
            ."⏳ <b>مدت:</b> ".self::fa((string)$plan['days'])." روز\n\n"
            .'این کد را می‌توانید برای کاربر ارسال کنید.',
            ['reply_markup'=>Keyboard::inline([
                [Keyboard::copyTextButton('📋 کپی کد اشتراک',$code)],
                [Keyboard::button('🎟 کدهای اشتراک','admin:codes')],
                [Keyboard::button('↩️ پنل مدیریت','admin:menu')],
            ])]
        );
    }

    private function generateSubscriptionCode(): string
    {
        $alphabet='ABCDEFGHJKLMNPQRSTUVWXYZ23456789';
        for($attempt=0;$attempt<20;$attempt++){
            $parts=[];
            for($p=0;$p<3;$p++){
                $part='';
                for($i=0;$i<4;$i++) $part.=$alphabet[random_int(0,strlen($alphabet)-1)];
                $parts[]=$part;
            }
            $code='BM-'.implode('-',$parts);
            if(!Db::fetchOne('SELECT id FROM subscription_codes WHERE code=?',[$code])) return $code;
        }
        throw new \RuntimeException('ساخت کد اشتراک یکتا ناموفق بود.');
    }

    private function listCodes(Context $ctx,string $filter='all'): void
    {
        $where='';
        $params=[];
        $title='همه';
        switch($filter){
            case 'usable': $where='WHERE active=1 AND used=0'; $title='قابل استفاده'; break;
            case 'inactive': $where='WHERE active=0 AND used=0'; $title='غیرفعال'; break;
            case 'used': $where='WHERE used=1'; $title='استفاده شده'; break;
            default: $filter='all'; $title='همه';
        }

        $countRow=Db::fetchOne("SELECT COUNT(*) n FROM subscription_codes {$where}");
        $count=(int)($countRow['n']??0);
        $codes=Db::fetchAll("SELECT c.*,u.first_name,u.last_name,u.phone_number FROM subscription_codes c LEFT JOIN users u ON u.id=c.used_by_user_id {$where} ORDER BY c.id DESC LIMIT 20",$params);

        $text="📋 <b>کدهای اشتراک — {$title}</b>\nتعداد: ".self::fa((string)$count)."\n\n";
        if(!$codes){
            $text.='موردی در این بخش وجود ندارد.';
        }else{
            foreach($codes as $index=>$c){
                $type=self::subscriptionTypeName((string)$c['type']);
                if((int)$c['used']===1){
                    $status='🔴 استفاده شده';
                }elseif((int)$c['active']===1){
                    $status='🟢 قابل استفاده';
                }else{
                    $status='⚫️ غیرفعال';
                }
                $text.= '<b>'.self::fa((string)($index+1)).'.</b> <code>'.htmlspecialchars((string)$c['code'],ENT_QUOTES,'UTF-8')."</code>\n";
                $text.= "📌 <b>نوع:</b> {$type}\n";
                $text.= "⏳ <b>مدت:</b> ".self::fa((string)$c['duration_days'])." روز\n";
                $text.= "📅 <b>ایجاد:</b> ".self::dateJalali((string)$c['created_at'])."\n";
                $text.= "{$status}\n";
                if((int)$c['used']===1){
                    $text.= "🕒 <b>تاریخ استفاده:</b> ".self::dateJalali((string)$c['used_at'])."\n";
                    $name=trim((string)($c['first_name']??'').' '.(string)($c['last_name']??''));
                    if($name!=='') $text.= "👤 <b>استفاده‌کننده:</b> ".htmlspecialchars($name,ENT_QUOTES,'UTF-8')."\n";
                    if((string)($c['phone_number']??'')!=='') $text.= "📱 <b>موبایل:</b> ".htmlspecialchars((string)$c['phone_number'],ENT_QUOTES,'UTF-8')."\n";
                }
                $text.="\n";
            }
        }

        $rows=[
            [Keyboard::button('1️⃣ همه کدها','admin:codes:all'),Keyboard::button('2️⃣ قابل استفاده','admin:codes:usable')],
            [Keyboard::button('3️⃣ غیرفعال','admin:codes:inactive'),Keyboard::button('4️⃣ استفاده شده','admin:codes:used')],
            [Keyboard::button('5️⃣ بروزرسانی','admin:codes:refresh')],
            [Keyboard::button('6️⃣ بازگشت به پنل مدیریت','admin:menu')],
        ];
        $ctx->reply($text,['reply_markup'=>Keyboard::inline($rows)]);
    }

    private function showUserManagement(Context $ctx): void
    {
        $ctx->reply('👥 <b>مدیریت کاربران</b>\n\nیکی از گزینه‌های زیر را انتخاب کنید:', ['reply_markup'=>Keyboard::inline([
            [Keyboard::button('👤 لیست کاربران','admin:userlist:0')],
            [Keyboard::button('📱 جستجو با شماره موبایل','admin:usersearch')],
            [Keyboard::button('↩️ بازگشت به پنل مدیریت','admin:menu')],
        ])]);
    }

    private function listUsers(Context $ctx,int $page=0): void
    {
        $size=10;
        $page=max(0,$page);
        $total=(int)(Db::fetchOne('SELECT COUNT(*) n FROM users')['n']??0);
        $pages=max(1,(int)ceil($total/$size));
        $page=min($page,$pages-1);
        $users=Db::fetchAll('SELECT id,first_name,last_name,phone_number,status FROM users ORDER BY id DESC LIMIT '.$size.' OFFSET '.($page*$size));

        $text="👥 <b>لیست کاربران</b>\nتعداد کل: ".self::fa((string)$total)."\nصفحه ".self::fa((string)($page+1))." از ".self::fa((string)$pages)."\n\n";
        $rows=[];
        foreach($users as $u){
            $icon=$u['status']==='active'?'🟢':'🔴';
            $name=trim((string)$u['first_name'].' '.(string)$u['last_name']);
            $rows[]=[Keyboard::button($icon.' '.$name.' — '.$u['phone_number'],'admin:user:'.(int)$u['id'])];
        }
        if(!$users) $text.='کاربری ثبت نشده است.';
        $nav=[];
        if($page>0)$nav[]=Keyboard::button('⬅️ قبلی','admin:userlist:'.($page-1));
        if($page<$pages-1)$nav[]=Keyboard::button('بعدی ➡️','admin:userlist:'.($page+1));
        if($nav)$rows[]=$nav;
        $rows[]=[Keyboard::button('📱 جستجو با شماره موبایل','admin:usersearch')];
        $rows[]=[Keyboard::button('↩️ مدیریت کاربران','admin:users')];
        $ctx->reply($text,['reply_markup'=>Keyboard::inline($rows)]);
    }

    private function showUserDetails(Context $ctx,array $u): void
    {
        $active=$u['status']==='active';
        $status=$active?'🟢 فعال':'🔴 غیرفعال';
        $action=$active?'🔴 غیرفعال کردن':'🟢 فعال کردن';

        $name=htmlspecialchars(trim((string)$u['first_name'].' '.(string)$u['last_name']),ENT_QUOTES,'UTF-8');
        $phone=htmlspecialchars((string)$u['phone_number'],ENT_QUOTES,'UTF-8');
        $registered=self::dateJalali((string)($u['created_at']??''));
        $lastLogin=(!empty($u['last_login_at']))
            ? self::dateJalali((string)$u['last_login_at'])
            : 'هنوز وارد نشده است';

        // اشتراک فعال کاربر را نمایش می‌دهیم؛ اگر منقضی شده باشد، آخرین اشتراک را هم برای اطلاع مدیر نشان می‌دهیم.
        $sub=Db::fetchOne(
            'SELECT * FROM subscriptions WHERE user_id=? ORDER BY end_date DESC LIMIT 1',
            [(int)$u['id']]
        );

        $text="👤 <b>اطلاعات کاربر</b>\n\n"
            ."👤 <b>نام:</b> {$name} ( کاربر عادی )\n"
            ."📱 <b>موبایل:</b> {$phone}\n"
            ."📅 <b>ثبت‌نام:</b> {$registered}\n"
            ."🕒 <b>آخرین ورود:</b> {$lastLogin}\n"
            ."🔐 <b>وضعیت حساب:</b> {$status}\n";

        if($sub){
            $subscriptionActive=$sub['status']==='active' && (string)$sub['end_date']>Clock::now();
            $subStatus=$subscriptionActive?'🟢 فعال':'🔴 منقضی شده';
            // تغییر یافته: استفاده از تابع برای نام‌گذاری نوع اشتراک
            $type=self::subscriptionTypeName((string)$sub['type']);
            $start=self::dateJalali((string)$sub['start_date']);
            $end=self::dateJalali((string)$sub['end_date']);

            $text.="\n<b>💳 اشتراک</b>\n"
                ."📌 <b>وضعیت:</b> {$subStatus}\n"
                ."🏷 <b>نوع:</b> {$type}\n"
                ."📅 <b>شروع:</b> {$start}\n"
                ."📆 <b>پایان:</b> {$end}\n";

            if($subscriptionActive){
                // تغییر یافته: استفاده از تابع محاسبه دقیق زمان
                $text.="⏳ <b>باقی‌مانده:</b> " . self::formatRemainingTime((string)$sub['end_date']) . "\n";
            }else{
                $text.="⏳ <b>باقی‌مانده:</b> ۰ روز\n";
            }
        }else{
            $text.="\n<b>💳 اشتراک</b>\n"
                ."📌 <b>وضعیت:</b> 🔴 ندارد\n"
                ."🏷 <b>نوع:</b> —\n";
        }

        $ctx->reply($text,['reply_markup'=>Keyboard::inline([
            [Keyboard::button($action,'admin:usertoggle:'.(int)$u['id'])],
            [Keyboard::button('↩️ لیست کاربران','admin:userlist:0')],
            [Keyboard::button('↩️ مدیریت کاربران','admin:users')],
        ])]);
    }

    private function listPendingPayments(Context $ctx): void
    {
        $rows=Db::fetchAll("SELECT p.id,p.amount_rial,p.plan_type,p.created_at,u.first_name,u.last_name,u.phone_number FROM payments p JOIN users u ON u.id=p.user_id WHERE p.status='pending_review' ORDER BY p.receipt_sent_at,p.id LIMIT 20");
        $buttons=[];
        foreach($rows as $r) {
            $plan=self::PLANS[$r['plan_type']]['name']??$r['plan_type'];
            $buttons[]=[Keyboard::button('🧾 #'.self::fa((string)$r['id']).' — '.$r['first_name'].' '.$r['last_name'].' — '.self::money((int)$r['amount_rial']).' ریال','admin:pay:'.(int)$r['id'])];
        }
        $buttons[]=[Keyboard::button('↩️ پنل مدیریت','admin:menu')];
        $ctx->reply($rows?'🧾 <b>پرداخت‌های در انتظار بررسی</b>':'در حال حاضر پرداختی در انتظار بررسی نیست.',['reply_markup'=>Keyboard::inline($buttons)]);
    }

    private function openPendingPayment(Context $ctx,int $id): void
    {
        $p=Db::fetchOne("SELECT p.*,u.first_name,u.last_name,u.phone_number FROM payments p JOIN users u ON u.id=p.user_id WHERE p.id=? AND p.status='pending_review'",[$id]);
        if(!$p){$ctx->answerCallback('پرداخت در انتظار بررسی پیدا نشد.',true);return;}
        $plan=self::PLANS[$p['plan_type']]['name']??$p['plan_type'];
        $caption='🧾 <b>فیش واریزی — فاکتور '.self::fa((string)$id)."</b>\n"
            .'👤 کاربر: '.htmlspecialchars($p['first_name'].' '.$p['last_name'],ENT_QUOTES,'UTF-8')."\n"
            .'📱 موبایل: '.$p['phone_number']."\n"
            .'📦 اشتراک: '.$plan."\n"
            .'💰 مبلغ: '.self::money((int)$p['amount_rial']).' ریال';
        $keyboard=['reply_markup'=>Keyboard::inline([[Keyboard::button('✅ تأیید','pay:ok:'.$id),Keyboard::button('❌ رد','pay:no:'.$id)],[Keyboard::button('↩️ پرداخت‌های در انتظار','admin:pays')]])];
        if($p['receipt_kind']==='photo' && $p['receipt_file_id']) $ctx->api->sendPhoto($ctx->chatId,(string)$p['receipt_file_id'],$caption,$keyboard);
        elseif($p['receipt_kind']==='document' && $p['receipt_file_id']) $ctx->api->sendDocument($ctx->chatId,(string)$p['receipt_file_id'],$caption,$keyboard);
        else $ctx->reply($caption,$keyboard);
    }

    /**
     * تابع محاسبه زمان باقی‌مانده به صورت روز و ساعت.
     * زمان پایان در دیتابیس به UTC ذخیره شده است.
     */
    private static function formatRemainingTime(string $endDate): string
    {
        $seconds = strtotime($endDate . ' UTC') - time();
        
        if ($seconds <= 0) {
            return '۰ روز';
        }
        
        $days = (int) floor($seconds / 86400);
        $hours = (int) floor(($seconds % 86400) / 3600);
        
        $parts = [];
        if ($days > 0) $parts[] = self::fa((string)$days) . ' روز';
        if ($hours > 0) $parts[] = self::fa((string)$hours) . ' ساعت';
        
        if (empty($parts)) {
            return 'کمتر از ۱ ساعت';
        }
        
        return implode(' و ', $parts);
    }

    private static function money(int $value): string { return self::fa(str_replace(',', '٬', number_format($value))); }
    private static function fa(string $s): string { return strtr($s,['0'=>'۰','1'=>'۱','2'=>'۲','3'=>'۳','4'=>'۴','5'=>'۵','6'=>'۶','7'=>'۷','8'=>'۸','9'=>'۹']); }
}
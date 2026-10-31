# راهنمای نصب و راه‌اندازی نهایی (ویندوز)

این ربات با **Python + aiogram** نوشته شده و دیتابیس آن **PostgreSQL** است
(نشانی و نام دیتابیس در `DATABASE_URL` فایل `.env` است).

## ۱. پیش‌نیازها
- Python نصب‌شده و محیط مجازی `.venv` در پوشه پروژه
- سرویس **PostgreSQL** نصب و روشن (در Services ویندوز: `postgresql-x64-…` روی حالت Automatic)
- کامپیوتر همیشه روشن و متصل به اینترنت (برای اجرای دائمی)؛ در Power Options گزینه Sleep را روی Never بگذارید

## ۲. نصب وابستگی‌ها
در پوشه پروژه (با `.venv` فعال):
```
pip install -r requirements.txt
```

## ۳. تنظیم فایل `.env`
فایل `.env.example` را کپی کنید به `.env` و مقادیر را پر کنید
(توکن ربات، `DATABASE_URL`، `ADMIN_PHONE`، `ADMIN_TELEGRAM_ID`، مشخصات کارت).

## ۴. دیتابیس و Alembic (مدیریت تغییرات ساختار جدول‌ها)
از این مرحله، ربات خودش جدول نمی‌سازد؛ ساختار دیتابیس فقط با Alembic مدیریت می‌شود.

**الف) دیتابیس فعلی شما (که تا الان کار می‌کرده):** فقط یک‌بار این دستور را بزنید تا Alembic بداند
جدول‌ها از قبل وجود دارند:
```
alembic stamp head
```

**ب) نصب تازه روی دیتابیس خالی:** ابتدا یک دیتابیس خالی (مثلاً `beyhaghi_mezaj`) در pgAdmin بسازید، بعد:
```
alembic upgrade head
python seed_foods.py
```

**ج) هر زمان در آینده ساختار جدولی عوض شد (مثلاً ستون جدید):**
```
alembic revision --autogenerate -m "توضیح کوتاه"
alembic upgrade head
```

## ۵. بررسی سلامت تنظیمات
```
python -m scripts.check_setup
```
همه موارد باید ✅ باشند (هشدار Redis در ویندوز طبیعی است).

## ۶. اجرای آزمایشی
```
python main.py
```
با Ctrl+C متوقف می‌شود. قبل از اجرای دائمی، چک‌لیست `docs/CHECKLIST_FA.md` را یک‌بار کامل بزنید.

## ۷. اجرای دائمی (شروع خودکار با روشن شدن ویندوز + راه‌اندازی مجدد بعد از خطا)
PowerShell را با **Run as administrator** باز کنید، در پوشه پروژه:
```
powershell -ExecutionPolicy Bypass -File deploy\install_windows_tasks.ps1
```
این دستور دو وظیفه در Task Scheduler می‌سازد: اجرای دائمی ربات و بکاپ روزانه ساعت ۳ بامداد.

- اگر ربات با حساب SYSTEM بالا نیامد، با `-RunAsCurrentUser` دوباره نصب کنید
  (در این حالت ربات فقط پس از ورود شما به ویندوز اجرا می‌شود).
- وضعیت: `Get-ScheduledTask -TaskName BeyhaghiMezajBot`
- توقف/حذف: `powershell -ExecutionPolicy Bypass -File deploy\uninstall_windows_tasks.ps1`

## ۸. بکاپ دیتابیس
- خودکار: هر شب ساعت ۳ (آخرین ۱۴ بکاپ در پوشه `backups` می‌ماند).
- دستی: `python -m scripts.backup_db`
- حتماً هفته‌ای یک‌بار پوشه `backups` را روی یک دیسک یا فضای ابری دیگر کپی کنید.
- بازیابی (در صورت خرابی):
```
pg_restore -h localhost -U postgres -d beyhaghi_mezaj --clean --if-exists backups\نام-فایل.dump
```
اگر `pg_dump` پیدا نشد، پوشه `bin` نصب PostgreSQL (مثلاً `C:\Program Files\PostgreSQL\16\bin`) را به PATH اضافه کنید.

## ۹. به‌روزرسانی ربات با فایل‌های جدید
1. `powershell -ExecutionPolicy Bypass -File deploy\uninstall_windows_tasks.ps1` (یا توقف وظیفه)
2. بکاپ بگیرید: `python -m scripts.backup_db`
3. فایل‌های جدید را جایگزین کنید.
4. `pip install -r requirements.txt` و `alembic upgrade head`
5. دوباره `deploy\install_windows_tasks.ps1` را اجرا کنید.

## ۱۰. نکات مهم
- با هر ری‌استارت ربات، کاربران باید دوباره وارد حساب شوند (مگر Redis تنظیم شود).
- فایل `.env` (توکن و رمز دیتابیس) را به کسی ندهید و در zip برای دیگران نگذارید.
- اگر مجبورید تغییر مهمی در دیتابیس بدهید، قبلش بکاپ بگیرید.

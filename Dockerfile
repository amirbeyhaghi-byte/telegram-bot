FROM php:8.2-apache

# ۱) نصب پیش‌نیازهای سیستمی (libonig-dev برای mbstring ضروری است)
RUN apt-get update && apt-get install -y \
    libonig-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# ۲) نصب افزونه‌های PHP یکی‌یکی (کاهش مصرف رم)
RUN docker-php-ext-install -j1 pdo
RUN docker-php-ext-install -j1 pdo_mysql
RUN docker-php-ext-install -j1 mbstring

# ۳) کپی کردن کدهای پروژه
COPY . /var/www/html/

# ۴) تنظیم پوشه public به عنوان ریشه سایت
ENV APACHE_DOCUMENT_ROOT /var/www/html/public
RUN sed -ri -e 's!/var/www/html!${APACHE_DOCUMENT_ROOT}!g' /etc/apache2/sites-available/*.conf
RUN sed -ri -e 's!/var/www/!${APACHE_DOCUMENT_ROOT}!g' /etc/apache2/apache2.conf /etc/apache2/conf-available/*.conf

# ۵) فعال کردن mod_rewrite
RUN a2enmod rewrite
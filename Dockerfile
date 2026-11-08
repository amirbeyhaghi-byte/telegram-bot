FROM php:8.2-apache

# نصب افزونه‌های لازم برای MySQL و mbstring
RUN docker-php-ext-install pdo pdo_mysql mbstring

# کپی کردن کدها
COPY . /var/www/html/

# تنظیم DocumentRoot روی پوشه public
ENV APACHE_DOCUMENT_ROOT /var/www/html/public
RUN sed -ri -e 's!/var/www/html!${APACHE_DOCUMENT_ROOT}!g' /etc/apache2/sites-available/*.conf
RUN sed -ri -e 's!/var/www/!${APACHE_DOCUMENT_ROOT}!g' /etc/apache2/apache2.conf /etc/apache2/conf-available/*.conf

# فعال کردن mod_rewrite (در صورت نیاز)
RUN a2enmod rewrite
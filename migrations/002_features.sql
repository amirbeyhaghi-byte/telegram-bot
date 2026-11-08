-- قابلیت‌های منتقل‌شده از نسخه پایتون: اشتراک، خوراکی، کد هدیه و پرداخت
CREATE TABLE IF NOT EXISTS subscriptions (
 id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
 user_id BIGINT UNSIGNED NOT NULL,
 type VARCHAR(20) NOT NULL,
 start_date DATETIME NOT NULL,
 end_date DATETIME NOT NULL,
 status VARCHAR(20) NOT NULL DEFAULT 'active',
 payment_id BIGINT UNSIGNED NULL,
 created_at DATETIME NOT NULL,
 PRIMARY KEY(id), KEY ix_subscriptions_user_id(user_id),
 CONSTRAINT fk_subscriptions_user FOREIGN KEY(user_id) REFERENCES users(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS food_items (
 id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
 category VARCHAR(100) NOT NULL,
 name VARCHAR(150) NOT NULL,
 variety VARCHAR(150) NULL,
 temperament VARCHAR(50) NOT NULL,
 warmth VARCHAR(20) NOT NULL,
 moisture VARCHAR(20) NOT NULL,
 description VARCHAR(1000) NULL,
 active TINYINT(1) NOT NULL DEFAULT 1,
 PRIMARY KEY(id), KEY ix_food_category(category), KEY ix_food_name(name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS subscription_codes (
 id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
 code VARCHAR(100) NOT NULL UNIQUE,
 type VARCHAR(20) NOT NULL,
 duration_days INT NOT NULL,
 active TINYINT(1) NOT NULL DEFAULT 1,
 used TINYINT(1) NOT NULL DEFAULT 0,
 used_by_user_id BIGINT UNSIGNED NULL,
 used_at DATETIME NULL,
 created_at DATETIME NOT NULL,
 PRIMARY KEY(id), KEY ix_subscription_codes_active(active),
 CONSTRAINT fk_subscription_codes_user FOREIGN KEY(used_by_user_id) REFERENCES users(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS payments (
 id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
 user_id BIGINT UNSIGNED NOT NULL,
 telegram_id BIGINT NOT NULL,
 plan_type VARCHAR(20) NOT NULL,
 duration_days INT NOT NULL,
 amount_rial BIGINT NOT NULL,
 status VARCHAR(20) NOT NULL DEFAULT 'awaiting_receipt',
 receipt_file_id VARCHAR(255) NULL,
 receipt_kind VARCHAR(10) NULL,
 receipt_sent_at DATETIME NULL,
 reviewed_by BIGINT NULL,
 reviewed_at DATETIME NULL,
 subscription_id BIGINT UNSIGNED NULL,
 created_at DATETIME NOT NULL,
 PRIMARY KEY(id), KEY ix_payments_user_id(user_id), KEY ix_payments_status(status),
 CONSTRAINT fk_payments_user FOREIGN KEY(user_id) REFERENCES users(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

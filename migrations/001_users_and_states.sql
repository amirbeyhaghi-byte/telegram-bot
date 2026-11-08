-- جدول کاربران (معادل جدول users نسخه پایتون)
CREATE TABLE IF NOT EXISTS users (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    phone_number VARCHAR(20) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    created_at DATETIME NOT NULL,
    last_login_at DATETIME NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'active',
    PRIMARY KEY (id),
    UNIQUE KEY ix_users_phone_number (phone_number)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- وضعیت گفتگو (چون وب‌هوک بدون حافظه است، وضعیت هر کاربر اینجا نگه‌داری می‌شود)
CREATE TABLE IF NOT EXISTS user_states (
    telegram_id BIGINT NOT NULL,
    state VARCHAR(64) NULL,
    data MEDIUMTEXT NULL,
    updated_at DATETIME NOT NULL,
    PRIMARY KEY (telegram_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

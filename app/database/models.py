from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
)

from app.utils import utcnow


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )

    first_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    last_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    phone_number: Mapped[str] = mapped_column(
        String(20),
        unique=True,
        nullable=False,
        index=True,
    )

    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utcnow,
        nullable=False,
    )

    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        default="active",
        nullable=False,
    )


class Subscription(Base):
    __tablename__ = "subscriptions"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    start_date: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
    )

    end_date: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    payment_id: Mapped[int | None] = mapped_column(
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utcnow,
        nullable=False,
    )


class TemperamentQuestion(Base):
    __tablename__ = "temperament_questions"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )

    question: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )

    order: Mapped[int] = mapped_column(
        nullable=False,
    )

    active: Mapped[bool] = mapped_column(
        default=True,
        nullable=False,
    )


class TemperamentAnswer(Base):
    __tablename__ = "temperament_answers"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )

    question_id: Mapped[int] = mapped_column(
        ForeignKey("temperament_questions.id"),
        nullable=False,
        index=True,
    )

    answer: Mapped[str] = mapped_column(
        String(300),
        nullable=False,
    )

    score_warm: Mapped[int] = mapped_column(
        default=0,
        nullable=False,
    )

    score_cold: Mapped[int] = mapped_column(
        default=0,
        nullable=False,
    )

    score_dry: Mapped[int] = mapped_column(
        default=0,
        nullable=False,
    )

    score_wet: Mapped[int] = mapped_column(
        default=0,
        nullable=False,
    )


class FoodItem(Base):
    __tablename__ = "food_items"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )

    category: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
        index=True,
    )

    variety: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True,
    )

    temperament: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    warmth: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    moisture: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    description: Mapped[str | None] = mapped_column(
        String(1000),
        nullable=True,
    )

    active: Mapped[bool] = mapped_column(
        default=True,
        nullable=False,
    )


class SubscriptionCode(Base):
    __tablename__ = "subscription_codes"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )

    code: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
        index=True,
    )

    type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    duration_days: Mapped[int] = mapped_column(
        nullable=False,
    )

    active: Mapped[bool] = mapped_column(
        default=True,
        nullable=False,
    )

    used: Mapped[bool] = mapped_column(
        default=False,
        nullable=False,
    )

    used_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"),
        nullable=True,
    )

    used_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utcnow,
        nullable=False,
    )


class Payment(Base):
    """فاکتور / پرداخت کارت‌به‌کارت (با تأیید دستی مدیر)."""

    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    # شناسه تلگرام کاربر هنگام صدور فاکتور (برای اطلاع‌رسانی نتیجه)
    telegram_id: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )

    plan_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    duration_days: Mapped[int] = mapped_column(
        nullable=False,
    )

    amount_rial: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )

    # awaiting_receipt / pending_review / approved / rejected / cancelled
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="awaiting_receipt",
        index=True,
    )

    receipt_file_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    # photo / document
    receipt_kind: Mapped[str | None] = mapped_column(
        String(10),
        nullable=True,
    )

    receipt_sent_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    reviewed_by: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
    )

    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    subscription_id: Mapped[int | None] = mapped_column(
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utcnow,
        nullable=False,
    )

"""حذف جدول قدیمی و بلااستفاده user_subscriptions

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-22

این جدول از مدل قدیمی UserSubscription باقی مانده بود (مدل در مرحله ۰ حذف شد
و هیچ بخشی از ربات از آن استفاده نمی‌کند). اگر جدول ردیف داشته باشد، حذف
انجام نمی‌شود و خطا می‌دهد تا داده‌ای از بین نرود.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()

    # روی دیتابیس تازه این جدول اصلاً وجود ندارد؛ در آن صورت کاری لازم نیست
    if not sa.inspect(bind).has_table("user_subscriptions"):
        return

    rows = bind.execute(
        sa.text("select count(*) from user_subscriptions")
    ).scalar_one()

    if rows:
        raise RuntimeError(
            f"جدول user_subscriptions خالی نیست ({rows} ردیف)؛ برای جلوگیری "
            "از از بین رفتن داده، حذف انجام نشد."
        )

    # ایندکس‌های جدول همراه خود جدول حذف می‌شوند
    op.drop_table("user_subscriptions")


def downgrade() -> None:
    op.create_table(
        "user_subscriptions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("plan_type", sa.String(length=20), nullable=False),
        sa.Column("start_date", sa.DateTime(), nullable=False),
        sa.Column("end_date", sa.DateTime(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_user_subscriptions_user_id"),
        "user_subscriptions",
        ["user_id"],
        unique=False,
    )

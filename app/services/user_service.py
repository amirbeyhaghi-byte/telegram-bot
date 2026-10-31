from pwdlib import PasswordHash
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import User
from app.utils import normalize_phone


password_hasher = PasswordHash.recommended()


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(
    password: str,
    password_hash: str,
) -> bool:
    return password_hasher.verify(
        password,
        password_hash,
    )


async def get_user_by_phone(
    session: AsyncSession,
    phone_number: str,
) -> User | None:
    phone = normalize_phone(phone_number)

    result = await session.execute(
        select(User).where(
            User.phone_number == phone
        )
    )

    return result.scalar_one_or_none()


async def create_user(
    session: AsyncSession,
    first_name: str,
    last_name: str,
    phone_number: str,
    password: str,
) -> User:
    phone = normalize_phone(phone_number)

    user = User(
        first_name=first_name,
        last_name=last_name,
        phone_number=phone,
        password_hash=hash_password(password),
        status="active",
    )

    session.add(user)

    await session.flush()

    return user
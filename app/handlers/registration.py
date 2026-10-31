import logging

from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from sqlalchemy import select

from app.database.database import AsyncSessionLocal
from app.database.models import User
from app.keyboards.main import main_menu_keyboard
from app.keyboards.registration import (
    login_keyboard,
    phone_keyboard,
    registration_keyboard,
)
from app.services.subscription_service import create_free_subscription
from app.services.user_service import (
    create_user,
    get_user_by_phone,
    normalize_phone,
    verify_password,
)
from app.states.main import MainStates
from app.services.validation import (
    is_valid_phone,
    validate_name,
    validate_password,
)
from app.states.registration import LoginStates, RegistrationStates
from app.utils import utcnow


router = Router()

logger = logging.getLogger(__name__)


def contact_belongs_to_sender(message: Message) -> bool:
    """
    شماره‌ای که با دکمه «ارسال شماره» می‌آید فقط وقتی معتبر است که
    تلگرام تأیید کرده باشد متعلق به همین فرستنده است.
    (مخاطب فوروارد‌شده یا شماره دیگران همیشه user_id متفاوت دارد.)
    """
    contact = message.contact

    return (
        contact is not None
        and message.from_user is not None
        and contact.user_id == message.from_user.id
    )


async def delete_quietly(message: Message) -> None:
    """پیام حاوی رمز عبور را از چت پاک می‌کند (در صورت خطا نادیده گرفته می‌شود)."""
    try:
        await message.delete()
    except Exception:  # noqa: BLE001
        pass


# =========================
# ثبت نام
# =========================

@router.message(lambda message: message.text == "📝 ثبت‌نام")
async def start_registration(
    message: Message,
    state: FSMContext,
):
    await state.set_state(RegistrationStates.first_name)

    await message.answer(
        "📝 <b>ثبت‌نام در سامانه</b>\n\n"
        "لطفاً نام خود را وارد کنید:",
        parse_mode="HTML",
    )


@router.message(RegistrationStates.first_name)
async def registration_first_name(
    message: Message,
    state: FSMContext,
):
    first_name, error = validate_name(message.text)

    if error:
        await message.answer(error)
        return

    await state.update_data(
        first_name=first_name
    )

    await state.set_state(
        RegistrationStates.last_name
    )

    await message.answer(
        "لطفاً نام خانوادگی خود را وارد کنید:"
    )


@router.message(RegistrationStates.last_name)
async def registration_last_name(
    message: Message,
    state: FSMContext,
):
    last_name, error = validate_name(message.text)

    if error:
        await message.answer(error)
        return

    await state.update_data(
        last_name=last_name
    )

    await state.set_state(
        RegistrationStates.phone_number
    )

    await message.answer(
        "📱 لطفاً شماره موبایل خود را با استفاده از "
        "دکمه زیر ارسال کنید.\n\n"
        "⚠️ شماره باید متعلق به خود شما باشد.",
        reply_markup=phone_keyboard(),
    )


@router.message(RegistrationStates.phone_number)
async def registration_phone_number(
    message: Message,
    state: FSMContext,
):
    if message.contact is None:
        await message.answer(
            "⚠️ لطفاً شماره موبایل خود را فقط با "
            "دکمه «📱 ارسال شماره موبایل» ارسال کنید.",
            reply_markup=phone_keyboard(),
        )
        return

    if not contact_belongs_to_sender(message):
        logger.warning(
            "Registration with foreign contact telegram_id=%s",
            message.from_user.id if message.from_user else None,
        )

        await message.answer(
            "⛔ این شماره متعلق به حساب تلگرام شما نیست.\n\n"
            "ثبت‌نام فقط با شماره موبایل همین حساب تلگرام ممکن است.",
            reply_markup=phone_keyboard(),
        )
        return

    phone_number = normalize_phone(
        message.contact.phone_number
    )

    if not is_valid_phone(phone_number):
        await message.answer(
            "⚠️ شماره موبایل معتبر نیست.",
            reply_markup=phone_keyboard(),
        )
        return

    await state.update_data(
        phone_number=phone_number
    )

    async with AsyncSessionLocal() as session:
        existing_user = await get_user_by_phone(
            session,
            phone_number,
        )

    if existing_user is not None:
        await message.answer(
            "⚠️ این شماره موبایل قبلاً در سامانه ثبت شده است.\n\n"
            "لطفاً از گزینه «🔐 ورود به حساب» استفاده کنید.",
            reply_markup=login_keyboard(),
        )

        await state.clear()
        return

    await state.set_state(
        RegistrationStates.password
    )

    await message.answer(
        "🔐 لطفاً یک رمز عبور برای حساب خود انتخاب کنید:"
    )


@router.message(RegistrationStates.password)
async def registration_password(
    message: Message,
    state: FSMContext,
):
    password = (message.text or "").strip()

    await delete_quietly(message)

    if not password:
        await message.answer(
            "⚠️ لطفاً رمز عبور را وارد کنید."
        )
        return

    data = await state.get_data()

    password_error = validate_password(
        password,
        data.get("phone_number"),
    )

    if password_error:
        await message.answer(password_error)
        return

    first_name = data.get("first_name")
    last_name = data.get("last_name")
    phone_number = data.get("phone_number")

    if not first_name or not last_name or not phone_number:
        await state.clear()

        await message.answer(
            "⚠️ اطلاعات ثبت‌نام کامل نیست.\n\n"
            "لطفاً دوباره ثبت‌نام را شروع کنید.",
            reply_markup=registration_keyboard(),
        )
        return

    async with AsyncSessionLocal() as session:
        existing_user = await get_user_by_phone(
            session,
            phone_number,
        )

        if existing_user is not None:
            await state.clear()

            await message.answer(
                "⚠️ این شماره موبایل قبلاً ثبت شده است.",
                reply_markup=login_keyboard(),
            )
            return

        user = await create_user(
            session=session,
            first_name=first_name,
            last_name=last_name,
            phone_number=phone_number,
            password=password,
        )

        free_subscription = await create_free_subscription(
            session=session,
            user_id=user.id,
        )

        await session.commit()

        saved_phone = user.phone_number

    await state.clear()

    await state.update_data(
        phone_number=saved_phone
    )

    await state.set_state(
        MainStates.menu
    )

    await message.answer(
        "<b>🎉 ثبت‌نام با موفقیت انجام شد.</b>\n\n"
        "🎁 یک ماه اشتراک رایگان برای شما فعال شد.\n\n"
        "اکنون می‌توانید از خدمات سامانه استفاده کنید.",
        parse_mode="HTML",
        reply_markup=main_menu_keyboard(
            saved_phone
        ),
    )


# =========================
# ورود
# =========================

@router.message(lambda message: message.text == "🔐 ورود به حساب")
async def start_login(
    message: Message,
    state: FSMContext,
):
    await state.set_state(
        LoginStates.phone_number
    )

    await message.answer(
        "🔐 <b>ورود به حساب</b>\n\n"
        "برای امنیت حساب شما، ورود فقط با شماره موبایلِ "
        "همین حساب تلگرام ممکن است.\n\n"
        "لطفاً با دکمه زیر شماره خود را ارسال کنید.\n"
        "برای انصراف /start را بزنید.",
        parse_mode="HTML",
        reply_markup=phone_keyboard(),
    )


@router.message(LoginStates.phone_number)
async def login_phone_number(
    message: Message,
    state: FSMContext,
):
    if message.contact is None:
        await message.answer(
            "⚠️ لطفاً شماره موبایل خود را فقط با "
            "دکمه «📱 ارسال شماره موبایل» ارسال کنید.",
            reply_markup=phone_keyboard(),
        )
        return

    if not contact_belongs_to_sender(message):
        logger.warning(
            "Login with foreign contact telegram_id=%s",
            message.from_user.id if message.from_user else None,
        )

        await message.answer(
            "⛔ این شماره متعلق به حساب تلگرام شما نیست.\n\n"
            "ورود فقط با شماره موبایل همین حساب تلگرام امکان‌پذیر است.",
            reply_markup=phone_keyboard(),
        )
        return

    phone_number = normalize_phone(
        message.contact.phone_number
    )

    async with AsyncSessionLocal() as session:
        user = await get_user_by_phone(
            session,
            phone_number,
        )

    if user is None:
        await message.answer(
            "❌ حسابی با این شماره موبایل پیدا نشد.\n\n"
            "لطفاً ابتدا ثبت‌نام کنید.",
            reply_markup=registration_keyboard(),
        )

        await state.clear()
        return

    await state.update_data(
        phone_number=user.phone_number
    )

    await state.set_state(
        LoginStates.password
    )

    await message.answer(
        "🔐 لطفاً رمز عبور خود را وارد کنید:"
    )


@router.message(LoginStates.password)
async def login_password(
    message: Message,
    state: FSMContext,
):
    password = (message.text or "").strip()

    await delete_quietly(message)

    if not password:
        await message.answer(
            "⚠️ لطفاً رمز عبور را وارد کنید."
        )
        return

    data = await state.get_data()

    phone_number = data.get(
        "phone_number"
    )

    if not phone_number:
        await state.clear()

        await message.answer(
            "⚠️ اطلاعات ورود پیدا نشد.\n\n"
            "لطفاً دوباره وارد حساب شوید.",
            reply_markup=registration_keyboard(),
        )
        return

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).where(
                User.phone_number == phone_number
            )
        )

        user = result.scalar_one_or_none()

        if user is None:
            await state.clear()

            await message.answer(
                "❌ کاربر پیدا نشد.",
                reply_markup=registration_keyboard(),
            )
            return

        if not verify_password(
            password,
            user.password_hash,
        ):
            await message.answer(
                "❌ رمز عبور اشتباه است.\n\n"
                "لطفاً دوباره رمز عبور را وارد کنید."
            )
            return

        if user.status != "active":
            await state.clear()

            await message.answer(
                "⛔ <b>حساب کاربری شما غیرفعال شده است.</b>\n\n"
                "برای پیگیری با مدیر سامانه تماس بگیرید.",
                parse_mode="HTML",
                reply_markup=registration_keyboard(),
            )
            return

        user.last_login_at = utcnow()

        await session.commit()

        saved_phone = user.phone_number

    await state.clear()

    await state.update_data(
        phone_number=saved_phone
    )

    await state.set_state(
        MainStates.menu
    )

    await message.answer(
        "<b>✅ ورود با موفقیت انجام شد.</b>\n\n"
        "لطفاً خدمت موردنظر خود را انتخاب کنید.",
        parse_mode="HTML",
        reply_markup=main_menu_keyboard(
            saved_phone
        ),
    )
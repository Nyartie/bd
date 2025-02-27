import asyncio
import logging
import re
from typing import Optional, Dict, Any

import bcrypt
from aiogram import Bot, Dispatcher, types, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.storage.memory import MemoryStorage

from config import Config
from database import Database
from queries import SQL
from utils import (
    generate_rental_report,
    generate_analytics_chart,
    cleanup_temp_files,
    validate_phone_number,
    format_rental_details,
    format_currency
)

# Инициализация логгера
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Инициализация бота
bot = Bot(
    token=Config.SECRET_KEY,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher(storage=MemoryStorage())
db = Database()


# Состояния FSM
class RegistrationStates(StatesGroup):
    email = State()
    password = State()
    phone = State()


class RentalStates(StatesGroup):
    select_size = State()
    confirm_rental = State()


class ReturnStates(StatesGroup):
    select_rental = State()


# ------------------------ Клавиатуры ------------------------
def main_menu_kb() -> types.ReplyKeyboardMarkup:
    """Главное меню"""
    builder = ReplyKeyboardBuilder()
    builder.row(
        types.KeyboardButton(text="🏒 Арендовать"),
        types.KeyboardButton(text="📋 Мои аренды")
    )
    builder.row(
        types.KeyboardButton(text="📊 Отчеты"),
        types.KeyboardButton(text="🛠 Поддержка")
    )
    return builder.as_markup(resize_keyboard=True)


def sizes_keyboard(sizes: list) -> types.InlineKeyboardMarkup:
    """Клавиатура с размерами"""
    builder = InlineKeyboardBuilder()
    for size in sizes:
        builder.button(text=str(size['size']), callback_data=f"size_{size['size']}")
    builder.adjust(4)
    return builder.as_markup()


# ------------------------ Хэндлеры ------------------------
@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    """Обработка команды /start"""
    await state.clear()
    user = await db.get_user_by_tg_id(message.from_user.id)

    if user:
        await message.answer(
            "👋 С возвращением!\n"
            "Используйте кнопки ниже для работы с системой:",
            reply_markup=main_menu_kb()
        )
        return

    await message.answer(
        "🎉 Добро пожаловать в систему аренды коньков!\n"
        "Для начала работы пройдите регистрацию.\n"
        "Введите ваш email:"
    )
    await state.set_state(RegistrationStates.email)


@dp.message(RegistrationStates.email)
async def process_email(message: types.Message, state: FSMContext):
    """Обработка email при регистрации"""
    email = message.text.strip().lower()

    if not re.match(r"^[\w\.-]+@[\w\.-]+\.\w+$", email):
        await message.answer("❌ Неверный формат email! Попробуйте снова:")
        return

    if await db.fetchrow(SQL.CHECK_EMAIL_EXISTS, email):
        await message.answer("❌ Этот email уже зарегистрирован! Введите другой:")
        return

    await state.update_data(email=email)
    await message.answer("🔒 Введите пароль (минимум 6 символов):")
    await state.set_state(RegistrationStates.password)


@dp.message(RegistrationStates.password)
async def process_password(message: types.Message, state: FSMContext):
    password = message.text.strip()

    if len(password) < 6:
        await message.answer("❌ Пароль слишком короткий! Минимум 6 символов:")
        return

    await state.update_data(password=password)
    await message.answer("📱 Введите ваш телефон в формате +79991234567:")
    await state.set_state(RegistrationStates.phone)


@dp.message(RegistrationStates.phone)
async def process_phone(message: types.Message, state: FSMContext):
    phone = message.text.strip()

    if not validate_phone_number(phone):
        await message.answer("❌ Неверный формат телефона! Попробуйте снова:")
        return

    data = await state.get_data()
    hashed_pwd = bcrypt.hashpw(data['password'].encode(), bcrypt.gensalt()).decode()

    try:
        await db.execute(
            SQL.REGISTER_USER,
            message.from_user.id,
            data['email'],
            phone,
            hashed_pwd,
            message.from_user.full_name
        )
        await message.answer(
            "✅ Регистрация успешно завершена!\n"
            "Используйте кнопки ниже для работы с системой:",
            reply_markup=main_menu_kb()
        )
    except Exception as e:
        logger.error(f"Registration error: {e}")
        await message.answer("⚠️ Произошла ошибка при регистрации. Попробуйте позже.")

    await state.clear()


@dp.message(F.text == "🏒 Арендовать")
async def start_rental_process(message: types.Message, state: FSMContext):
    sizes = await db.fetch(SQL.GET_AVAILABLE_SIZES)

    if not sizes:
        await message.answer("😔 В данный момент нет доступных коньков.")
        return

    await message.answer("👇 Выберите размер коньков:",
                         reply_markup=sizes_keyboard(sizes))
    await state.set_state(RentalStates.select_size)


@dp.callback_query(RentalStates.select_size, F.data.startswith("size_"))
async def process_size_selection(callback: types.CallbackQuery, state: FSMContext):
    size = int(callback.data.split("_")[1])
    inventory = await db.fetch(SQL.GET_AVAILABLE_INVENTORY, size)

    if not inventory:
        await callback.message.edit_text("😔 Этот размер временно отсутствует.")
        await state.clear()
        return

    await state.update_data(size_id=inventory[0]['size_id'])
    await callback.message.edit_text(
        f"🔍 Найден доступный инвентарь:\n"
        f"• Модель: {inventory[0]['brand']} {inventory[0]['model_name']}\n"
        f"• Размер: {size}\n\n"
        f"Подтверждаете аренду?",
        reply_markup=InlineKeyboardBuilder()
        .button(text="✅ Подтвердить", callback_data="confirm")
        .button(text="❌ Отмена", callback_data="cancel")
        .as_markup()
    )
    await state.set_state(RentalStates.confirm_rental)


@dp.callback_query(RentalStates.confirm_rental, F.data == "confirm")
async def confirm_rental(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    user = await db.get_user_by_tg_id(callback.from_user.id)

    try:
        rental_id = await db.execute(
            SQL.CREATE_RENTAL,
            user['id'],
            data['size_id'],
            Config.DEFAULT_HOURLY_RATE
        )
        await callback.message.edit_text(
            "🎉 Аренда успешно оформлена!\n"
            f"Стоимость: {Config.DEFAULT_HOURLY_RATE}/час",
            reply_markup=main_menu_kb()
        )
        await log_action(user['id'], 'rent_start', f"Rental #{rental_id}")
    except Exception as e:
        logger.error(f"Rental error: {e}")
        await callback.message.answer("⚠️ Ошибка оформления аренды.")

    await state.clear()


@dp.message(F.text == "📋 Мои аренды")
async def show_active_rentals(message: types.Message):
    user = await db.get_user_by_tg_id(message.from_user.id)
    rentals = await db.fetch(SQL.GET_ACTIVE_RENTALS, user['id'])

    if not rentals:
        await message.answer("У вас нет активных аренд.")
        return

    response = ["🔷 Активные аренды:\n"]
    for idx, rent in enumerate(rentals, 1):
        response.append(
            f"{idx}. {rent['brand']} {rent['size']}\n"
            f"   Начало: {rent['start_time'].strftime('%d.%m %H:%M')}\n"
            f"   Стоимость: {format_currency(rent.get('total_cost', 0))}"
        )

    await message.answer("\n".join(response),
                         reply_markup=InlineKeyboardBuilder()
                         .button(text="↩️ Вернуть коньки", callback_data="return_skates")
                         .as_markup()
                         )


@dp.message(F.text == "📊 Отчеты")
async def generate_reports(message: types.Message):
    try:
        # CSV отчет
        csv_report = await generate_rental_report(message.from_user.id)
        await message.answer_document(
            types.BufferedInputFile(csv_report.read(), "rental_report.csv"),
            caption="📊 Отчет по арендам"
        )

        # График
        chart = await generate_analytics_chart()
        await message.answer_photo(
            types.BufferedInputFile(chart.read(), "popularity_chart.png"),
            caption="📈 Популярность размеров"
        )

        # Очистка
        csv_report.close()
        chart.close()
        await cleanup_temp_files()

    except Exception as e:
        logger.error(f"Report generation error: {e}")
        await message.answer("⚠️ Ошибка генерации отчета.")


# ------------------------ Системные функции ------------------------
async def log_action(user_id: int, action_type: str, details: str):
    await db.execute(
        SQL.LOG_ACTION,
        user_id,
        action_type,
        details
    )


async def on_startup():
    await db.connect()  # Подключаемся к БД
    logger.info("Database initialized")
    await cleanup_temp_files()


async def on_shutdown():
    await db.close()  # Закрываем соединения
    logger.info("Database connection closed")


async def main():
    await on_startup()  # Явно вызываем on_startup
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

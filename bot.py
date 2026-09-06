import asyncio
import logging
import os
import sqlite3
from datetime import datetime

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import KeyboardButton, Message, ReplyKeyboardMarkup, ReplyKeyboardRemove

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
DB_PATH = os.getenv("DB_PATH", "bot.db")

logging.basicConfig(level=logging.INFO)
router = Router()


class PhysicsRequest(StatesGroup):
    goal = State()
    grade = State()
    level = State()
    budget = State()
    schedule = State()
    contact = State()


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            username TEXT,
            goal TEXT NOT NULL,
            grade TEXT NOT NULL,
            level TEXT NOT NULL,
            budget TEXT NOT NULL,
            schedule TEXT NOT NULL,
            contact TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Новая',
            created_at TEXT NOT NULL
        )
    """)
    conn.commit()
    return conn


def save_request(message: Message, data: dict) -> int:
    conn = get_db()
    cur = conn.execute("""
        INSERT INTO requests
        (user_id, username, goal, grade, level, budget, schedule, contact, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        message.from_user.id,
        message.from_user.username,
        data["goal"], data["grade"], data["level"],
        data["budget"], data["schedule"], data["contact"],
        datetime.now().isoformat(timespec="seconds")
    ))
    request_id = cur.lastrowid
    conn.commit()
    conn.close()
    return request_id


def main_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="👨‍🏫 Найти преподавателя")],
            [KeyboardButton(text="📌 Моя заявка"), KeyboardButton(text="ℹ️ О боте")],
        ],
        resize_keyboard=True
    )


@router.message(CommandStart())
async def start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "👋 Привет! Я ProfiPhysicsBot.\n\n"
        "Помогу оформить заявку на поиск преподавателя физики. "
        "Задам несколько вопросов и передам заявку ответственному человеку.",
        reply_markup=main_menu()
    )


@router.message(F.text == "ℹ️ О боте")
async def about(message: Message):
    await message.answer(
        "⚡ <b>ProfiPhysicsBot</b>\n\n"
        "Бот собирает параметры ученика и помогает подобрать преподавателя "
        "по цели, классу, уровню, бюджету и расписанию.\n\n"
        "Команда /cancel отменяет текущую заявку."
    )


@router.message(F.text == "👨‍🏫 Найти преподавателя")
async def begin(message: Message, state: FSMContext):
    await state.set_state(PhysicsRequest.goal)
    await message.answer(
        "Шаг 1/6. Какая главная цель?\n\n"
        "Например: ЕГЭ, ОГЭ, олимпиада, повышение школьной успеваемости "
        "или поступление.",
        reply_markup=ReplyKeyboardRemove()
    )


@router.message(PhysicsRequest.goal)
async def goal(message: Message, state: FSMContext):
    text = (message.text or "").strip()
    if len(text) < 3:
        await message.answer("Напишите цель подробнее, например: подготовка к ЕГЭ.")
        return
    await state.update_data(goal=text)
    await state.set_state(PhysicsRequest.grade)
    await message.answer("Шаг 2/6. Какой класс или возраст ученика?")


@router.message(PhysicsRequest.grade)
async def grade(message: Message, state: FSMContext):
    text = (message.text or "").strip()
    if len(text) < 1:
        await message.answer("Укажите класс или возраст.")
        return
    await state.update_data(grade=text)
    await state.set_state(PhysicsRequest.level)
    await message.answer(
        "Шаг 3/6. Как оцените текущий уровень?\n\n"
        "Например: начальный, средний, сильный, олимпиадный."
    )


@router.message(PhysicsRequest.level)
async def level(message: Message, state: FSMContext):
    text = (message.text or "").strip()
    if len(text) < 2:
        await message.answer("Опишите текущий уровень в нескольких словах.")
        return
    await state.update_data(level=text)
    await state.set_state(PhysicsRequest.budget)
    await message.answer(
        "Шаг 4/6. Какой бюджет за одно занятие?\n"
        "Например: до 2 500 ₽ или 3 000–4 000 ₽."
    )


@router.message(PhysicsRequest.budget)
async def budget(message: Message, state: FSMContext):
    text = (message.text or "").strip()
    if len(text) < 2:
        await message.answer("Укажите бюджет текстом.")
        return
    await state.update_data(budget=text)
    await state.set_state(PhysicsRequest.schedule)
    await message.answer(
        "Шаг 5/6. Когда удобно заниматься?\n"
        "Например: будни после 18:00, выходные или гибкий график."
    )


@router.message(PhysicsRequest.schedule)
async def schedule(message: Message, state: FSMContext):
    text = (message.text or "").strip()
    if len(text) < 2:
        await message.answer("Напишите удобные дни или время.")
        return
    await state.update_data(schedule=text)
    await state.set_state(PhysicsRequest.contact)
    await message.answer(
        "Шаг 6/6. Оставьте контакт для связи: @username или телефон."
    )


@router.message(PhysicsRequest.contact)
async def contact(message: Message, state: FSMContext, bot: Bot):
    text = (message.text or "").strip()
    if len(text) < 3:
        await message.answer("Контакт выглядит слишком коротким. Попробуйте ещё раз.")
        return

    await state.update_data(contact=text)
    data = await state.get_data()
    request_id = save_request(message, data)
    await state.clear()

    await message.answer(
        f"✅ Заявка №{request_id} принята!\n\n"
        "Я сохранил параметры и передал заявку ответственному человеку. "
        "С вами свяжутся по указанному контакту.",
        reply_markup=main_menu()
    )

    if ADMIN_ID:
        username = f"@{message.from_user.username}" if message.from_user.username else "не указан"
        await bot.send_message(
            ADMIN_ID,
            f"🔔 <b>Новая заявка №{request_id}</b>\n\n"
            f"Пользователь: {username}\n"
            f"ID: <code>{message.from_user.id}</code>\n\n"
            f"Цель: {data['goal']}\n"
            f"Класс/возраст: {data['grade']}\n"
            f"Уровень: {data['level']}\n"
            f"Бюджет: {data['budget']}\n"
            f"Расписание: {data['schedule']}\n"
            f"Контакт: {data['contact']}"
        )


@router.message(F.text == "📌 Моя заявка")
async def my_request(message: Message):
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM requests WHERE user_id = ? ORDER BY id DESC LIMIT 1",
        (message.from_user.id,)
    ).fetchone()
    conn.close()

    if not row:
        await message.answer("У вас пока нет заявок.")
        return

    await message.answer(
        f"📌 <b>Последняя заявка №{row['id']}</b>\n\n"
        f"Цель: {row['goal']}\n"
        f"Класс/возраст: {row['grade']}\n"
        f"Уровень: {row['level']}\n"
        f"Бюджет: {row['budget']}\n"
        f"Расписание: {row['schedule']}\n"
        f"Статус: {row['status']}"
    )


def is_admin(message: Message):
    return ADMIN_ID and message.from_user.id == ADMIN_ID


@router.message(Command("admin"))
async def admin(message: Message):
    if not is_admin(message):
        await message.answer("⛔ Доступ запрещён.")
        return

    conn = get_db()
    total = conn.execute("SELECT COUNT(*) FROM requests").fetchone()[0]
    new = conn.execute("SELECT COUNT(*) FROM requests WHERE status='Новая'").fetchone()[0]
    rows = conn.execute(
        "SELECT id, goal, grade, created_at FROM requests ORDER BY id DESC LIMIT 5"
    ).fetchall()
    conn.close()

    text = f"🛠 <b>Админ-панель ProfiPhysicsBot</b>\n\nВсего заявок: {total}\nНовых: {new}\n\n"
    if rows:
        text += "\n".join(
            f"№{r['id']} — {r['goal']} — {r['grade']} — {r['created_at']}"
            for r in rows
        )
    await message.answer(text)


@router.message(Command("cancel"))
async def cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Заявка отменена.", reply_markup=main_menu())


@router.message()
async def fallback(message: Message):
    await message.answer(
        "Выберите действие в меню или нажмите /start.",
        reply_markup=main_menu()
    )


async def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is not set")

    get_db().close()
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher()
    dp.include_router(router)

    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())

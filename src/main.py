import os
import asyncio
import sqlite3
from datetime import datetime

from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from aiogram.filters import Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

if not TOKEN:
    raise ValueError("TOKEN не найден в .env")

bot = Bot(token=TOKEN)
dp = Dispatcher()

DB_NAME = "orders.db"


# =========================
# БАЗА ДАННЫХ
# =========================
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            username TEXT,
            customer_name TEXT NOT NULL,
            phone TEXT NOT NULL,
            address TEXT NOT NULL,
            product TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            comment TEXT,
            status TEXT NOT NULL DEFAULT 'new',
            created_at TEXT NOT NULL
        )
    """)

    conn.commit()
    conn.close()


def create_order(
    user_id: int,
    username: str,
    customer_name: str,
    phone: str,
    address: str,
    product: str,
    quantity: int,
    comment: str,
):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO orders (
            user_id, username, customer_name, phone, address,
            product, quantity, comment, status, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'new', ?)
    """, (
        user_id,
        username,
        customer_name,
        phone,
        address,
        product,
        quantity,
        comment,
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    ))

    order_id = cur.lastrowid
    conn.commit()
    conn.close()
    return order_id


def get_user_orders(user_id: int):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    cur.execute("""
        SELECT id, product, quantity, status, created_at
        FROM orders
        WHERE user_id = ?
        ORDER BY id DESC
    """, (user_id,))
    rows = cur.fetchall()

    conn.close()
    return rows


def get_all_orders():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    cur.execute("""
        SELECT id, user_id, username, customer_name, phone, address,
               product, quantity, comment, status, created_at
        FROM orders
        ORDER BY id DESC
    """)
    rows = cur.fetchall()

    conn.close()
    return rows


def get_order_by_id(order_id: int):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    cur.execute("""
        SELECT id, user_id, username, customer_name, phone, address,
               product, quantity, comment, status, created_at
        FROM orders
        WHERE id = ?
    """, (order_id,))
    row = cur.fetchone()

    conn.close()
    return row


def update_order_status(order_id: int, new_status: str):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    cur.execute("""
        UPDATE orders
        SET status = ?
        WHERE id = ?
    """, (new_status, order_id))

    conn.commit()
    conn.close()


# =========================
# FSM СОСТОЯНИЯ
# =========================
class OrderForm(StatesGroup):
    customer_name = State()
    phone = State()
    address = State()
    product = State()
    quantity = State()
    comment = State()


# =========================
# КНОПКИ
# =========================
def admin_order_keyboard(order_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ В работу", callback_data=f"status:{order_id}:in_progress"),
            InlineKeyboardButton(text="✔️ Выполнен", callback_data=f"status:{order_id}:done"),
        ],
        [
            InlineKeyboardButton(text="❌ Отменен", callback_data=f"status:{order_id}:cancelled"),
        ]
    ])


# =========================
# ОБЩИЕ КОМАНДЫ
# =========================
@dp.message(Command("start"))
async def start(message: Message):
    text = (
        "Привет! Я бот для оформления заказов.\n\n"
        "Команды:\n"
        "/new_order — оформить новый заказ\n"
        "/my_orders — мои заказы\n"
    )

    if message.from_user.id == ADMIN_ID:
        text += "/orders — все заказы (для администратора)\n"

    await message.answer(text)


@dp.message(Command("new_order"))
async def new_order(message: Message, state: FSMContext):
    await state.set_state(OrderForm.customer_name)
    await message.answer("Введите ваше имя:")


@dp.message(Command("my_orders"))
async def my_orders(message: Message):
    orders = get_user_orders(message.from_user.id)

    if not orders:
        await message.answer("У вас пока нет заказов.")
        return

    lines = ["Ваши заказы:\n"]
    for order_id, product, quantity, status, created_at in orders:
        lines.append(
            f"Заказ #{order_id}\n"
            f"Товар: {product}\n"
            f"Количество: {quantity}\n"
            f"Статус: {status}\n"
            f"Создан: {created_at}\n"
        )

    await message.answer("\n".join(lines))


# =========================
# FSM: ОФОРМЛЕНИЕ ЗАКАЗА
# =========================
@dp.message(OrderForm.customer_name)
async def order_name(message: Message, state: FSMContext):
    await state.update_data(customer_name=message.text.strip())
    await state.set_state(OrderForm.phone)
    await message.answer("Введите номер телефона:")


@dp.message(OrderForm.phone)
async def order_phone(message: Message, state: FSMContext):
    await state.update_data(phone=message.text.strip())
    await state.set_state(OrderForm.address)
    await message.answer("Введите адрес доставки:")


@dp.message(OrderForm.address)
async def order_address(message: Message, state: FSMContext):
    await state.update_data(address=message.text.strip())
    await state.set_state(OrderForm.product)
    await message.answer("Введите название товара/услуги:")


@dp.message(OrderForm.product)
async def order_product(message: Message, state: FSMContext):
    await state.update_data(product=message.text.strip())
    await state.set_state(OrderForm.quantity)
    await message.answer("Введите количество:")


@dp.message(OrderForm.quantity)
async def order_quantity(message: Message, state: FSMContext):
    text = message.text.strip()

    if not text.isdigit() or int(text) <= 0:
        await message.answer("Количество должно быть положительным числом. Введите еще раз:")
        return

    await state.update_data(quantity=int(text))
    await state.set_state(OrderForm.comment)
    await message.answer("Комментарий к заказу. Если нет — напишите '-'.")


@dp.message(OrderForm.comment)
async def order_comment(message: Message, state: FSMContext):
    comment = message.text.strip()
    if comment == "-":
        comment = ""

    await state.update_data(comment=comment)
    data = await state.get_data()

    order_id = create_order(
        user_id=message.from_user.id,
        username=message.from_user.username or "",
        customer_name=data["customer_name"],
        phone=data["phone"],
        address=data["address"],
        product=data["product"],
        quantity=data["quantity"],
        comment=data["comment"],
    )

    await state.clear()

    await message.answer(
        f"Спасибо! Ваш заказ #{order_id} создан.\n"
        f"Товар: {data['product']}\n"
        f"Количество: {data['quantity']}\n"
        f"Статус: new"
    )

    if ADMIN_ID:
        admin_text = (
            f"Новый заказ #{order_id}\n\n"
            f"Клиент: {data['customer_name']}\n"
            f"Username: @{message.from_user.username or 'нет'}\n"
            f"User ID: {message.from_user.id}\n"
            f"Телефон: {data['phone']}\n"
            f"Адрес: {data['address']}\n"
            f"Товар: {data['product']}\n"
            f"Количество: {data['quantity']}\n"
            f"Комментарий: {data['comment'] or 'нет'}\n"
            f"Статус: new"
        )

        await bot.send_message(
            ADMIN_ID,
            admin_text,
            reply_markup=admin_order_keyboard(order_id)
        )


# =========================
# АДМИН-КОМАНДЫ
# =========================
@dp.message(Command("orders"))
async def orders(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("У вас нет доступа к этой команде.")
        return

    rows = get_all_orders()

    if not rows:
        await message.answer("Заказов пока нет.")
        return

    for row in rows[:20]:
        order_id, user_id, username, customer_name, phone, address, product, quantity, comment, status, created_at = row

        text = (
            f"Заказ #{order_id}\n"
            f"Клиент: {customer_name}\n"
            f"Username: @{username or 'нет'}\n"
            f"User ID: {user_id}\n"
            f"Телефон: {phone}\n"
            f"Адрес: {address}\n"
            f"Товар: {product}\n"
            f"Количество: {quantity}\n"
            f"Комментарий: {comment or 'нет'}\n"
            f"Статус: {status}\n"
            f"Создан: {created_at}"
        )

        await message.answer(text, reply_markup=admin_order_keyboard(order_id))


@dp.callback_query(F.data.startswith("status:"))
async def change_status(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("Нет доступа", show_alert=True)
        return

    _, order_id_str, new_status = callback.data.split(":")
    order_id = int(order_id_str)

    order = get_order_by_id(order_id)
    if not order:
        await callback.answer("Заказ не найден", show_alert=True)
        return

    update_order_status(order_id, new_status)

    order = get_order_by_id(order_id)
    _, user_id, username, customer_name, phone, address, product, quantity, comment, status, created_at = order

    text = (
        f"Заказ #{order_id}\n"
        f"Клиент: {customer_name}\n"
        f"Username: @{username or 'нет'}\n"
        f"User ID: {user_id}\n"
        f"Телефон: {phone}\n"
        f"Адрес: {address}\n"
        f"Товар: {product}\n"
        f"Количество: {quantity}\n"
        f"Комментарий: {comment or 'нет'}\n"
        f"Статус: {status}\n"
        f"Создан: {created_at}"
    )

    await callback.message.edit_text(text, reply_markup=admin_order_keyboard(order_id))
    await callback.answer("Статус обновлен")

    try:
        await bot.send_message(
            user_id,
            f"Статус вашего заказа #{order_id} изменен: {status}"
        )
    except Exception:
        pass


# =========================
# ЗАПУСК
# =========================
async def main():
    init_db()
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
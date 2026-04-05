#version: 3.0
import os
import json
import base64
import logging
from uuid import uuid4
from typing import Dict, List

from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message,
    Update,
    CallbackQuery,
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from aiogram.filters import Command


BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set")

if not WEBHOOK_SECRET:
    raise RuntimeError("WEBHOOK_SECRET is not set")


logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ==========
# DEMO STORAGE
# Для реального продакшена замени на БД:
# YDB / PostgreSQL / Redis
# ==========
DRAFTS: Dict[int, List[str]] = {}
ORDERS: Dict[str, dict] = {}

# ==========
# MENU
# ==========
MENU = {
    "pizza_margherita": {"name": "Пицца Маргарита", "price": 450},
    "pizza_pepperoni": {"name": "Пицца Пепперони", "price": 520},
    "burger_beef": {"name": "Бургер с говядиной", "price": 390},
    "shawarma_chicken": {"name": "Шаурма с курицей", "price": 280},
    "cola": {"name": "Кола", "price": 120},
    "fries": {"name": "Картофель фри", "price": 170},
}

STATUS_INACTIVE = "неактивно"
STATUS_ACTIVE = "активно"
STATUS_DONE = "выполнено"


def main_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Меню"), KeyboardButton(text="Мой черновик")],
            [KeyboardButton(text="Открытые заказы"), KeyboardButton(text="Мои заказы")],
        ],
        resize_keyboard=True,
        input_field_placeholder="Выбери действие",
    )


def dishes_keyboard() -> InlineKeyboardMarkup:
    rows = []
    for dish_id, item in MENU.items():
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{item['name']} — {item['price']}₽",
                    callback_data=f"add:{dish_id}",
                )
            ]
        )

    rows.append(
        [
            InlineKeyboardButton(text="Показать черновик", callback_data="draft:show"),
            InlineKeyboardButton(text="Оформить заказ", callback_data="draft:create"),
        ]
    )
    rows.append(
        [InlineKeyboardButton(text="Очистить черновик", callback_data="draft:clear")]
    )

    return InlineKeyboardMarkup(inline_keyboard=rows)


def order_action_keyboard(order: dict, viewer_user_id: int) -> InlineKeyboardMarkup:
    buttons = []

    if order["status"] == STATUS_INACTIVE:
        buttons.append(
            [InlineKeyboardButton(text="Взять заказ", callback_data=f"order:pick:{order['id']}")]
        )

    if order["status"] == STATUS_ACTIVE and order.get("assigned_to") == viewer_user_id:
        buttons.append(
            [InlineKeyboardButton(text="Завершить заказ", callback_data=f"order:done:{order['id']}")]
        )

    buttons.append(
        [InlineKeyboardButton(text="Обновить список", callback_data="orders:open")]
    )

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_user_display(message_or_callback) -> str:
    user = message_or_callback.from_user
    if user.username:
        return f"@{user.username}"
    full_name = (user.full_name or "").strip()
    return full_name or str(user.id)


def calc_total(items: List[str]) -> int:
    return sum(MENU[item_id]["price"] for item_id in items)


def format_draft(user_id: int) -> str:
    items = DRAFTS.get(user_id, [])
    if not items:
        return "Черновик пуст."

    lines = ["Твой черновик заказа:"]
    for idx, item_id in enumerate(items, start=1):
        item = MENU[item_id]
        lines.append(f"{idx}. {item['name']} — {item['price']}₽")

    lines.append("")
    lines.append(f"Итого: {calc_total(items)}₽")
    return "\n".join(lines)


def format_order(order: dict) -> str:
    lines = [
        f"Заказ #{order['id']}",
        f"Статус: {order['status']}",
        f"Клиент: {order['created_by_name']}",
    ]

    if order.get("assigned_to_name"):
        lines.append(f"Исполнитель: {order['assigned_to_name']}")

    lines.append("")
    lines.append("Состав заказа:")
    for idx, item_id in enumerate(order["items"], start=1):
        item = MENU[item_id]
        lines.append(f"{idx}. {item['name']} — {item['price']}₽")

    lines.append("")
    lines.append(f"Итого: {calc_total(order['items'])}₽")
    return "\n".join(lines)


def make_response(status_code: int, payload: dict) -> dict:
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(payload, ensure_ascii=False),
    }


def extract_json_body(event: dict) -> dict:
    raw_body = event.get("body") or "{}"
    if event.get("isBase64Encoded"):
        raw_body = base64.b64decode(raw_body).decode("utf-8")
    return json.loads(raw_body)


# ==========
# COMMANDS / TEXT BUTTONS
# ==========
@dp.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer(
        "Привет! Я бот для управления заказами.\n\n"
        "Что я умею:\n"
        "• показать меню блюд\n"
        "• собрать заказ\n"
        "• создать заказ со статусом 'неактивно'\n"
        "• дать исполнителю взять заказ → статус 'активно'\n"
        "• завершить заказ → статус 'выполнено'",
        reply_markup=main_menu_keyboard(),
    )


@dp.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "Команды:\n"
        "/start — старт\n"
        "/help — помощь\n"
        "/menu — меню блюд\n"
        "/draft — показать черновик\n"
        "/orders — открытые заказы\n"
        "/myorders — мои заказы",
        reply_markup=main_menu_keyboard(),
    )


@dp.message(Command("menu"))
@dp.message(F.text == "Меню")
async def show_menu(message: Message):
    await message.answer(
        "Выбери блюда для заказа:",
        reply_markup=dishes_keyboard(),
    )


@dp.message(Command("draft"))
@dp.message(F.text == "Мой черновик")
async def show_draft(message: Message):
    await message.answer(
        format_draft(message.from_user.id),
        reply_markup=main_menu_keyboard(),
    )


@dp.message(Command("orders"))
@dp.message(F.text == "Открытые заказы")
async def show_open_orders(message: Message):
    open_orders = [
        order for order in ORDERS.values()
        if order["status"] in (STATUS_INACTIVE, STATUS_ACTIVE)
    ]

    if not open_orders:
        await message.answer("Открытых заказов нет.", reply_markup=main_menu_keyboard())
        return

    for order in open_orders:
        await message.answer(
            format_order(order),
            reply_markup=order_action_keyboard(order, message.from_user.id),
        )


@dp.message(Command("myorders"))
@dp.message(F.text == "Мои заказы")
async def show_my_orders(message: Message):
    user_id = message.from_user.id

    user_orders = [
        order for order in ORDERS.values()
        if order["created_by"] == user_id or order.get("assigned_to") == user_id
    ]

    if not user_orders:
        await message.answer("У тебя пока нет заказов.", reply_markup=main_menu_keyboard())
        return

    for order in user_orders:
        await message.answer(
            format_order(order),
            reply_markup=order_action_keyboard(order, user_id),
        )


# ==========
# CALLBACKS
# ==========
@dp.callback_query(F.data.startswith("add:"))
async def cb_add_dish(callback: CallbackQuery):
    dish_id = callback.data.split(":", 1)[1]
    if dish_id not in MENU:
        await callback.answer("Блюдо не найдено", show_alert=True)
        return

    user_id = callback.from_user.id
    DRAFTS.setdefault(user_id, []).append(dish_id)

    item = MENU[dish_id]
    await callback.answer(f"Добавлено: {item['name']}")


@dp.callback_query(F.data == "draft:show")
async def cb_show_draft(callback: CallbackQuery):
    await callback.message.answer(
        format_draft(callback.from_user.id),
        reply_markup=main_menu_keyboard(),
    )
    await callback.answer()


@dp.callback_query(F.data == "draft:clear")
async def cb_clear_draft(callback: CallbackQuery):
    DRAFTS[callback.from_user.id] = []
    await callback.answer("Черновик очищен")
    await callback.message.answer("Черновик очищен.", reply_markup=main_menu_keyboard())


@dp.callback_query(F.data == "draft:create")
async def cb_create_order(callback: CallbackQuery):
    user_id = callback.from_user.id
    items = DRAFTS.get(user_id, [])

    if not items:
        await callback.answer("Черновик пуст", show_alert=True)
        return

    order_id = uuid4().hex[:8]
    order = {
        "id": order_id,
        "items": items[:],
        "status": STATUS_INACTIVE,
        "created_by": user_id,
        "created_by_name": get_user_display(callback),
        "assigned_to": None,
        "assigned_to_name": None,
    }
    ORDERS[order_id] = order
    DRAFTS[user_id] = []

    await callback.answer("Заказ создан")
    await callback.message.answer(
        "Заказ создан.\n\n" + format_order(order),
        reply_markup=order_action_keyboard(order, callback.from_user.id),
    )


@dp.callback_query(F.data == "orders:open")
async def cb_refresh_open_orders(callback: CallbackQuery):
    open_orders = [
        order for order in ORDERS.values()
        if order["status"] in (STATUS_INACTIVE, STATUS_ACTIVE)
    ]

    if not open_orders:
        await callback.message.answer("Открытых заказов нет.")
        await callback.answer()
        return

    for order in open_orders:
        await callback.message.answer(
            format_order(order),
            reply_markup=order_action_keyboard(order, callback.from_user.id),
        )
    await callback.answer()


@dp.callback_query(F.data.startswith("order:pick:"))
async def cb_pick_order(callback: CallbackQuery):
    order_id = callback.data.split(":")[2]
    order = ORDERS.get(order_id)

    if not order:
        await callback.answer("Заказ не найден", show_alert=True)
        return

    if order["status"] != STATUS_INACTIVE:
        await callback.answer("Заказ уже взят или завершён", show_alert=True)
        return

    order["status"] = STATUS_ACTIVE
    order["assigned_to"] = callback.from_user.id
    order["assigned_to_name"] = get_user_display(callback)

    await callback.answer("Заказ взят в работу")
    await callback.message.answer(
        "Статус обновлён.\n\n" + format_order(order),
        reply_markup=order_action_keyboard(order, callback.from_user.id),
    )


@dp.callback_query(F.data.startswith("order:done:"))
async def cb_done_order(callback: CallbackQuery):
    order_id = callback.data.split(":")[2]
    order = ORDERS.get(order_id)

    if not order:
        await callback.answer("Заказ не найден", show_alert=True)
        return

    if order["status"] != STATUS_ACTIVE:
        await callback.answer("Заказ не активен", show_alert=True)
        return

    if order.get("assigned_to") != callback.from_user.id:
        await callback.answer("Завершить может только тот, кто взял заказ", show_alert=True)
        return

    order["status"] = STATUS_DONE

    await callback.answer("Заказ завершён")
    await callback.message.answer(
        "Заказ выполнен.\n\n" + format_order(order),
        reply_markup=main_menu_keyboard(),
    )


@dp.message(F.text)
async def fallback_text(message: Message):
    await message.answer(
        "Я не понял команду.\nНажми 'Меню' или используй /help",
        reply_markup=main_menu_keyboard(),
    )


async def handler(event: dict, context):
    headers = event.get("headers") or {}
    headers = {str(k).lower(): v for k, v in headers.items()}

    secret = headers.get("x-telegram-bot-api-secret-token")
    if secret != WEBHOOK_SECRET:
        return make_response(403, {"ok": False, "error": "forbidden"})

    try:
        update_data = extract_json_body(event)
        update = Update.model_validate(update_data, context={"bot": bot})
        await dp.feed_update(bot, update)
        return make_response(200, {"ok": True})
    except Exception as e:
        logging.exception("Webhook processing failed")
        return make_response(500, {"ok": False, "error": str(e)})

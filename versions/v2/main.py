#version: 2.0
import os
import json
import base64
import logging

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, Update, ReplyKeyboardMarkup, KeyboardButton
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


def main_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Ping"), KeyboardButton(text="Help")],
        ],
        resize_keyboard=True,
        input_field_placeholder="Напиши сообщение или нажми кнопку",
    )


def make_response(status_code: int, payload: dict) -> dict:
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
        },
        "body": json.dumps(payload, ensure_ascii=False),
    }


def extract_json_body(event: dict) -> dict:
    raw_body = event.get("body") or "{}"

    if event.get("isBase64Encoded"):
        raw_body = base64.b64decode(raw_body).decode("utf-8")

    return json.loads(raw_body)


@dp.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer(
        "Привет! Я бот в Yandex Cloud Function 🚀\n\n"
        "Доступные команды:\n"
        "/start — старт\n"
        "/help — помощь\n"
        "/ping — проверка",
        reply_markup=main_keyboard(),
    )


@dp.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "Я работаю через webhook.\n\n"
        "Что умею:\n"
        "/start — показать приветствие\n"
        "/help — показать помощь\n"
        "/ping — ответить pong\n\n"
        "Можно ещё просто написать любой текст.",
        reply_markup=main_keyboard(),
    )


@dp.message(Command("ping"))
async def cmd_ping(message: Message):
    await message.answer("pong", reply_markup=main_keyboard())


@dp.message(F.text.casefold() == "ping")
async def btn_ping(message: Message):
    await message.answer("pong", reply_markup=main_keyboard())


@dp.message(F.text.casefold() == "help")
async def btn_help(message: Message):
    await message.answer(
        "Нажми:\n"
        "/start — старт\n"
        "/help — помощь\n"
        "/ping — проверка",
        reply_markup=main_keyboard(),
    )


@dp.message(F.text)
async def echo_text(message: Message):
    await message.answer(f"Ты написал: {message.text}", reply_markup=main_keyboard())


@dp.message()
async def fallback_message(message: Message):
    await message.answer(
        "Я пока умею отвечать только на текстовые сообщения.",
        reply_markup=main_keyboard(),
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
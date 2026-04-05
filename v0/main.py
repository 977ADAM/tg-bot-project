# version: 0
import os
import json
import base64

from aiogram import Bot, Dispatcher
from aiogram.types import Message, Update
from aiogram.filters import Command


BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set")

if not WEBHOOK_SECRET:
    raise RuntimeError("WEBHOOK_SECRET is not set")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


@dp.message(Command("start"))
async def handle_start(message: Message):
    await message.answer("Привет!")


@dp.message()
async def echo_message(message: Message):
    if message.text:
        await message.answer(f"Ты написал: {message.text}")
    else:
        await message.answer("Я пока отвечаю только на текстовые сообщения.")


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
        return make_response(500, {"ok": False, "error": str(e)})
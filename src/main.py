import os
import json
import base64
import requests

BOT_TOKEN = os.environ["BOT_TOKEN"]
WEBHOOK_SECRET = os.environ["WEBHOOK_SECRET"]
TG_API = f"https://api.telegram.org/bot{BOT_TOKEN}"


def response(status_code: int, payload: dict):
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json"
        },
        "body": json.dumps(payload, ensure_ascii=False)
    }


def send_message(chat_id: int, text: str):
    r = requests.post(
        f"{TG_API}/sendMessage",
        json={"chat_id": chat_id, "text": text},
        timeout=10,
    )
    r.raise_for_status()


def handler(event, context):
    headers = event.get("headers") or {}
    headers = {str(k).lower(): v for k, v in headers.items()}

    secret = headers.get("x-telegram-bot-api-secret-token")
    if secret != WEBHOOK_SECRET:
        return response(403, {"ok": False, "error": "forbidden"})

    raw_body = event.get("body") or "{}"
    if event.get("isBase64Encoded"):
        raw_body = base64.b64decode(raw_body).decode("utf-8")

    update = json.loads(raw_body)

    message = update.get("message") or {}
    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    text = (message.get("text") or "").strip()

    if not chat_id:
        return response(200, {"ok": True})

    if text == "/start":
        answer = "Привет! Бот на Yandex Cloud Function работает 🚀"
    else:
        answer = f"Ты написал: {text}"

    send_message(chat_id, answer)
    return response(200, {"ok": True})
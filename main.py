from flask import Flask, request
import requests
import json
from utils import load_json, save_json

# Завантаження конфігурації
with open("config.json") as f:
    config = json.load(f)

BOT_TOKEN = config["bot_token"]
ADMIN_CHAT_ID = config["admin_chat_id"]
DEFAULT_WM = config.get("default_wm", "2594")
API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"
CAPI_URL = "https://capi-production-1013.up.railway.app"  # Твій CAPI endpoint

app = Flask(__name__)

# Завантаження всіх JSON
users = load_json("users.json")
leads = load_json("leads.json")
offers = load_json("offers.json")
user_links = load_json("user_links.json")
messages = load_json("messages.json")
pixels = load_json("pixels.json")


def send_message(chat_id, text, reply_markup=None):
    data = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    if reply_markup:
        data["reply_markup"] = json.dumps(reply_markup)
    res = requests.post(f"{API_URL}/sendMessage", json=data)
    if res.ok:
        msg_id = res.json()["result"]["message_id"]
        messages.setdefault(str(chat_id), []).append(msg_id)
        save_json("messages.json", messages)
        return msg_id
    return None


def delete_bot_messages(chat_id):
    for msg_id in messages.get(str(chat_id), []):
        requests.post(f"{API_URL}/deleteMessage", json={"chat_id": chat_id, "message_id": msg_id})
    messages[str(chat_id)] = []
    save_json("messages.json", messages)


def delete_user_message(chat_id, message_id):
    requests.post(f"{API_URL}/deleteMessage", json={"chat_id": chat_id, "message_id": message_id})


def get_keyboard(is_admin=False):
    buttons = [
        [{"text": "📦 Оффери"}, {"text": "🔗 Мої посилання"}],
        [{"text": "📊 Статистика"}, {"text": "🌐 Мова"}],
        [{"text": "🎯 Мої пікселі"}]
    ]
    if is_admin:
        buttons.append([{"text": "⚙️ Адмін"}])
    return {"keyboard": buttons, "resize_keyboard": True}


@app.route("/webhook", methods=["POST"])
def webhook():
    update = request.get_json()
    message = update.get("message")
    if not message:
        return "ok"

    chat_id = message["chat"]["id"]
    user_id = str(chat_id)
    msg_id = message["message_id"]
    text = message.get("text", "")
    is_admin = chat_id == ADMIN_CHAT_ID

    delete_user_message(chat_id, msg_id)
    delete_bot_messages(chat_id)

    if user_id not in users:
        users[user_id] = {
            "wm": user_id[-4:],
            "username": message["chat"].get("username", ""),
            "first_name": message["chat"].get("first_name", ""),
            "state": None
        }
        save_json("users.json", users)

    wm = users[user_id]["wm"]

    if text == "/start" or text == "🔙 Назад":
        users[user_id]["state"] = None
        users[user_id].pop("temp_pixel", None)
        save_json("users.json", users)
        welcome = (
            f"👋 Привіт, {message['chat'].get('first_name', '')}!\n\n"
            "Ти підключений до панелі заливу 📲\n\n"
            "Цей бот:\n"
            "🔗 — видає твоє унікальне посилання\n"
            "📊 — показує статистику лідів\n"
            "📥 — сповіщає про нові заявки\n"
            "🎯 — керування Pixel ID\n"
            "⚙️ — доступ до адмінки (лише для боса)\n\n"
            "👇 Обери команду нижче:"
        )
        send_message(chat_id, welcome, get_keyboard(is_admin))
        return "ok"

    if text == "🎯 Мої пікселі":
        users[user_id]["state"] = None
        save_json("users.json", users)
        menu = {
            "keyboard": [
                [{"text": "➕ Додати Pixel"}, {"text": "❌ Видалити Pixel"}],
                [{"text": "🔙 Назад"}]
            ],
            "resize_keyboard": True
        }
        send_message(chat_id, "🎯 Обери дію з Pixel:", menu)
        return "ok"

    if text == "➕ Додати Pixel":
        users[user_id]["state"] = "awaiting_pixel"
        save_json("users.json", users)
        send_message(chat_id, "📝 Введи <b>Pixel ID</b> (15–16 цифр):", {"keyboard": [[{"text": "🔙 Назад"}]]})
        return "ok"

    if users[user_id].get("state") == "awaiting_pixel":
        if not text.isdigit():
            send_message(chat_id, "❌ Некоректний Pixel ID", {"keyboard": [[{"text": "🔙 Назад"}]]})
            return "ok"
        users[user_id]["temp_pixel"] = text
        users[user_id]["state"] = "awaiting_token"
        save_json("users.json", users)
        send_message(chat_id, "🔐 Введи Access Token для цього Pixel:", {"keyboard": [[{"text": "🔙 Назад"}]]})
        return "ok"

    if users[user_id].get("state") == "awaiting_token":
        pixel_id = users[user_id]["temp_pixel"]
        token = text
        try:
            res = requests.post(f"{CAPI_URL}/add_pixel", json={"wm": wm, "pixel_id": pixel_id, "access_token": token})
            if res.status_code == 200:
                send_message(chat_id, f"✅ Pixel <code>{pixel_id}</code> додано до CAPI.")
            else:
                send_message(chat_id, f"⚠️ Помилка CAPI: {res.text}")
        except Exception as e:
            send_message(chat_id, f"🚫 Не вдалося надіслати в CAPI: {e}")
        users[user_id]["state"] = None
        users[user_id].pop("temp_pixel", None)
        save_json("users.json", users)
        return "ok"

    if text == "❌ Видалити Pixel":
        users[user_id]["state"] = "awaiting_remove_pixel"
        save_json("users.json", users)
        send_message(chat_id, "📝 Введи Pixel ID, який хочеш видалити:", {"keyboard": [[{"text": "🔙 Назад"}]]})
        return "ok"

    if users[user_id].get("state") == "awaiting_remove_pixel":
        try:
            res = requests.post(f"{CAPI_URL}/remove_pixel", json={"wm": wm, "pixel_id": text})
            if res.status_code == 200:
                send_message(chat_id, f"🗑️ Pixel <code>{text}</code> видалено з CAPI.")
            else:
                send_message(chat_id, f"❌ CAPI помилка: {res.text}")
        except Exception as e:
            send_message(chat_id, f"🚫 Видалення не вдалося: {e}")
        users[user_id]["state"] = None
        save_json("users.json", users)
        return "ok"

    # решта логіки: оффери, статистика, мова, адмінка...
    return "ok"


@app.route("/")
def index():
    return "Bot is alive!"


@app.route("/ping")
def ping():
    return "pong"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)

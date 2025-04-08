from flask import Flask, request
import requests
import json
from utils import load_json, save_json

# Завантажуємо налаштування з config.json
with open("config.json") as f:
    config = json.load(f)

BOT_TOKEN = config["bot_token"]
ADMIN_CHAT_ID = config["admin_chat_id"]
BASE_LANDING_URL = "https://site.com?wm="  # Можеш замінити на свій домен

app = Flask(__name__)
API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

# Ініціалізація даних
users = load_json("users.json")
admin_auth = load_json("admin.json")
admin_session = {"authorized": False}


def send_message(chat_id, text, reply_markup=None):
    data = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML"
    }
    if reply_markup:
        data["reply_markup"] = json.dumps(reply_markup)
    requests.post(f"{API_URL}/sendMessage", data=data)


def get_keyboard(is_admin=False):
    buttons = [
        [{"text": "Моє посилання"}],
        [{"text": "Статуси"}],
        [{"text": "Мова"}]
    ]
    if is_admin:
        buttons.append([{"text": "Адмін"}])
    return {"keyboard": buttons, "resize_keyboard": True}


@app.route('/webhook', methods=["POST"])
def webhook():
    update = request.get_json()

    if "message" in update:
        msg = update["message"]
        chat_id = msg["chat"]["id"]
        user_id = str(chat_id)
        text = msg.get("text", "")
        is_admin = (chat_id == ADMIN_CHAT_ID)

        # Реєстрація користувача
        if user_id not in users:
            wm_code = user_id[-4:]
            users[user_id] = {
                "wm": wm_code,
                "username": msg["chat"].get("username", ""),
                "first_name": msg["chat"].get("first_name", "")
            }
            save_json("users.json", users)

        wm_link = f"{BASE_LANDING_URL}{users[user_id]['wm']}"

        # /start
        if text == "/start":
            send_message(chat_id, f"👋 Вітаю, {msg['chat'].get('first_name', '')}!", get_keyboard(is_admin))
            return "ok"

        # Моє посилання
        if text == "Моє посилання":
            send_message(chat_id, f"🔗 Ваше унікальне посилання:\n{wm_link}")
            return "ok"

        # Статуси (заглушка)
        if text == "Статуси":
            send_message(chat_id, "🕐 Статуси заявок тимчасово недоступні. Скоро буде оновлення.")
            return "ok"

        # Мова (заглушка)
        if text == "Мова":
            send_message(chat_id, "🌐 Поки що доступна тільки одна мова: українська.")
            return "ok"

        # Адмін
        if text == "Адмін":
            if not is_admin:
                send_message(chat_id, "⛔ Доступ заборонено.")
            elif not admin_session.get("authorized"):
                send_message(chat_id, "🔒 Введіть пароль:")
            else:
                return send_admin_panel(chat_id)
            return "ok"

        # Введення пароля
        if is_admin and not admin_session.get("authorized"):
            if text.strip() == admin_auth.get("password"):
                admin_session["authorized"] = True
                return send_admin_panel(chat_id)
            else:
                send_message(chat_id, "❌ Невірний пароль.")
                return "ok"

    return "ok"


def send_admin_panel(chat_id):
    user_count = len(users)
    wm_list = "\n".join([f"{u['first_name']} → {u['wm']}" for u in users.values()])
    text = f"""
🛠️ <b>АДМІН ПАНЕЛЬ</b>

👤 Кількість баєрів: {user_count}

📋 Список:
{wm_list}
    """.strip()
    send_message(chat_id, text)
    return "ok"


@app.route('/')
def index():
    return "Bot is running."


if __name__ == "__main__":
    app.run(debug=True)

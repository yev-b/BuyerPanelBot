from flask import Flask, request
import requests
import json
from utils import load_json, save_json

# Завантажуємо налаштування з config.json
with open("config.json") as f:
    config = json.load(f)

BOT_TOKEN = config["bot_token"]
ADMIN_CHAT_ID = config["admin_chat_id"]
BASE_LANDING_URL = "https://site.com?wm="

CPA_API_URL = "https://api.cpa.moe/ext/add.json?id=2594-1631fca8ff4515be7517265e1e62b755"

app = Flask(__name__)
API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

users = load_json("users.json")
admin_auth = load_json("admin.json")
leads = load_json("leads.json")
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

        if user_id not in users:
            wm_code = user_id[-4:]
            users[user_id] = {
                "wm": wm_code,
                "username": msg["chat"].get("username", ""),
                "first_name": msg["chat"].get("first_name", "")
            }
            save_json("users.json", users)

        wm_link = f"{BASE_LANDING_URL}{users[user_id]['wm']}"

        if text.startswith("/start"):
            first = msg['chat'].get('first_name', '')
text = f"""
👋 Привіт, {first}!

Ти підключений до панелі заливу 📲

Цей бот:
🔗 — видає твоє унікальне посилання
📊 — показує статуси лідів
📥 — сповіщає про нові заявки
⚙️ — доступ до адмінки (лише для боса)

👇 Обери команду нижче:
"""
send_message(chat_id, text, get_keyboard(is_admin))

            return "ok"

        if text == "Моє посилання":
            send_message(chat_id, f"🔗 Ваше унікальне посилання:\n{wm_link}")
            return "ok"

        if text == "Статуси":
            send_message(chat_id, "🕐 Статуси заявок тимчасово недоступні. Скоро буде оновлення.")
            return "ok"

        if text == "Мова":
            send_message(chat_id, "🌐 Поки що доступна тільки одна мова: українська.")
            return "ok"

        if text == "Адмін":
            if not is_admin:
                send_message(chat_id, "⛔ Доступ заборонено.")
            elif not admin_session.get("authorized"):
                send_message(chat_id, "🔒 Введіть пароль:")
            else:
                return send_admin_panel(chat_id)
            return "ok"

        if is_admin and not admin_session.get("authorized"):
            if text.strip() == admin_auth.get("password"):
                admin_session["authorized"] = True
                return send_admin_panel(chat_id)
            else:
                send_message(chat_id, "❌ Невірний пароль.")
                return "ok"

    return "ok"


@app.route("/lead", methods=["POST"])
def receive_lead():
    data = request.json
    wm = data.get("wm", "")
    name = data.get("name", "")
    phone = data.get("phone", "")
    ip = data.get("ip", "")
    ua = data.get("user_agent", "")
    country = data.get("country", "")
    referer = data.get("referer", "")
    datetime = data.get("datetime", "")
    us = data.get("utm_source", "")
    um = data.get("utm_medium", "")
    uc = data.get("utm_campaign", "")
    ut = data.get("utm_term", "")
    un = data.get("utm_content", "")

    payload = {
        "id": "auto",
        "wm": wm,
        "offer": "1639",
        "name": name,
        "phone": phone,
        "ip": ip,
        "ua": ua,
        "country": country,
        "currency": "EUR",
        "us": us,
        "um": um,
        "uc": uc,
        "ut": ut,
        "un": un,
        "params": {
            "referer": referer,
            "datetime": datetime
        }
    }

    # Відправляємо заявку в CPA API
    response = requests.post(CPA_API_URL, json=payload)
    result = response.json()

    # Якщо success → зберігаємо uid
    if result.get("status") == "ok" and "uid" in result:
        uid = result["uid"]
        if wm not in leads:
            leads[wm] = []
        leads[wm].append(uid)
        save_json("leads.json", leads)

        # Знаходимо чат баєра
        for user_id, info in users.items():
            if info["wm"] == wm:
                buyer_chat_id = int(user_id)
                send_message(buyer_chat_id, f"🟢 Новий лід на <b>wm:{wm}</b>")
                break

        # Сповіщення тобі (адміну)
        username = info.get("username", "невідомо")
        first_name = info.get("first_name", "")
        send_message(ADMIN_CHAT_ID, f"📥 Новий лід від <b>wm:{wm}</b> — <i>@{username} ({first_name})</i>")

        return {"status": "ok", "uid": uid}, 200

    return {"status": "error", "message": result.get("error", "Unknown error")}, 400


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

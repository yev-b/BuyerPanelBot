from flask import Flask, request
import requests
import json
import os
from utils import load_json, save_json

# Завантаження конфігів
with open("config.json") as f:
    config = json.load(f)

BOT_TOKEN = config["bot_token"]
ADMIN_CHAT_ID = config["admin_chat_id"]
DEFAULT_WM = config.get("default_wm", "2594")

API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

users = load_json("users.json")
admin_session = {"authorized": False}
leads = load_json("leads.json")
offers = load_json("offers.json")

app = Flask(__name__)


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
    base_buttons = ["Оффери", "Моє посилання", "Статуси", "Мова"]
    if is_admin:
        base_buttons.append("Адмін")
    keyboard = [[{"text": btn1}, {"text": btn2}] if btn2 else [{"text": btn1}]
                for btn1, btn2 in zip(base_buttons[::2], base_buttons[1::2] + [None])]
    return {"keyboard": keyboard, "resize_keyboard": True}


@app.route("/webhook", methods=["POST"])
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

        user_wm = users[user_id]["wm"]

        if text.startswith("/start"):
            name = msg["chat"].get("first_name", "")
            welcome = f"""
👋 Привіт, {name}!

Ти підключений до панелі заливу 📲

Цей бот:
🔗 — видає твоє унікальне посилання
📊 — показує статуси лідів
📥 — сповіщає про нові заявки
⚙️ — доступ до адмінки (лише для боса)

👇 Обери команду нижче:
"""
            send_message(chat_id, welcome, get_keyboard(is_admin))
            return "ok"

        if text == "Моє посилання":
            send_message(chat_id, f"🔗 Ваше посилання:\nhttps://fortemax.store?wm={user_wm}")
            return "ok"

        if text == "Статуси":
            send_message(chat_id, "🕐 Статуси тимчасово недоступні.")
            return "ok"

        if text == "Мова":
            send_message(chat_id, "🌐 Доступна лише українська.")
            return "ok"

        if text == "Адмін":
            if not is_admin:
                send_message(chat_id, "⛔ Доступ заборонено.")
            else:
                return send_admin_panel(chat_id)
            return "ok"

        if text == "Оффери":
            offer_buttons = [
                [{"text": offer["name"]}] for offer in offers.values()
            ]
            markup = {"keyboard": offer_buttons, "resize_keyboard": True}
            send_message(chat_id, "📦 Обери оффер:", markup)
            return "ok"

        # Якщо натиснуто назву оффера
        for offer_id, offer in offers.items():
            if text == offer["name"]:
                domain = offer["domain"]
                link = f"{domain}?wm={user_wm}&offer={offer_id}"
                send_message(chat_id, f"🔗 Посилання для <b>{offer['name']}</b>:\n{link}")
                return "ok"

    return "ok"


@app.route("/lead", methods=["POST"])
def receive_lead():
    data = request.json
    wm = data.get("wm", "") or DEFAULT_WM
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
        "offer": data.get("offer", ""),
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

    response = requests.post("https://api.cpa.moe/ext/add.json?id=2594-1631fca8ff4515be7517265e1e62b755", json=payload)
    result = response.json()

    if result.get("status") == "ok" and "uid" in result:
        uid = result["uid"]
        if wm not in leads:
            leads[wm] = []
        leads[wm].append(uid)
        save_json("leads.json", leads)

        for user_id, info in users.items():
            if info["wm"] == wm:
                send_message(int(user_id), "🟢 Новий лід на вашому оффері!")
                break

        send_message(ADMIN_CHAT_ID, f"📥 Новий лід від wm:{wm}")
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
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

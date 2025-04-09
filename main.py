from flask import Flask, request
import requests
import json
import os
from utils import load_json, save_json

# Завантаження конфігурації
with open("config.json") as f:
    config = json.load(f)

BOT_TOKEN = config["bot_token"]
ADMIN_CHAT_ID = config["admin_chat_id"]
WEBHOOK_URL = config["webhook_url"]
DEFAULT_WM = config.get("default_wm", "2594")
API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"
CAPI_URL = config.get("capi_url", "https://capi-production-1013.up.railway.app")

# Flask app
app = Flask(__name__)

# Завантаження баз
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
        [{"text": "📊 Статистика"}, {"text": "🎯 Мої пікселі"}]
    ]
    if is_admin:
        buttons.append([{"text": "⚙️ Адмін"}])
    return {"keyboard": buttons, "resize_keyboard": True}


@app.route("/set_webhook")
def set_webhook():
    res = requests.get(f"{API_URL}/setWebhook?url={WEBHOOK_URL}/webhook")
    return res.text


@app.route("/", methods=["GET"])
@app.route("/ping", methods=["GET"])
def alive():
    return "Bot is alive!"


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
            f"👋 Привіт, {users[user_id]['first_name']}!\n\n"
            "Цей бот:\n"
            "🔗 — видає твої посилання\n"
            "📊 — статистика лідів\n"
            "🎯 — керування Pixel ID\n"
            "⚙️ — адмінка\n\n"
            "👇 Обери дію:"
        )
        send_message(chat_id, welcome, get_keyboard(is_admin))
        return "ok"

    if text == "📦 Оффери":
        buttons = [[{"text": offer["name"]}] for offer in offers]
        buttons.append([{"text": "🔙 Назад"}])
        users[user_id]["state"] = "choosing_offer"
        save_json("users.json", users)
        send_message(chat_id, "📦 Обери оффер:", {"keyboard": buttons, "resize_keyboard": True})
        return "ok"

    if users[user_id].get("state") == "choosing_offer":
        selected = next((o for o in offers if o["name"] == text), None)
        if selected:
            link = f"{selected['url']}?wm={wm}"
            user_links.setdefault(user_id, []).append({"offer": selected["name"], "link": link})
            save_json("user_links.json", user_links)
            send_message(chat_id, f"🔗 Твоє посилання:\n<code>{link}</code>")
        else:
            send_message(chat_id, "❌ Такого оффера немає.")
        users[user_id]["state"] = None
        save_json("users.json", users)
        return "ok"

    if text == "🔗 Мої посилання":
        links = user_links.get(user_id, [])
        if not links:
            send_message(chat_id, "🔍 У тебе ще немає посилань.")
        else:
            msg = "\n\n".join([f"<b>{l['offer']}</b>:\n<code>{l['link']}</code>" for l in links])
            send_message(chat_id, f"🔗 Твої посилання:\n\n{msg}")
        return "ok"

    if text == "📊 Статистика":
        count = sum(1 for l in leads if leads[l]["wm"] == wm)
        send_message(chat_id, f"📊 Кількість твоїх заявок: <b>{count}</b>")
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
        send_message(chat_id, "📝 Введи <b>Pixel ID</b>:", {"keyboard": [[{"text": "🔙 Назад"}]]})
        return "ok"

    if users[user_id].get("state") == "awaiting_pixel":
        if not text.isdigit():
            send_message(chat_id, "❌ Pixel ID має бути числом!", {"keyboard": [[{"text": "🔙 Назад"}]]})
            return "ok"
        users[user_id]["temp_pixel"] = text
        users[user_id]["state"] = "awaiting_token"
        save_json("users.json", users)
        send_message(chat_id, "🔐 Введи Access Token:", {"keyboard": [[{"text": "🔙 Назад"}]]})
        return "ok"

    if users[user_id].get("state") == "awaiting_token":
        pixel_id = users[user_id]["temp_pixel"]
        token = text
        try:
            res = requests.post(f"{CAPI_URL}/add_pixel", json={"wm": wm, "pixel_id": pixel_id, "access_token": token})
            if res.ok:
                send_message(chat_id, f"✅ Pixel <code>{pixel_id}</code> додано.")
            else:
                send_message(chat_id, f"❌ Помилка CAPI: {res.text}")
        except Exception as e:
            send_message(chat_id, f"🚫 Не вдалося додати Pixel: {e}")
        users[user_id]["state"] = None
        users[user_id].pop("temp_pixel", None)
        save_json("users.json", users)
        return "ok"

    if text == "❌ Видалити Pixel":
        users[user_id]["state"] = "awaiting_remove_pixel"
        save_json("users.json", users)
        send_message(chat_id, "🗑️ Введи Pixel ID для видалення:", {"keyboard": [[{"text": "🔙 Назад"}]]})
        return "ok"

    if users[user_id].get("state") == "awaiting_remove_pixel":
        try:
            res = requests.post(f"{CAPI_URL}/remove_pixel", json={"wm": wm, "pixel_id": text})
            if res.ok:
                send_message(chat_id, f"🗑️ Pixel <code>{text}</code> видалено.")
            else:
                send_message(chat_id, f"❌ Помилка при видаленні: {res.text}")
        except Exception as e:
            send_message(chat_id, f"🚫 Видалити Pixel не вдалося: {e}")
        users[user_id]["state"] = None
        save_json("users.json", users)
        return "ok"

    if text == "⚙️ Адмін" and is_admin:
        total_users = len(users)
        total_leads = len(leads)
        send_message(chat_id, f"👑 <b>Адмінка:</b>\n👥 Користувачів: {total_users}\n📥 Заявок: {total_leads}")
        return "ok"

    return "ok"


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

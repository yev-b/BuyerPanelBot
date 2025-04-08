from flask import Flask, request
import requests
import json
import os
from utils import load_json, save_json

with open("config.json") as f:
    config = json.load(f)

BOT_TOKEN = config["bot_token"]
ADMIN_CHAT_ID = config["admin_chat_id"]
DEFAULT_WM = config.get("default_wm", "2594")

CPA_API_ADD = "https://api.cpa.moe/ext/add.json?id=2594-1631fca8ff4515be7517265e1e62b755"
CPA_API_STATUS = "https://api.cpa.moe/ext/list.json?id=2594-1631fca8ff4515be7517265e1e62b755&ids="

API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

users = load_json("users.json")
leads = load_json("leads.json")
offers = load_json("offers.json")
user_links = load_json("user_links.json")
admin_session = {"authorized": False}

app = Flask(__name__)


def send_message(chat_id, text, reply_markup=None):
    data = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML"
    }
    if reply_markup:
        data["reply_markup"] = json.dumps(reply_markup)
    response = requests.post(f"{API_URL}/sendMessage", data=data)
    if response.ok:
        return response.json().get("result", {}).get("message_id")
    return None


def delete_message(chat_id, message_id):
    requests.post(f"{API_URL}/deleteMessage", data={
        "chat_id": chat_id,
        "message_id": message_id
    })


def get_keyboard(is_admin=False):
    base_buttons = ["📦 Оффери", "🔗 Мої посилання", "📊 Статистика", "🌐 Мова"]
    if is_admin:
        base_buttons.append("⚙️ Адмін")
    keyboard = [[{"text": b1}, {"text": b2}] if b2 else [{"text": b1}]
                for b1, b2 in zip(base_buttons[::2], base_buttons[1::2] + [None])]
    return {"keyboard": keyboard, "resize_keyboard": True}


@app.route("/webhook", methods=["POST"])
def webhook():
    update = request.get_json()
    if "message" not in update:
        return "ok"

    msg = update["message"]
    chat_id = msg["chat"]["id"]
    message_id = msg["message_id"]
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

    if text.startswith("/start") or text == "🔙 Назад":
        delete_message(chat_id, message_id)
        first = msg["chat"].get("first_name", "")
        welcome = f"""
👋 Привіт, {first}!

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

    if text == "📦 Оффери":
        delete_message(chat_id, message_id)
        offer_buttons = [[{"text": offer["name"]}] for offer in offers.values()]
        offer_buttons.append([{"text": "🔙 Назад"}])
        send_message(chat_id, "📦 Обери оффер:", {"keyboard": offer_buttons, "resize_keyboard": True})
        return "ok"

    if text == "🔗 Мої посилання":
        delete_message(chat_id, message_id)
        links = user_links.get(user_id, [])
        if not links:
            send_message(chat_id, "❗ У вас ще немає збережених посилань.", {
                "keyboard": [[{"text": "🔙 Назад"}]], "resize_keyboard": True
            })
        else:
            formatted = "\n".join([f"🔗 {link}" for link in links])
            send_message(chat_id, f"📌 Ваші посилання:\n{formatted}", {
                "keyboard": [[{"text": "🔙 Назад"}]], "resize_keyboard": True
            })
        return "ok"

    if text == "📊 Статистика":
        delete_message(chat_id, message_id)
        return get_lead_statuses(user_wm, chat_id)

    if text == "🌐 Мова":
        delete_message(chat_id, message_id)
        send_message(chat_id, "🌐 Поки що доступна лише українська.", {
            "keyboard": [[{"text": "🔙 Назад"}]], "resize_keyboard": True
        })
        return "ok"

    if text == "⚙️ Адмін":
        delete_message(chat_id, message_id)
        if is_admin:
            return send_admin_panel(chat_id)
        else:
            send_message(chat_id, "⛔ Доступ заборонено.", {
                "keyboard": [[{"text": "🔙 Назад"}]], "resize_keyboard": True
            })
        return "ok"

    for offer_id, offer in offers.items():
        if text == offer["name"]:
            delete_message(chat_id, message_id)
            link = f"{offer['domain']}?wm={user_wm}&offer={offer_id}"
            user_links.setdefault(user_id, [])
            if link not in user_links[user_id]:
                user_links[user_id].append(link)
                save_json("user_links.json", user_links)
            send_message(chat_id, f"🔗 Посилання для <b>{offer['name']}</b>:\n{link}", {
                "keyboard": [[{"text": "🔙 Назад"}]], "resize_keyboard": True
            })
            return "ok"

    return "ok"


@app.route("/lead", methods=["POST"])
def receive_lead():
    data = request.json
    wm = data.get("wm", "") or DEFAULT_WM

    payload = {
        "id": "auto",
        "wm": wm,
        "offer": data.get("offer", ""),
        "name": data.get("name", ""),
        "phone": data.get("phone", ""),
        "ip": data.get("ip", ""),
        "ua": data.get("user_agent", ""),
        "country": data.get("country", ""),
        "currency": "EUR",
        "us": data.get("utm_source", ""),
        "um": data.get("utm_medium", ""),
        "uc": data.get("utm_campaign", ""),
        "ut": data.get("utm_term", ""),
        "un": data.get("utm_content", ""),
        "params": {
            "referer": data.get("referer", ""),
            "datetime": data.get("datetime", "")
        }
    }

    response = requests.post(CPA_API_ADD, json=payload)
    result = response.json()

    if result.get("status") == "ok" and "uid" in result:
        uid = result["uid"]
        leads.setdefault(wm, []).append(uid)
        save_json("leads.json", leads)

        for uid_user, info in users.items():
            if info["wm"] == wm:
                send_message(int(uid_user), "🟢 Новий лід на вашому оффері!")
                break

        send_message(ADMIN_CHAT_ID, f"📥 Новий лід від wm:{wm}")
        return {"status": "ok", "uid": uid}, 200

    return {"status": "error", "message": result.get("error", "Unknown error")}, 400


def get_lead_statuses(wm, chat_id):
    uid_list = leads.get(wm, [])
    if not uid_list:
        send_message(chat_id, "❗ У вас ще немає лідів.", {
            "keyboard": [[{"text": "🔙 Назад"}]], "resize_keyboard": True
        })
        return "ok"

    try:
        url = CPA_API_STATUS + ",".join(uid_list)
        result = requests.get(url).json()

        statuses = {
            "Ожидает": "⏳ Очікує",
            "Холд": "🟡 В холді",
            "Принят": "✅ Прийнято",
            "Отмена": "❌ Відхилено",
            "Треш": "🗑️ Видалено"
        }

        lines = [f"{statuses.get(info['status'], '❓ Невідомо')} — <code>{uid}</code>"
                 for uid, info in result.get("leads", {}).items()]
        send_message(chat_id, "📊 <b>Статуси лідів:</b>\n" + "\n".join(lines), {
            "keyboard": [[{"text": "🔙 Назад"}]], "resize_keyboard": True
        })
    except Exception as e:
        send_message(chat_id, f"⚠️ Помилка при запиті: {e}", {
            "keyboard": [[{"text": "🔙 Назад"}]], "resize_keyboard": True
        })
    return "ok"


def send_admin_panel(chat_id):
    user_count = len(users)
    wm_list = "\n".join([f"{u['first_name']} → {u['wm']}" for u in users.values()])
    send_message(chat_id, f"""
🛠️ <b>АДМІН ПАНЕЛЬ</b>

👤 Кількість баєрів: {user_count}
📋 Список:
{wm_list}
    """.strip(), {
        "keyboard": [[{"text": "🔙 Назад"}]], "resize_keyboard": True
    })
    return "ok"


@app.route('/')
def index():
    return "Bot is running."


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

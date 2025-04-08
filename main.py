from flask import Flask, request
import requests
import json
from utils import load_json, save_json

with open("config.json") as f:
    config = json.load(f)

BOT_TOKEN = config["bot_token"]
ADMIN_CHAT_ID = config["admin_chat_id"]
DEFAULT_WM = config.get("default_wm", "2594")
API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

app = Flask(__name__)

users = load_json("users.json")
leads = load_json("leads.json")
offers = load_json("offers.json")
user_links = load_json("user_links.json")
message_log = load_json("messages.json")


def send_message(chat_id, text, reply_markup=None):
    data = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML"
    }
    if reply_markup:
        data["reply_markup"] = json.dumps(reply_markup)
    res = requests.post(f"{API_URL}/sendMessage", json=data)
    if res.ok:
        message_id = res.json()["result"]["message_id"]
        message_log.setdefault(str(chat_id), []).append(message_id)
        save_json("messages.json", message_log)
        return message_id
    return None


def delete_message(chat_id, message_id):
    requests.post(f"{API_URL}/deleteMessage", json={
        "chat_id": chat_id,
        "message_id": message_id
    })


def delete_previous_bot_messages(chat_id):
    chat_id_str = str(chat_id)
    if chat_id_str in message_log:
        for msg_id in message_log[chat_id_str]:
            delete_message(chat_id, msg_id)
        message_log[chat_id_str] = []
        save_json("messages.json", message_log)


def get_keyboard(is_admin=False):
    buttons = [
        [{"text": "📦 Оффери"}, {"text": "🔗 Мої посилання"}],
        [{"text": "📊 Статистика"}, {"text": "🌐 Мова"}]
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
    text = message.get("text", "")
    msg_id = message["message_id"]
    user_id = str(chat_id)
    is_admin = chat_id == ADMIN_CHAT_ID

    if user_id not in users:
        users[user_id] = {
            "wm": user_id[-4:] if user_id != DEFAULT_WM else DEFAULT_WM,
            "username": message["chat"].get("username", ""),
            "first_name": message["chat"].get("first_name", "")
        }
        save_json("users.json", users)

    wm = users[user_id]["wm"]

    if text == "/start" or text == "🔙 Назад":
        delete_previous_bot_messages(chat_id)
        delete_message(chat_id, msg_id)
        welcome = (
            f"👋 Привіт, {message['chat'].get('first_name', '')}!\n\n"
            "Ти підключений до панелі заливу 📲\n\n"
            "Цей бот:\n"
            "🔗 — видає твоє унікальне посилання\n"
            "📊 — показує статистику лідів\n"
            "📥 — сповіщає про нові заявки\n"
            "⚙️ — доступ до адмінки (лише для боса)\n\n"
            "👇 Обери команду нижче:"
        )
        send_message(chat_id, welcome, get_keyboard(is_admin))
        return "ok"

    if text == "📦 Оффери":
        delete_previous_bot_messages(chat_id)
        delete_message(chat_id, msg_id)
        offer_buttons = [[{"text": offer["name"]}] for offer in offers.values()]
        offer_buttons.append([{"text": "🔙 Назад"}])
        send_message(chat_id, "📦 Обери оффер:", {"keyboard": offer_buttons, "resize_keyboard": True})
        return "ok"

    if text == "🔗 Мої посилання":
        delete_previous_bot_messages(chat_id)
        delete_message(chat_id, msg_id)
        links = user_links.get(user_id, [])
        if not links:
            send_message(chat_id, "❗ У вас ще немає збережених посилань.", {"keyboard": [[{"text": "🔙 Назад"}]]})
        else:
            formatted = "\n".join([f"🔗 {link}" for link in links])
            send_message(chat_id, f"📌 Ваші посилання:\n{formatted}", {"keyboard": [[{"text": "🔙 Назад"}]]})
        return "ok"

    if text == "📊 Статистика":
        delete_previous_bot_messages(chat_id)
        delete_message(chat_id, msg_id)
        return get_lead_statuses(wm, chat_id)

    if text == "🌐 Мова":
        delete_previous_bot_messages(chat_id)
        delete_message(chat_id, msg_id)
        send_message(chat_id, "🌐 Поки що доступна лише українська 🇺🇦", {"keyboard": [[{"text": "🔙 Назад"}]]})
        return "ok"

    if text == "⚙️ Адмін":
        delete_previous_bot_messages(chat_id)
        delete_message(chat_id, msg_id)
        if is_admin:
            return send_admin_panel(chat_id)
        else:
            send_message(chat_id, "⛔ Доступ заборонено.", {"keyboard": [[{"text": "🔙 Назад"}]]})
        return "ok"

    for offer_id, offer in offers.items():
        if text == offer["name"]:
            delete_previous_bot_messages(chat_id)
            delete_message(chat_id, msg_id)
            link = f"{offer['domain']}?wm={wm}&offer={offer_id}"
            user_links.setdefault(user_id, [])
            if link not in user_links[user_id]:
                user_links[user_id].append(link)
                save_json("user_links.json", user_links)
            send_message(chat_id, f"🔗 Посилання для <b>{offer['name']}</b>:\n{link}",
                         {"keyboard": [[{"text": "🔙 Назад"}]], "resize_keyboard": True})
            return "ok"

    return "ok"


def get_lead_statuses(wm, chat_id):
    uids = leads.get(wm, [])
    if not uids:
        send_message(chat_id, "ℹ️ У вас ще немає заявок.", {"keyboard": [[{"text": "🔙 Назад"}]]})
        return "ok"

    url = f"https://api.cpa.moe/ext/list.json?id=2594-1631fca8ff4515be7517265e1e62b755&ids={','.join(uids)}"
    try:
        r = requests.get(url).json()
        statuses = {
            "Ожидает": "⏳ Очікує",
            "Холд": "🟡 В холді",
            "Принят": "✅ Прийнято",
            "Отмена": "❌ Відхилено",
            "Треш": "🗑️ Видалено"
        }
        lines = [f"{statuses.get(lead['status'], '❓ Невідомо')} — <code>{lead['uid']}</code>"
                 for lead in r.get("leads", [])]
        send_message(chat_id, "📊 <b>Статистика лідів:</b>\n" + "\n".join(lines),
                     {"keyboard": [[{"text": "🔙 Назад"}]], "resize_keyboard": True})
    except Exception as e:
        send_message(chat_id, f"❌ Помилка: {e}", {"keyboard": [[{"text": "🔙 Назад"}]]})
    return "ok"


def send_admin_panel(chat_id):
    count = len(users)
    wm_list = "\n".join([f"{u['first_name']} → {u['wm']}" for u in users.values()])
    send_message(chat_id,
                 f"🛠️ <b>АДМІН ПАНЕЛЬ</b>\n\n👤 Кількість баєрів: {count}\n\n📋 Список:\n{wm_list}",
                 {"keyboard": [[{"text": "🔙 Назад"}]], "resize_keyboard": True})
    return "ok"


@app.route("/")
def index():
    return "Bot is alive!"


if __name__ == "__main__":
    app.run(debug=True)

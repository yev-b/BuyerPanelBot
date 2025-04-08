
from flask import Flask, request
import json
import requests

app = Flask(__name__)

# Конфіг
TOKEN = "7977859879:AAHXHPye3slD6S_TVSLdw-QmwiO0PXeOAa4"
URL = f"https://api.telegram.org/bot{TOKEN}/"

BUTTONS_UA = {
    "keyboard": [[
        {"text": "🔗 Моє посилання"},
        {"text": "📊 Статуси"},
        {"text": "🌐 Мова"}
    ]],
    "resize_keyboard": True,
    "one_time_keyboard": False
}

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json()

    if "message" in data:
        chat_id = data["message"]["chat"]["id"]
        text = data["message"].get("text", "")

        if text == "/start":
            welcome = "Привіт! Це ваш бот для контролю заявок 👋\nВиберіть дію нижче:"
            send_message(chat_id, welcome, BUTTONS_UA)
        elif "посилання" in text.lower():
            link = f"https://fortemax.store/?wm=buyer{chat_id}"
            send_message(chat_id, f"Ваше унікальне посилання:\n{link}")
        elif "статус" in text.lower():
            send_message(chat_id, "📊 Статуси ще не підключено, скоро буде 😉")
        elif "мова" in text.lower():
            send_message(chat_id, "🌐 Зараз підтримується лише українська. EN — скоро.")
        else:
            send_message(chat_id, "Не розумію 🤖 Оберіть дію з меню нижче.", BUTTONS_UA)

    return "OK"

def send_message(chat_id, text, reply_markup=None):
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True
    }
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup)

    requests.post(URL + "sendMessage", json=payload)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)

from flask import Flask, request
import json
import requests

app = Flask(__name__)

TOKEN = "7977859879:AAHXHPye3slD6S_TVSLdw-QmwiO0PXeOAa4"  # твій токен
URL = f"https://api.telegram.org/bot{TOKEN}/"

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json()
    print("🔥 ОТРИМАНО ДАНІ ВІД TELEGRAM:")
    print(json.dumps(data, indent=2, ensure_ascii=False))

    if "message" in data:
        chat_id = data["message"]["chat"]["id"]
        text = data["message"].get("text", "")

        if text == "/start":
            send_message(chat_id, "✅ Бот працює! Команда /start отримана.")
        else:
            send_message(chat_id, "ℹ️ Інше повідомлення отримано.")

    return "OK"

def send_message(chat_id, text):
    payload = {
        "chat_id": chat_id,
        "text": text
    }
    requests.post(URL + "sendMessage", json=payload)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)

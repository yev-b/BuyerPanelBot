import requests
from flask import Flask, request
import json

app = Flask(__name__)

TOKEN = "7977859879:AAHXHPye3slD6S_TVSLdw-QmwiO0PXeOAa4"

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json()

    if "message" in data:
        chat_id = data["message"]["chat"]["id"]
        text = data["message"].get("text", "")

        if text == "/start":
            send_message(chat_id, "Привіт! Це ваш бот для контролю заявок.")
        else:
            send_message(chat_id, "Я вас почув 👂")

    return "OK"

def send_message(chat_id, text):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text
    }
    requests.post(url, json=payload)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)

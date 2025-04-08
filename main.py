# main.py
from flask import Flask, request
import json

app = Flask(__name__)

@app.route('/webhook', methods=['POST'])
def webhook():
    return 'OK'

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)

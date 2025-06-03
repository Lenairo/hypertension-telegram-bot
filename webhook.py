from flask import Flask, request
import os
from dotenv import load_dotenv

load_dotenv()

WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # e.g. https://your-domain.com
PORT = int(os.getenv("PORT", 5000))

# Import bot instance and handlers from bot.py
from bot import bot

app = Flask(__name__)

@app.route('/webhook', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = bot.types.Update.de_json(json_string)  # Use bot.types to access telebot.types
        bot.process_new_updates([update])
        return "OK", 200
    else:
        return "Unsupported Media Type", 415

@app.route('/', methods=['GET'])
def index():
    return "Webhook is running.", 200

if __name__ == '__main__':
    bot.remove_webhook()
    bot.set_webhook(url=f"{WEBHOOK_URL}/webhook")
    print("✅ Webhook set. Starting Flask server...")
    app.run(host='0.0.0.0', port=PORT)



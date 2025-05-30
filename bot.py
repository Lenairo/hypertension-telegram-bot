import telebot
import psycopg2
from datetime import datetime
from dotenv import load_dotenv
import os

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
bot = telebot.TeleBot(BOT_TOKEN)

# PostgreSQL connection for patient data
def get_db_connection():
    return psycopg2.connect(
        host=os.getenv("PG_HOST"),
        user=os.getenv("PG_USER"),
        password=os.getenv("PG_PASSWORD"),
        dbname=os.getenv("PG_DB"),
        port=5432
    )

user_data = {}

translations = {
    "English": {
        "welcome": "👋 Welcome! Please choose your *preferred language*:",
        "ask_patient_id": "Please enter your *patient ID*:",
        "linked": "✅ You're linked! We'll ask for your blood pressure daily.",
        "systolic": "📊 Enter your *systolic* blood pressure (mmHg):",
        "diastolic": "Now enter your *diastolic* blood pressure (mmHg):",
        "pulse": "❤️ Finally, enter your *pulse* (bpm):",
        "summary": "🩺 Here are your readings:\nSystolic: {sys} mmHg\nDiastolic: {dia} mmHg\nPulse: {pulse} bpm\nMAP: {map} mmHg",
        "thanks": "✅ Thank you! Your data is saved.",
        "db_error": "❌ Error saving your data. Please try again later.",
    },
    "Ukrainian": {
        "welcome": "👋 Ласкаво просимо! Будь ласка, оберіть *бажану мову*:",
        "ask_patient_id": "Введіть ваш *ID пацієнта*:",
        "linked": "✅ Ви підключені! Ми щодня будемо питати вас про тиск.",
        "systolic": "📊 Введіть ваш *систолічний* тиск (мм рт. ст.):",
        "diastolic": "Тепер введіть ваш *діастолічний* тиск (мм рт. ст.):",
        "pulse": "❤️ Нарешті, введіть ваш *пульс* (уд/хв):",
        "summary": "🩺 Ваші показники:\nСистолічний: {sys} мм рт. ст.\nДіастолічний: {dia} мм рт. ст.\nПульс: {pulse} уд/хв\nMAP: {map} мм рт. ст.",
        "thanks": "✅ Дякуємо! Ваші дані збережено.",
        "db_error": "❌ Помилка збереження даних. Спробуйте ще раз пізніше.",
    }
}

@bot.message_handler(commands=['start'])
def welcome(message):
    chat_id = message.chat.id
    user_data[chat_id] = {}
    markup = telebot.types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
    markup.add("English", "Ukrainian")
    bot.send_message(chat_id, "👋 Welcome! Please choose your *preferred language*:", parse_mode="Markdown", reply_markup=markup)

@bot.message_handler(func=lambda msg: msg.chat.id in user_data and "language" not in user_data[msg.chat.id])
def get_language(message):
    chat_id = message.chat.id
    language = message.text.strip()
    user_data[chat_id]["language"] = language
    bot.send_message(chat_id, translations[language]["ask_patient_id"], parse_mode="Markdown")

@bot.message_handler(func=lambda msg: msg.chat.id in user_data and "patient_id" not in user_data[msg.chat.id])
def save_patient_id(message):
    chat_id = message.chat.id
    patient_id = message.text.strip()
    user_data[chat_id]["patient_id"] = patient_id
    language = user_data[chat_id]["language"]

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO patient_bot_links (
                patient_id, telegram_user_id, telegram_username, language
            ) VALUES (%s, %s, %s, %s)
            ON CONFLICT (telegram_user_id) DO UPDATE SET
                patient_id = EXCLUDED.patient_id,
                language = EXCLUDED.language
        """, (
            patient_id,
            chat_id,
            message.from_user.username or "",
            language
        ))
        conn.commit()
        cursor.close()
        conn.close()

        bot.send_message(chat_id, translations[language]["linked"])
        bot.send_message(chat_id, translations[language]["systolic"], parse_mode="Markdown")
    except Exception as e:
        print(f"DB Error: {e}")
        bot.send_message(chat_id, translations[language]["db_error"])

@bot.message_handler(func=lambda msg: msg.chat.id in user_data and "systolic" not in user_data[msg.chat.id])
def get_systolic(message):
    chat_id = message.chat.id
    user_data[chat_id]["systolic"] = message.text.strip()
    lang = user_data[chat_id]["language"]
    bot.send_message(chat_id, translations[lang]["diastolic"], parse_mode="Markdown")

@bot.message_handler(func=lambda msg: msg.chat.id in user_data and "diastolic" not in user_data[msg.chat.id])
def get_diastolic(message):
    chat_id = message.chat.id
    user_data[chat_id]["diastolic"] = message.text.strip()
    lang = user_data[chat_id]["language"]
    bot.send_message(chat_id, translations[lang]["pulse"], parse_mode="Markdown")

@bot.message_handler(func=lambda msg: msg.chat.id in user_data and "pulse" not in user_data[msg.chat.id])
def save_bp_readings(message):
    chat_id = message.chat.id
    user_data[chat_id]["pulse"] = message.text.strip()
    lang = user_data[chat_id]["language"]

    try:
        sys = float(user_data[chat_id]["systolic"])
        dia = float(user_data[chat_id]["diastolic"])
        pulse = float(user_data[chat_id]["pulse"])
        map_val = round(dia + (sys - dia) / 3)

        summary = translations[lang]["summary"].format(sys=sys, dia=dia, pulse=pulse, map=map_val)
        bot.send_message(chat_id, summary)

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO patient_bp_readings (
                patient_id, systolic_bp, diastolic_bp, pulse
            ) VALUES (%s, %s, %s, %s)
        """, (
            user_data[chat_id]["patient_id"],
            sys,
            dia,
            pulse
        ))
        conn.commit()
        cursor.close()
        conn.close()

        bot.send_message(chat_id, translations[lang]["thanks"])
        del user_data[chat_id]  # reset conversation
    except Exception as e:
        print(f"DB Error on BP insert: {e}")
        bot.send_message(chat_id, translations[lang]["db_error"])

# Start bot
print("🤖 Bot is now polling. Waiting for messages...")
bot.polling()


    

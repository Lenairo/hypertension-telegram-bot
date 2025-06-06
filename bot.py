import telebot
import psycopg2
from dotenv import load_dotenv
import os

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")

bot = telebot.TeleBot(BOT_TOKEN)
user_data = {}

# --- Database connection ---
def get_db_connection():
    return psycopg2.connect(
        host=os.getenv("PG_HOST"),
        user=os.getenv("PG_USER"),
        password=os.getenv("PG_PASSWORD"),
        dbname=os.getenv("PG_DB"),
        port=5432
    )

# --- Translations ---
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
        "main_menu": "Please choose:",
        "enter_bp_button": "📤 Enter BP"
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
        "main_menu": "Будь ласка, оберіть:",
        "enter_bp_button": "📤 Ввести тиск"
    }
}

# --- Helpers ---
def is_onboarded(chat_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM patient_bot_links WHERE telegram_user_id = %s", (chat_id,))
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        return result is not None
    except Exception as e:
        print(f"DB Error (is_onboarded): {e}")
        return False

def get_user_language(chat_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT language FROM patient_bot_links WHERE telegram_user_id = %s", (chat_id,))
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        return result[0] if result else "English"
    except Exception as e:
        print(f"DB Error (get_user_language): {e}")
        return "English"

def send_main_menu(chat_id, lang):
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(translations[lang]["enter_bp_button"])
    bot.send_message(chat_id, translations[lang]["main_menu"], reply_markup=markup)

# --- Handlers ---
@bot.message_handler(commands=['start'])
def welcome(message):
    chat_id = message.chat.id
    if is_onboarded(chat_id):
        lang = get_user_language(chat_id)
        greeting = "👋 Welcome back!" if lang == "English" else "👋 Ласкаво просимо знову!"
        bot.send_message(chat_id, greeting, reply_markup=telebot.types.ReplyKeyboardRemove())
        send_main_menu(chat_id, lang)
        return

    user_data[chat_id] = {}
    markup = telebot.types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
    markup.add("English", "Ukrainian")
    bot.send_message(chat_id, translations["English"]["welcome"], parse_mode="Markdown", reply_markup=markup)

@bot.message_handler(func=lambda msg: msg.chat.id in user_data and "language" not in user_data[msg.chat.id])
def get_language(message):
    chat_id = message.chat.id
    language = message.text.strip()
    if language not in translations:
        bot.send_message(chat_id, "⚠️ Please select a valid language option.")
        return
    user_data[chat_id]["language"] = language
    bot.send_message(chat_id, translations[language]["ask_patient_id"], parse_mode="Markdown")

@bot.message_handler(func=lambda msg: msg.chat.id in user_data and "patient_id" not in user_data[msg.chat.id])
def save_patient_id(message):
    chat_id = message.chat.id
    patient_id = message.text.strip()
    language = user_data[chat_id]["language"]
    user_data[chat_id]["patient_id"] = patient_id
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO patient_bot_links (patient_id, telegram_user_id, telegram_username, language)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (telegram_user_id) DO UPDATE SET patient_id = EXCLUDED.patient_id, language = EXCLUDED.language
        """, (patient_id, chat_id, message.from_user.username or "", language))
        conn.commit()
        cursor.close()
        conn.close()
        bot.send_message(chat_id, translations[language]["linked"])
        bot.send_message(chat_id, translations[language]["systolic"], parse_mode="Markdown")
        user_data[chat_id]["state"] = "awaiting_systolic"
    except Exception as e:
        print(f"DB Error (save_patient_id): {e}")
        bot.send_message(chat_id, translations[language]["db_error"])

@bot.message_handler(func=lambda msg: msg.chat.id in user_data and user_data[msg.chat.id].get("state") == "awaiting_systolic")
def get_systolic(message):
    chat_id = message.chat.id
    try:
        systolic = float(message.text.strip())
        user_data[chat_id]["systolic"] = systolic
        user_data[chat_id]["state"] = "awaiting_diastolic"
        bot.send_message(chat_id, translations[user_data[chat_id]["language"]]["diastolic"], parse_mode="Markdown")
    except ValueError:
        bot.send_message(chat_id, "⚠️ Please enter a valid number")

@bot.message_handler(func=lambda msg: msg.chat.id in user_data and user_data[msg.chat.id].get("state") == "awaiting_diastolic")
def get_diastolic(message):
    chat_id = message.chat.id
    try:
        diastolic = float(message.text.strip())
        user_data[chat_id]["diastolic"] = diastolic
        user_data[chat_id]["state"] = "awaiting_pulse"
        bot.send_message(chat_id, translations[user_data[chat_id]["language"]]["pulse"], parse_mode="Markdown")
    except ValueError:
        bot.send_message(chat_id, "⚠️ Please enter a valid number")

@bot.message_handler(func=lambda msg: msg.chat.id in user_data and user_data[msg.chat.id].get("state") == "awaiting_pulse")
def get_pulse(message):
    chat_id = message.chat.id
    try:
        pulse = float(message.text.strip())
        user_data[chat_id]["pulse"] = pulse
        lang = user_data[chat_id]["language"]
        sys = user_data[chat_id]["systolic"]
        dia = user_data[chat_id]["diastolic"]
        map_val = round(dia + (sys - dia) / 3)
        summary = translations[lang]["summary"].format(sys=sys, dia=dia, pulse=pulse, map=map_val)
        bot.send_message(chat_id, summary)
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO patient_bp_readings (patient_id, systolic_bp, diastolic_bp, pulse)
                VALUES (%s, %s, %s, %s)
            """, (user_data[chat_id]["patient_id"], sys, dia, pulse))
            conn.commit()
            cursor.close()
            conn.close()
            bot.send_message(chat_id, translations[lang]["thanks"])
            send_main_menu(chat_id, lang)
            del user_data[chat_id]
        except Exception as e:
            print(f"DB Error (get_pulse save): {e}")
            bot.send_message(chat_id, translations[lang]["db_error"])
    except ValueError:
        bot.send_message(chat_id, "⚠️ Please enter a valid number")

@bot.message_handler(func=lambda msg: msg.chat.id not in user_data and is_onboarded(msg.chat.id) and msg.text in [
    translations[get_user_language(msg.chat.id)]["enter_bp_button"], "/enter"
])
def handle_enter_bp(message):
    chat_id = message.chat.id
    lang = get_user_language(chat_id)
    user_data[chat_id] = {"language": lang, "state": "awaiting_systolic"}
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT patient_id FROM patient_bot_links WHERE telegram_user_id = %s", (chat_id,))
        patient = cursor.fetchone()
        cursor.close()
        conn.close()
        if patient:
            user_data[chat_id]["patient_id"] = patient[0]
            bot.send_message(chat_id, translations[lang]["systolic"], parse_mode="Markdown")
        else:
            bot.send_message(chat_id, translations[lang]["db_error"])
    except Exception as e:
        print(f"DB Error (handle_enter_bp): {e}")
        bot.send_message(chat_id, translations[lang]["db_error"])

@bot.message_handler(func=lambda msg: msg.chat.id not in user_data and is_onboarded(msg.chat.id))
def resume_session(message):
    send_main_menu(message.chat.id, get_user_language(message.chat.id))

@bot.message_handler(func=lambda msg: True)
def fallback(message):
    chat_id = message.chat.id
    if not is_onboarded(chat_id):
        bot.send_message(chat_id, "Please type /start to begin.")
    else:
        send_main_menu(chat_id, get_user_language(chat_id))

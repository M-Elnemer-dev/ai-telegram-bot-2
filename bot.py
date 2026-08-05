import os
import time
import logging
from collections import defaultdict
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from g4f.client import Client

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("TELEGRAM_TOKEN")
ADMIN_ID = os.getenv("ADMIN_CHAT_ID")

g4f_client = Client()

user_settings = defaultdict(lambda: {"mode": "quick", "lang": "en"})
user_histories = defaultdict(list)
user_message_times = defaultdict(list)
RATE_LIMIT_COUNT = 5
RATE_LIMIT_WINDOW = 10

def get_main_keyboard(user_id: int):
    s = user_settings[user_id]
    mode_marks = {"quick": "⚡", "points": "📌", "arabic": "🌐"}
    lang_marks = {"en": "🇺🇸 EN", "ar": "🇸🇦 AR"}

    keyboard = [
        [
            InlineKeyboardButton(f"{mode_marks.get(s['mode'], '⚡')} Mode", callback_data="toggle_mode"),
            InlineKeyboardButton(f"Lang: {lang_marks.get(s['lang'], 'EN')}", callback_data="toggle_lang")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_histories[user_id] = []
    
    text = "🤖 **Welcome to the AI Document & Text Summarizer!** 📄\n\nاختر وضع التلخيص أو اللغة من الأزرار بالأسفل ثم أرسل نصك:"
    await update.message.reply_text(text, reply_markup=get_main_keyboard(user_id), parse_mode="Markdown")

async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()

    s = user_settings[user_id]

    if query.data == "toggle_mode":
        if s["mode"] == "quick":
            s["mode"] = "points"
        elif s["mode"] == "points":
            s["mode"] = "arabic"
        else:
            s["mode"] = "quick"
    elif query.data == "toggle_lang":
        s["lang"] = "ar" if s["lang"] == "en" else "en"

    modes_desc = {"quick": "⚡ Quick Summary", "points": "📌 Key Points", "arabic": "🌐 Arabic Summary"}
    status_text = f"⚙️ **Settings Updated:**\n- Mode: {modes_desc[s['mode']]}\n- Language: {s['lang'].upper()}\n\nأرسل النص الآن للتلخيص:"
    
    await query.message.edit_text(status_text, reply_markup=get_main_keyboard(user_id), parse_mode="Markdown")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    s = user_settings[user_id]

    if is_rate_limited(user_id):
        await update.message.reply_text("⚠️ Rate limit reached.")
        return

    user_text = update.message.text
    user_histories[user_id].append({"role": "user", "content": user_text})
    if len(user_histories[user_id]) > 10:
        user_histories[user_id] = user_histories[user_id][-10:]

    if s["mode"] == "arabic" or s["lang"] == "ar":
        system_content = "You are a professional text summarizer. You MUST provide a clear, concise summary of the text provided by the user entirely and strictly in Arabic language."
    elif s["mode"] == "points":
        system_content = "You are a professional text summarizer. Extract the main key points of the text provided in clear bullet points in English."
    else:
        system_content = "You are a professional text summarizer. Provide a quick, clear, and concise summary of the text provided by the user in English."

    messages = [
        {"role": "system", "content": system_content}
    ] + user_histories[user_id]

    try:
        client = Client()
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
        )
        reply = response.choices[0].message.content
        if reply:
            user_histories[user_id].append({"role": "assistant", "content": reply})
            await update.message.reply_text(reply, reply_markup=get_main_keyboard(user_id), parse_mode="Markdown")
        else:
            await update.message.reply_text("⚠️ No response generated.", reply_markup=get_main_keyboard(user_id))
    except Exception as e:
        logger.error(f"AI Error: {e}")
        await update.message.reply_text(f"حدث خطأ: {str(e)}", reply_markup=get_main_keyboard(user_id))

def is_rate_limited(user_id: int) -> bool:
    current_time = time.time()
    user_message_times[user_id] = [
        t for t in user_message_times[user_id] if current_time - t < RATE_LIMIT_WINDOW
    ]
    if len(user_message_times[user_id]) >= RATE_LIMIT_COUNT:
        return True
    user_message_times[user_id].append(current_time)
    return False

def main():
    if not TELEGRAM_TOKEN:
        logger.critical("TELEGRAM_BOT_TOKEN environment variable is missing or empty!")
        return

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CallbackQueryHandler(button_click))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    app.run_polling()

if __name__ == '__main__':
    main()

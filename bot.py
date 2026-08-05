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

user_languages = {}
user_states = {}
user_histories = defaultdict(list)
user_message_times = defaultdict(list)
RATE_LIMIT_COUNT = 5
RATE_LIMIT_WINDOW = 10

TRANSLATIONS = {
    "ar": {
        "welcome": "🤖 **Welcome to the AI Document & Text Summarizer!** 📄\n\nDefault Language: English 🇺🇸\nSend a text, PDF, or Word file to summarize!",
        "quick_summary": "⚡ Quick Summary",
        "quick_summary_text": "⚡ **Quick Summary Mode Activated:** Send your text to get a fast summary.",
        "key_points": "📌 Key Points",
        "key_points_text": "📌 **Key Points Mode Activated:** Send your text to extract main points.",
        "arabic_summary": "🌐 Arabic Summary",
        "arabic_summary_text": "🌐 **Arabic Summary Mode Activated:** Send your text for an Arabic summary.",
        "change_lang": "🌐 Change UI Language",
        "select_lang": "🌐 **Select Language / اختر اللغة:**"
    },
    "en": {
        "welcome": "🤖 **Welcome to the AI Document & Text Summarizer!** 📄\n\nDefault Language: English 🇺🇸\nSend a text, PDF, or Word file to summarize!",
        "quick_summary": "⚡ Quick Summary",
        "quick_summary_text": "⚡ **Quick Summary Mode Activated:** Send your text to get a fast summary.",
        "key_points": "📌 Key Points",
        "key_points_text": "📌 **Key Points Mode Activated:** Send your text to extract main points.",
        "arabic_summary": "🌐 Arabic Summary",
        "arabic_summary_text": "🌐 **Arabic Summary Mode Activated:** Send your text for an Arabic summary.",
        "change_lang": "🌐 Change UI Language",
        "select_lang": "🌐 **Select Language:**"
    }
}

def get_t(user_id: int, key: str) -> str:
    lang = user_languages.get(user_id, "en")
    if lang not in TRANSLATIONS:
        lang = "en"
    return TRANSLATIONS[lang].get(key, TRANSLATIONS["en"].get(key, key))

def is_rate_limited(user_id: int) -> bool:
    current_time = time.time()
    user_message_times[user_id] = [
        t for t in user_message_times[user_id] if current_time - t < RATE_LIMIT_WINDOW
    ]
    if len(user_message_times[user_id]) >= RATE_LIMIT_COUNT:
        return True
    user_message_times[user_id].append(current_time)
    return False

def get_main_keyboard(user_id: int):
    keyboard = [
        [InlineKeyboardButton(get_t(user_id, "quick_summary"), callback_data="quick_summary"), InlineKeyboardButton(get_t(user_id, "key_points"), callback_data="key_points")],
        [InlineKeyboardButton(get_t(user_id, "arabic_summary"), callback_data="arabic_summary")],
        [InlineKeyboardButton(get_t(user_id, "change_lang"), callback_data="change_lang")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_language_keyboard():
    keyboard = [
        [InlineKeyboardButton("🇸🇦 العربية", callback_data="set_lang_ar"), InlineKeyboardButton("🇺🇸 English", callback_data="set_lang_en")]
    ]
    return InlineKeyboardMarkup(keyboard)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_states[user_id] = "quick_summary"
    user_histories[user_id] = []
    
    text = get_t(user_id, "welcome")
    await update.message.reply_text(text, reply_markup=get_main_keyboard(user_id), parse_mode="Markdown")

async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()

    if query.data.startswith("set_lang_"):
        selected_lang = query.data.split("_")[2]
        user_languages[user_id] = selected_lang
        msg = f"✅ Language updated to: **{selected_lang.upper()}**"
        await query.message.reply_text(msg, reply_markup=get_main_keyboard(user_id), parse_mode="Markdown")
        return

    if query.data == "quick_summary":
        user_states[user_id] = "quick_summary"
        user_histories[user_id] = []
        msg = get_t(user_id, "quick_summary_text")
    elif query.data == "key_points":
        user_states[user_id] = "key_points"
        user_histories[user_id] = []
        msg = get_t(user_id, "key_points_text")
    elif query.data == "arabic_summary":
        user_states[user_id] = "arabic_summary"
        user_histories[user_id] = []
        msg = get_t(user_id, "arabic_summary_text")
    elif query.data == "change_lang":
        await query.message.reply_text(get_t(user_id, "select_lang"), reply_markup=get_language_keyboard(), parse_mode="Markdown")
        return

    await query.message.reply_text(msg, reply_markup=get_main_keyboard(user_id), parse_mode="Markdown")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    current_state = user_states.get(user_id, "quick_summary")

    if is_rate_limited(user_id):
        await update.message.reply_text("⚠️ Rate limit reached.")
        return

    user_text = update.message.text
    user_histories[user_id].append({"role": "user", "content": user_text})
    if len(user_histories[user_id]) > 10:
        user_histories[user_id] = user_histories[user_id][-10:]

    if current_state == "arabic_summary":
        system_content = "You are a professional text summarizer. You MUST provide a clear, concise summary of the text provided by the user entirely and strictly in Arabic language."
    elif current_state == "key_points":
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

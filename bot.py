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

MODE_NAMES = {
    "quick": "⚡ Quick Summary",
    "points": "📌 Key Points",
    "deep": "🧠 Deep Analysis"
}

LANG_NAMES = {
    "en": "🇺🇸 English",
    "ar": "🇸🇦 العربية",
    "fr": "🇫🇷 Français",
    "de": "🇩🇪 Deutsch"
}

def get_main_keyboard(user_id: int):
    s = user_settings[user_id]
    current_mode_text = MODE_NAMES.get(s['mode'], '⚡ Quick')
    current_lang_text = LANG_NAMES.get(s['lang'], '🇺🇸 English')

    keyboard = [
        [InlineKeyboardButton(f"⚙️ Mode: {current_mode_text}", callback_data="menu_modes")],
        [InlineKeyboardButton(f"🌐 Lang: {current_lang_text}", callback_data="menu_langs")],
    ]
    return InlineKeyboardMarkup(keyboard)

def get_modes_keyboard():
    keyboard = [
        [InlineKeyboardButton("⚡ Quick Summary", callback_data="set_mode_quick")],
        [InlineKeyboardButton("📌 Key Points", callback_data="set_mode_points")],
        [InlineKeyboardButton("🧠 Deep Analysis", callback_data="set_mode_deep")],
        [InlineKeyboardButton("🔙 Back", callback_data="back_main")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_langs_keyboard():
    keyboard = [
        [InlineKeyboardButton("🇸🇦 العربية", callback_data="set_lang_ar"), InlineKeyboardButton("🇺🇸 English", callback_data="set_lang_en")],
        [InlineKeyboardButton("🇫🇷 Français", callback_data="set_lang_fr"), InlineKeyboardButton("🇩🇪 Deutsch", callback_data="set_lang_de")],
        [InlineKeyboardButton("🔙 Back", callback_data="back_main")]
    ]
    return InlineKeyboardMarkup(keyboard)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_histories[user_id] = []
    
    text = "🤖 **Welcome to the AI Document & Text Summarizer!** 📄\n\nاختر وضع التلخيص ولغة الإخراج من الأزرار بالأسفل:"
    await update.message.reply_text(text, reply_markup=get_main_keyboard(user_id), parse_mode="Markdown")

async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()

    s = user_settings[user_id]
    data = query.data

    if data == "menu_modes":
        await query.message.edit_text("📌 **اختر نوع التلخيص المطلوب:**", reply_markup=get_modes_keyboard(), parse_mode="Markdown")
        return
    elif data == "menu_langs":
        await query.message.edit_text("🌐 **اختر لغة الإخراج:**", reply_markup=get_langs_keyboard(), parse_mode="Markdown")
        return
    elif data == "back_main":
        await query.message.edit_text("⚙️ **الإعدادات الحالية:**\nأرسل النص الآن للتلخيص:", reply_markup=get_main_keyboard(user_id), parse_mode="Markdown")
        return
    elif data.startswith("set_mode_"):
        s["mode"] = data.split("_")[2]
    elif data.startswith("set_lang_"):
        s["lang"] = data.split("_")[2]

    status_text = f"⚙️ **Settings Updated:**\n- Mode: {MODE_NAMES[s['mode']]}\n- Language: {LANG_NAMES[s['lang']]}\n\nأرسل النص الآن للتلخيص:"
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

    lang_code = s["lang"]
    mode = s["mode"]

    if mode == "quick":
        system_content = f"You are a professional text summarizer. Provide a quick, clear, and concise summary of the text provided by the user in '{lang_code}' language."
    elif mode == "points":
        system_content = f"You are a professional text summarizer. Extract the main key points of the text provided in clear bullet points in '{lang_code}' language."
    elif mode == "deep":
        system_content = f"You are an expert analytical assistant. Provide a deep, comprehensive, and detailed analysis and summary of the text provided by the user in '{lang_code}' language."
    else:
        system_content = f"You are a professional text summarizer. Provide a summary in '{lang_code}' language."

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

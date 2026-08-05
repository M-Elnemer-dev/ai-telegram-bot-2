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

UI_TEXTS = {
    "en": {
        "welcome": "🤖 **Welcome to the AI Document & Text Summarizer!** 📄\n\nChoose your settings below:",
        "mode_btn": "⚙️ Mode",
        "lang_btn": "🌐 Lang",
        "select_mode": "📌 **Select Summary Mode:**",
        "select_lang": "🌐 **Select Output Language:**",
        "back": "🔙 Back",
        "settings_updated": "⚙️ **Settings Updated:**",
        "send_text": "Send your text now for summarization:",
        "loading": "⏳ **Processing your request, please wait...**",
        "quick": "⚡ Quick Summary",
        "points": "📌 Key Points",
        "deep": "🧠 Deep Analysis",
        "error": "⚠️ An error occurred."
    },
    "ar": {
        "welcome": "🤖 **مرحباً بك في بوت تلخيص النصوص والمستندات الذكي!** 📄\n\nاختر إعداداتك بالأسفل:",
        "mode_btn": "⚙️ الوضع",
        "lang_btn": "🌐 اللغة",
        "select_mode": "📌 **اختر نوع التلخيص:**",
        "select_lang": "🌐 **اختر لغة الإخراج:**",
        "back": "🔙 رجوع",
        "settings_updated": "⚙️ **تم تحديث الإعدادات:**",
        "send_text": "أرسل النص الآن للتلخيص:",
        "loading": "⏳ **جاري معالجة طلبك، برجاء الانتظار...**",
        "quick": "⚡ تلخيص سريع",
        "points": "📌 نقاط رئيسية",
        "deep": "🧠 تحليل متعمق",
        "error": "⚠️ حدث خطأ أثناء المعالجة."
    },
    "fr": {
        "welcome": "🤖 **Bienvenue dans le bot de résumé de texte IA!** 📄\n\nChoisissez vos paramètres ci-dessous:",
        "mode_btn": "⚙️ Mode",
        "lang_btn": "🌐 Langue",
        "select_mode": "📌 **Sélectionnez le mode de résumé:**",
        "select_lang": "🌐 **Sélectionnez la langue de sortie:**",
        "back": "🔙 Retour",
        "settings_updated": "⚙️ **Paramètres mis à jour:**",
        "send_text": "Envoyez votre texte maintenant:",
        "loading": "⏳ **Traitement en cours, veuillez patienter...**",
        "quick": "⚡ Résumé Rapide",
        "points": "📌 Points Clés",
        "deep": "🧠 Analyse Approfondie",
        "error": "⚠️ Une erreur s'est produite."
    },
    "de": {
        "welcome": "🤖 **Willkommen beim KI-Textzusammenfassungs-Bot!** 📄\n\nWählen Sie unten Ihre Einstellungen:",
        "mode_btn": "⚙️ Modus",
        "lang_btn": "🌐 Sprache",
        "select_mode": "📌 **Wählen Sie den Modus:**",
        "select_lang": "🌐 **Wählen Sie die Sprache:**",
        "back": "🔙 Zurück",
        "settings_updated": "⚙️ **Einstellungen aktualisiert:**",
        "send_text": "Senden Sie jetzt Ihren Text:",
        "loading": "⏳ **Ihre Anfrage wird bearbeitet, bitte warten...**",
        "quick": "⚡ Schnelle Zusammenfassung",
        "points": "📌 Kernpunkte",
        "deep": "🧠 Tiefenanalyse",
        "error": "⚠️ Ein Fehler ist aufgetreten."
    }
}

LANG_NAMES = {
    "en": "🇺🇸 English",
    "ar": "🇸🇦 العربية",
    "fr": "🇫🇷 Français",
    "de": "🇩🇪 Deutsch"
}

def get_t(lang: str, key: str) -> str:
    if lang not in UI_TEXTS:
        lang = "en"
    return UI_TEXTS[lang].get(key, UI_TEXTS["en"].get(key, key))

def get_main_keyboard(user_id: int):
    s = user_settings[user_id]
    lang = s['lang']
    mode = s['mode']
    
    mode_label = get_t(lang, mode)
    lang_label = LANG_NAMES.get(lang, "🇺🇸 English")

    keyboard = [
        [InlineKeyboardButton(f"{get_t(lang, 'mode_btn')}: {mode_label}", callback_data="menu_modes")],
        [InlineKeyboardButton(f"{get_t(lang, 'lang_btn')}: {lang_label}", callback_data="menu_langs")],
    ]
    return InlineKeyboardMarkup(keyboard)

def get_modes_keyboard(lang: str):
    keyboard = [
        [InlineKeyboardButton(get_t(lang, "quick"), callback_data="set_mode_quick")],
        [InlineKeyboardButton(get_t(lang, "points"), callback_data="set_mode_points")],
        [InlineKeyboardButton(get_t(lang, "deep"), callback_data="set_mode_deep")],
        [InlineKeyboardButton(get_t(lang, "back"), callback_data="back_main")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_langs_keyboard(lang: str):
    keyboard = [
        [InlineKeyboardButton("🇸🇦 العربية", callback_data="set_lang_ar"), InlineKeyboardButton("🇺🇸 English", callback_data="set_lang_en")],
        [InlineKeyboardButton("🇫🇷 Français", callback_data="set_lang_fr"), InlineKeyboardButton("🇩🇪 Deutsch", callback_data="set_lang_de")],
        [InlineKeyboardButton(get_t(lang, "back"), callback_data="back_main")]
    ]
    return InlineKeyboardMarkup(keyboard)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_settings[user_id] = {"mode": "quick", "lang": "en"}
    user_histories[user_id] = []
    
    text = get_t("en", "welcome")
    await update.message.reply_text(text, reply_markup=get_main_keyboard(user_id), parse_mode="Markdown")

async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()

    s = user_settings[user_id]
    data = query.data
    lang = s["lang"]

    if data == "menu_modes":
        await query.message.edit_text(get_t(lang, "select_mode"), reply_markup=get_modes_keyboard(lang), parse_mode="Markdown")
        return
    elif data == "menu_langs":
        await query.message.edit_text(get_t(lang, "select_lang"), reply_markup=get_langs_keyboard(lang), parse_mode="Markdown")
        return
    elif data == "back_main":
        status_text = f"{get_t(lang, 'settings_updated')}\n- Mode: {get_t(lang, s['mode'])}\n- Language: {LANG_NAMES[lang]}\n\n{get_t(lang, 'send_text')}"
        await query.message.edit_text(status_text, reply_markup=get_main_keyboard(user_id), parse_mode="Markdown")
        return
    elif data.startswith("set_mode_"):
        s["mode"] = data.split("_")[2]
    elif data.startswith("set_lang_"):
        s["lang"] = data.split("_")[2]

    new_lang = s["lang"]
    status_text = f"{get_t(new_lang, 'settings_updated')}\n- Mode: {get_t(new_lang, s['mode'])}\n- Language: {LANG_NAMES[new_lang]}\n\n{get_t(new_lang, 'send_text')}"
    await query.message.edit_text(status_text, reply_markup=get_main_keyboard(user_id), parse_mode="Markdown")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    s = user_settings[user_id]

    if is_rate_limited(user_id):
        await update.message.reply_text("⚠️ Rate limit reached.")
        return

    lang_code = s["lang"]
    mode = s["mode"]

    # رسالة اللودينج المؤقتة
    loading_msg = await update.message.reply_text(get_t(lang_code, "loading"), parse_mode="Markdown")

    user_text = update.message.text
    user_histories[user_id].append({"role": "user", "content": user_text})
    if len(user_histories[user_id]) > 10:
        user_histories[user_id] = user_histories[user_id][-10:]

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
        
        # حذف رسالة اللودينج وإرسال النتيجة
        await loading_msg.delete()
        
        if reply:
            user_histories[user_id].append({"role": "assistant", "content": reply})
            await update.message.reply_text(reply, reply_markup=get_main_keyboard(user_id), parse_mode="Markdown")
        else:
            await update.message.reply_text("⚠️ No response generated.", reply_markup=get_main_keyboard(user_id))
    except Exception as e:
        logger.error(f"AI Error: {e}")
        await loading_msg.delete()
        await update.message.reply_text(get_t(lang_code, "error"), reply_markup=get_main_keyboard(user_id))

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

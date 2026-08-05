import os
import time
import logging
import io
import asyncio
from collections import defaultdict
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from g4f.client import Client
import PyPDF2
from docx import Document

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("TELEGRAM_TOKEN")
ADMIN_ID = os.getenv("ADMIN_CHAT_ID")

user_settings = defaultdict(lambda: {"mode": "quick", "lang": "en"})
user_histories = defaultdict(list)
user_message_times = defaultdict(list)
RATE_LIMIT_COUNT = 5
RATE_LIMIT_WINDOW = 10

UI_TEXTS = {
    "en": {
        "welcome": "🤖 **Welcome to the AI Summarizer Bot!** 📄\n\nSend text or documents (PDF, Word, TXT):",
        "mode_btn": "⚙️ Mode",
        "lang_btn": "🌐 Lang",
        "select_mode": "📌 **Select Summary Mode:**",
        "select_lang": "🌐 **Select Output Language:**",
        "back": "🔙 Back",
        "settings_updated": "⚙️ **Settings Updated:**",
        "send_text": "Send your text or document now:",
        "loading": "⏳ **Processing your request, please wait...**",
        "quick": "⚡ Quick Summary",
        "points": "📌 Key Points",
        "deep": "🧠 Deep Analysis",
        "error": "⚠️ The AI service took too long or is temporarily busy. Please try again.",
        "unsupported": "⚠️ Unsupported file format.",
        "photo_not_supported": "⚠️ Images are not supported. Please send text or documents only."
    },
    "ar": {
        "welcome": "🤖 **مرحباً بك في بوت التلخيص الذكي!** 📄\n\nأرسل نصاً أو مستنداً (PDF, Word, TXT):",
        "mode_btn": "⚙️ الوضع",
        "lang_btn": "🌐 اللغة",
        "select_mode": "📌 **اختر نوع التلخيص:**",
        "select_lang": "🌐 **اختر لغة الإخراج:**",
        "back": "🔙 رجوع",
        "settings_updated": "⚙️ **تم تحديث الإعدادات:**",
        "send_text": "أرسل النص أو المستند الآن للتلخيص:",
        "loading": "⏳ **جاري معالجة طلبك، برجاء الانتظار...**",
        "quick": "⚡ تلخيص سريع",
        "points": "📌 نقاط رئيسية",
        "deep": "🧠 تحليل متعمق",
        "error": "⚠️ استغرق خادم الذكاء الاصطناعي وقتاً طويلاً أو الخدمة مضغوطة حالياً. حاول مرة أخرى.",
        "unsupported": "⚠️ صيغة الملف غير مدعومة.",
        "photo_not_supported": "⚠️ الصور غير مدعومة. يرسل النصوص أو المستندات فقط."
    },
    "fr": {
        "welcome": "🤖 **Bienvenue dans le bot de résumé IA!** 📄",
        "mode_btn": "⚙️ Mode",
        "lang_btn": "🌐 Langue",
        "select_mode": "📌 **Sélectionnez le mode de résumé:**",
        "select_lang": "📌 **Sélectionnez la langue de sortie:**",
        "back": "🔙 Retour",
        "settings_updated": "⚙️ **Paramètres mis à jour:**",
        "send_text": "Envoyez votre texte ou document:",
        "loading": "⏳ **Traitement en cours...**",
        "quick": "⚡ Résumé Rapide",
        "points": "📌 Points Clés",
        "deep": "🧠 Analyse Approfondie",
        "error": "⚠️ Le service IA a pris trop de temps. Veuillez réessayer.",
        "unsupported": "⚠️ Format non pris en charge.",
        "photo_not_supported": "⚠️ Images non prises en charge."
    },
    "de": {
        "welcome": "🤖 **Willkommen beim KI-Zusammenfassungs-Bot!** 📄",
        "mode_btn": "⚙️ Modus",
        "lang_btn": "🌐 Sprache",
        "select_mode": "📌 **Wählen Sie den Modus:**",
        "select_lang": "🌐 **Wählen Sie die Sprache:**",
        "back": "🔙 Zurück",
        "settings_updated": "⚙️ **Einstellungen aktualisiert:**",
        "send_text": "Senden Sie Text oder Dokument:",
        "loading": "⏳ **Ihre Anfrage wird bearbeitet...**",
        "quick": "⚡ Schnelle Zusammenfassung",
        "points": "📌 Kernpunkte",
        "deep": "🧠 Tiefenanalyse",
        "error": "⚠️ Der KI-Dienst hat zu lange gedauert. Bitte versuchen Sie es erneut.",
        "unsupported": "⚠️ Nicht unterstütztes Format.",
        "photo_not_supported": "⚠️ Bilder nicht unterstützt."
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
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(get_t(lang, "quick"), callback_data="set_mode_quick")],
        [InlineKeyboardButton(get_t(lang, "points"), callback_data="set_mode_points")],
        [InlineKeyboardButton(get_t(lang, "deep"), callback_data="set_mode_deep")],
        [InlineKeyboardButton(get_t(lang, "back"), callback_data="back_main")]
    ])

def get_langs_keyboard(lang: str):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🇸🇦 العربية", callback_data="set_lang_ar"), InlineKeyboardButton("🇺🇸 English", callback_data="set_lang_en")],
        [InlineKeyboardButton("🇫🇷 Français", callback_data="set_lang_fr"), InlineKeyboardButton("🇩🇪 Deutsch", callback_data="set_lang_de")],
        [InlineKeyboardButton(get_t(lang, "back"), callback_data="back_main")]
    ])

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_settings[user_id] = {"mode": "quick", "lang": "en"}
    user_histories[user_id] = []
    await update.message.reply_text(get_t("en", "welcome"), reply_markup=get_main_keyboard(user_id), parse_mode="Markdown")

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

async def process_content(update: Update, context: ContextTypes.DEFAULT_TYPE, text_content: str):
    user_id = update.effective_user.id
    s = user_settings[user_id]
    lang_code = s["lang"]
    mode = s["mode"]

    if is_rate_limited(user_id):
        await update.message.reply_text("⚠️ Rate limit reached.")
        return

    loading_msg = await update.message.reply_text(get_t(lang_code, "loading"), parse_mode="Markdown")

    user_histories[user_id].append({"role": "user", "content": text_content})
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

    messages = [{"role": "system", "content": system_content}] + user_histories[user_id]

    try:
        def fetch_ai():
            client = Client()
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=messages,
            )
            return response.choices[0].message.content if response and response.choices else None

        # استخدام asyncio.wait_for لضمان عدم التعليق أكثر من 15 ثانية
        reply = await asyncio.wait_for(asyncio.to_thread(fetch_ai), timeout=15.0)
        
        try:
            await loading_msg.delete()
        except Exception:
            pass
        
        if reply:
            user_histories[user_id].append({"role": "assistant", "content": reply})
            await update.message.reply_text(reply, reply_markup=get_main_keyboard(user_id), parse_mode="Markdown")
        else:
            await update.message.reply_text("⚠️ No response generated.", reply_markup=get_main_keyboard(user_id))
            
    except asyncio.TimeoutError:
        logger.error("AI Request Timeout")
        try:
            await loading_msg.delete()
        except Exception:
            pass
        await update.message.reply_text(get_t(lang_code, 'error'), reply_markup=get_main_keyboard(user_id))
    except Exception as e:
        logger.error(f"AI Error: {e}")
        try:
            await loading_msg.delete()
        except Exception:
            pass
        await update.message.reply_text(get_t(lang_code, 'error'), reply_markup=get_main_keyboard(user_id))

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text:
        await process_content(update, context, text)

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    s = user_settings[user_id]
    lang_code = s["lang"]
    
    document = update.message.document
    file_name = document.file_name.lower()
    
    try:
        file_bytes = await document.get_file()
        file_io = io.BytesIO()
        await file_bytes.download_to_memory(file_io)
        file_io.seek(0)
        
        extracted_text = ""
        
        if file_name.endswith('.pdf'):
            reader = PyPDF2.PdfReader(file_io)
            for page in reader.pages:
                t = page.extract_text()
                if t:
                    extracted_text += t + "\n"
        elif file_name.endswith('.docx'):
            doc = Document(file_io)
            for para in doc.paragraphs:
                if para.text:
                    extracted_text += para.text + "\n"
        elif file_name.endswith('.txt'):
            extracted_text = file_io.read().decode('utf-8', errors='ignore')
        else:
            await update.message.reply_text(get_t(lang_code, "unsupported"), reply_markup=get_main_keyboard(user_id))
            return
            
        if extracted_text.strip():
            await process_content(update, context, extracted_text[:4000])
        else:
            await update.message.reply_text("⚠️ Could not extract text from the file.", reply_markup=get_main_keyboard(user_id))
            
    except Exception as e:
        logger.error(f"File reading error: {e}")
        await update.message.reply_text(get_t(lang_code, 'error'), reply_markup=get_main_keyboard(user_id))

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    s = user_settings[user_id]
    lang_code = s["lang"]
    await update.message.reply_text(get_t(lang_code, "photo_not_supported"), reply_markup=get_main_keyboard(user_id))

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
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))

    app.run_polling()

if __name__ == main.__globals__.get('__name__', '__main__'):
    main()

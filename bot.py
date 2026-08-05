import os
import time
import logging
import io
import base64
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
        "welcome": "🤖 **Welcome to the AI Summarizer Bot!** 📄\n\nSend text, documents, or images:",
        "mode_btn": "⚙️ Mode",
        "lang_btn": "🌐 Lang",
        "select_mode": "📌 **Select Summary Mode:**",
        "select_lang": "🌐 **Select Output Language:**",
        "back": "🔙 Back",
        "settings_updated": "⚙️ **Settings Updated:**",
        "send_text": "Send your text, document, or image now:",
        "loading": "⏳ **Processing your request, please wait...**",
        "quick": "⚡ Quick Summary",
        "points": "📌 Key Points",
        "deep": "🧠 Deep Analysis",
        "error": "⚠️ An error occurred while generating the response.",
        "unsupported": "⚠️ Unsupported file format."
    },
    "ar": {
        "welcome": "🤖 **مرحباً بك في بوت التلخيص الذكي!** 📄\n\nأرسل نصاً، أو ملفاً، أو صورة:",
        "mode_btn": "⚙️ الوضع",
        "lang_btn": "🌐 اللغة",
        "select_mode": "📌 **اختر نوع التلخيص:**",
        "select_lang": "🌐 **اختر لغة الإخراج:**",
        "back": "🔙 رجوع",
        "settings_updated": "⚙️ **تم تحديث الإعدادات:**",
        "send_text": "أرسل النص أو المستند أو الصورة الآن للتلخيص:",
        "loading": "⏳ **جاري معالجة طلبك، برجاء الانتظار...**",
        "quick": "⚡ تلخيص سريع",
        "points": "📌 نقاط رئيسية",
        "deep": "🧠 تحليل متعمق",
        "error": "⚠️ حدث خطأ أثناء توليد الرد من الذكاء الاصطناعي.",
        "unsupported": "⚠️ صيغة الملف غير مدعومة."
    },
    "fr": {
        "welcome": "🤖 **Bienvenue dans le bot de résumé IA!** 📄",
        "mode_btn": "⚙️ Mode",
        "lang_btn": "🌐 Langue",
        "select_mode": "📌 **Sélectionnez le mode de résumé:**",
        "select_lang": "📌 **Sélectionnez la langue de sortie:**",
        "back": "🔙 Retour",
        "settings_updated": "⚙️ **Paramètres mis à jour:**",
        "send_text": "Envoyez votre texte, document ou image:",
        "loading": "⏳ **Traitement en cours...**",
        "quick": "⚡ Résumé Rapide",
        "points": "📌 Points Clés",
        "deep": "🧠 Analyse Approfondie",
        "error": "⚠️ Une erreur s'est produite.",
        "unsupported": "⚠️ Format non pris en charge."
    },
    "de": {
        "welcome": "🤖 **Willkommen beim KI-Zusammenfassungs-Bot!** 📄",
        "mode_btn": "⚙️ Modus",
        "lang_btn": "🌐 Sprache",
        "select_mode": "📌 **Wählen Sie den Modus:**",
        "select_lang": "🌐 **Wählen Sie die Sprache:**",
        "back": "🔙 Zurück",
        "settings_updated": "⚙️ **Einstellungen aktualisiert:**",
        "send_text": "Senden Sie Text, Dokument oder Bild:",
        "loading": "⏳ **Ihre Anfrage wird bearbeitet...**",
        "quick": "⚡ Schnelle Zusammenfassung",
        "points": "📌 Kernpunkte",
        "deep": "🧠 Tiefenanalyse",
        "error": "⚠️ Ein Fehler ist aufgetreten.",
        "unsupported": "⚠️ Nicht unterstütztes Format."
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

async def process_content(update: Update, context: ContextTypes.DEFAULT_TYPE, messages_payload):
    user_id = update.effective_user.id
    s = user_settings[user_id]
    lang_code = s["lang"]
    mode = s["mode"]

    if is_rate_limited(user_id):
        await update.message.reply_text("⚠️ Rate limit reached.")
        return

    loading_msg = await update.message.reply_text(get_t(lang_code, "loading"), parse_mode="Markdown")

    if mode == "quick":
        system_content = f"You are a professional text and image summarizer. Read the image or text provided, and give a quick, clear, and concise summary in '{lang_code}' language."
    elif mode == "points":
        system_content = f"You are a professional text and image summarizer. Extract the main key points from the provided image or text in clear bullet points in '{lang_code}' language."
    elif mode == "deep":
        system_content = f"You are an expert analytical assistant. Provide a deep, comprehensive, and detailed analysis of the provided image or text in '{lang_code}' language."
    else:
        system_content = f"You are a professional summarizer. Provide a summary in '{lang_code}' language."

    messages = [{"role": "system", "content": system_content}] + messages_payload

    try:
        client = Client()
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
        )
        reply = response.choices[0].message.content if response and response.choices else None
        
        try:
            await loading_msg.delete()
        except Exception:
            pass
        
        if reply:
            await update.message.reply_text(reply, reply_markup=get_main_keyboard(user_id), parse_mode="Markdown")
        else:
            await update.message.reply_text("⚠️ No response generated.", reply_markup=get_main_keyboard(user_id))
            
    except Exception as e:
        logger.error(f"AI Error: {e}")
        try:
            await loading_msg.delete()
        except Exception:
            pass
        await update.message.reply_text(f"{get_t(lang_code, 'error')}\n`{str(e)}`", reply_markup=get_main_keyboard(user_id), parse_mode="Markdown")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text:
        await process_content(update, context, [{"role": "user", "content": text}])

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    s = user_settings[user_id]
    lang_code = s["lang"]
    
    document = update.message.document
    file_name = document.file_name.lower()
    
    file_bytes = await document.get_file()
    file_io = io.BytesIO()
    await file_bytes.download_to_memory(file_io)
    file_io.seek(0)
    
    extracted_text = ""
    
    try:
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
            await process_content(update, context, [{"role": "user", "content": extracted_text}])
        else:
            await update.message.reply_text("⚠️ Could not extract text from the file.", reply_markup=get_main_keyboard(user_id))
            
    except Exception as e:
        logger.error(f"File reading error: {e}")
        await update.message.reply_text(get_t(lang_code, "error"), reply_markup=get_main_keyboard(user_id))

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    s = user_settings[user_id]
    lang_code = s["lang"]

    photo = update.message.photo[-1]
    photo_file = await photo.get_file()
    
    photo_io = io.BytesIO()
    await photo_file.download_to_memory(photo_io)
    base64_image = base64.b64encode(photo_io.getvalue()).decode('utf-8')

    content_message = {
        "role": "user",
        "content": [
            {"type": "text", "text": "Please read and summarize the text and content inside this image."},
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{base64_image}"
                }
            }
        ]
    }
    
    await process_content(update, context, [content_message])

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

if __name__ == '__main__':
    main()

import os
import time
import logging
import io
import asyncio
from collections import defaultdict
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
import PyPDF2
from docx import Document
from g4f.client import Client

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("TELEGRAM_TOKEN")
g4f_client = Client()

user_settings = defaultdict(lambda: {"mode": "quick", "lang": "en"})

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
        "error": "⚠️ An error occurred while generating the response.",
        "unsupported": "⚠️ Unsupported file format."
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
        "error": "⚠️ حدث خطأ أثناء توليد الرد من الذكاء الاصطناعي.",
        "unsupported": "⚠️ صيغة الملف غير مدعومة."
    }
}

LANG_NAMES = {"en": "🇺🇸 English", "ar": "🇸🇦 العربية"}

def get_t(lang: str, key: str) -> str:
    return UI_TEXTS.get(lang, UI_TEXTS["en"]).get(key, key)

def get_main_keyboard(user_id: int):
    s = user_settings[user_id]
    lang = s['lang']
    mode_label = get_t(lang, s['mode'])
    lang_label = LANG_NAMES.get(lang, "🇺🇸 English")

    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"{get_t(lang, 'mode_btn')}: {mode_label}", callback_data="menu_modes")],
        [InlineKeyboardButton(f"{get_t(lang, 'lang_btn')}: {lang_label}", callback_data="menu_langs")],
    ])

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
        [InlineKeyboardButton(get_t(lang, "back"), callback_data="back_main")]
    ])

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_settings[user_id] = {"mode": "quick", "lang": "en"}
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

def call_ai_free(prompt: str) -> str:
    response = g4f_client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content

async def process_content(update: Update, context: ContextTypes.DEFAULT_TYPE, text_content: str):
    user_id = update.effective_user.id
    s = user_settings[user_id]
    lang_code = s["lang"]
    mode = s["mode"]

    loading_msg = await update.message.reply_text(get_t(lang_code, "loading"), parse_mode="Markdown")

    if mode == "quick":
        instruction = f"Provide a concise summary in '{lang_code}':"
    elif mode == "points":
        instruction = f"Extract key bullet points in '{lang_code}':"
    else:
        instruction = f"Provide a detailed analysis in '{lang_code}':"

    prompt = f"{instruction}\n\n{text_content}"

    try:
        reply = await asyncio.to_thread(call_ai_free, prompt)
        try:
            await loading_msg.delete()
        except Exception:
            pass
        await update.message.reply_text(reply, reply_markup=get_main_keyboard(user_id))
    except Exception as e:
        logger.error(f"Free AI Error: {e}")
        try:
            await loading_msg.delete()
        except Exception:
            pass
        await update.message.reply_text(f"{get_t(lang_code, 'error')}\n\n`{str(e)}`", reply_markup=get_main_keyboard(user_id), parse_mode="Markdown")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text:
        await process_content(update, context, update.message.text)

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
            await update.message.reply_text("⚠️ Could not extract text from file.", reply_markup=get_main_keyboard(user_id))
            
    except Exception as e:
        logger.error(f"File reading error: {e}")
        await update.message.reply_text(get_t(lang_code, 'error'), reply_markup=get_main_keyboard(user_id))

def main():
    if not TELEGRAM_TOKEN:
        logger.critical("TELEGRAM_BOT_TOKEN missing!")
        return

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CallbackQueryHandler(button_click))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))

    app.run_polling()

if __name__ == '__main__':
    main()

#!/usr/bin/env python3
import os
import logging
import requests
import asyncio
from flask import Flask, jsonify
from dotenv import load_dotenv

from telegram import Update
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)

load_dotenv()

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
CUSTOM_API_URL = os.getenv('CUSTOM_API_URL', 'https://hackgpt-backend.onrender.com')
PORT = int(os.getenv('PORT', 10000))

if not TELEGRAM_TOKEN:
    logger.error("ERROR: TELEGRAM_BOT_TOKEN not found!")
    TELEGRAM_TOKEN = "dummy_token"

app = Flask(__name__)
application = None
bot_running = False

SUPPORTED_LANGS = {"en": "English", "hi": "Hindi", "hinglish": "Hinglish"}
SUPPORTED_PERSONAS = ["hackGPT", "DAN", "chatGPT-DEV"]

def build_prompt(user_text: str, lang: str) -> str:
    if lang == "hi":
        return f"Please reply in Hindi (Devanagari).\n\nUser: {user_text}"
    if lang == "hinglish":
        return f"Please reply in Hinglish (mix Hindi + English, Roman script).\n\nUser: {user_text}"
    return f"Please reply in English.\n\nUser: {user_text}"

def get_ai_response_sync(prompt: str, persona: str = "hackGPT") -> str:
    try:
        response = requests.post(
            f"{CUSTOM_API_URL}/chat",
            json={"message": prompt, "persona": persona, "temperature": 0.7, "max_tokens": 2000},
            timeout=30,
        )
        if response.status_code == 200:
            data = response.json()
            return data.get('response') or data.get('answer') or 'No response received'
        return f"API Error {response.status_code}"
    except requests.exceptions.Timeout:
        return "⏱️ Request timeout. Server busy hai."
    except Exception as e:
        logger.error(f"API error: {e}")
        return f"❌ Error: {str(e)[:100]}"

def ensure_defaults(context: ContextTypes.DEFAULT_TYPE):
    context.user_data.setdefault('persona', 'hackGPT')
    context.user_data.setdefault('lang', 'hinglish')

def status_text(context: ContextTypes.DEFAULT_TYPE) -> str:
    ensure_defaults(context)
    persona = context.user_data.get('persona', 'hackGPT')
    lang = context.user_data.get('lang', 'hinglish')
    return f"Current persona: {persona}\nCurrent language: {SUPPORTED_LANGS.get(lang, lang)}"

def main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Persona", callback_data="menu:persona"),
         InlineKeyboardButton("Language", callback_data="menu:lang")],
        [InlineKeyboardButton("Help", callback_data="menu:help"),
         InlineKeyboardButton("Reset", callback_data="menu:reset")],
    ])

def persona_keyboard(current: str) -> InlineKeyboardMarkup:
    rows, row = [], []
    for p in SUPPORTED_PERSONAS:
        text = f"✅ {p}" if p == current else p
        row.append(InlineKeyboardButton(text, callback_data=f"persona:{p}"))
        if len(row) == 2:
            rows.append(row); row = []
    if row: rows.append(row)
    rows.append([InlineKeyboardButton("⬅️ Back", callback_data="menu:main")])
    return InlineKeyboardMarkup(rows)

def lang_keyboard(current: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ English" if current == "en" else "English", callback_data="lang:en"),
         InlineKeyboardButton("✅ Hindi" if current == "hi" else "Hindi", callback_data="lang:hi")],
        [InlineKeyboardButton("✅ Hinglish" if current == "hinglish" else "Hinglish", callback_data="lang:hinglish")],
        [InlineKeyboardButton("⬅️ Back", callback_data="menu:main")],
    ])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user = update.effective_user
        ensure_defaults(context)
        welcome = (
            f"🤖 Welcome {user.first_name}!\n\n"
            "Main HackGPT Bot hu!\n\n"
            "Buttons se settings change karo (persona/language).\n\n"
            f"{status_text(context)}\n\n"
            "Just message karo! 🚀"
        )
        await update.message.reply_text(welcome, reply_markup=main_menu_keyboard())
    except Exception as e:
        logger.error(f"Start error: {e}")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_defaults(context)
    text = (
        "📚 Help\n\n"
        "Commands:\n"
        "/start\n/help\n/persona [hackGPT|DAN|chatGPT-DEV]\n/lang [en|hi|hinglish]\n/reset\n\n"
        "Tip: /start pe buttons milenge."
    )
    await update.message.reply_text(text, reply_markup=main_menu_keyboard())

async def set_persona(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_defaults(context)
    if context.args:
        persona = ' '.join(context.args)
        context.user_data['persona'] = persona
        await update.message.reply_text(f"✅ Persona: {persona}", reply_markup=main_menu_keyboard())
    else:
        current = context.user_data.get('persona', 'hackGPT')
        await update.message.reply_text("Select persona:\n\n" + status_text(context),
                                        reply_markup=persona_keyboard(current))

async def set_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_defaults(context)
    if context.args:
        lang = context.args[0].strip().lower()
        if lang not in SUPPORTED_LANGS:
            await update.message.reply_text("❌ Invalid language. Use: /lang en | hi | hinglish")
            return
        context.user_data['lang'] = lang
        await update.message.reply_text(f"✅ Language set to: {SUPPORTED_LANGS[lang]}",
                                        reply_markup=main_menu_keyboard())
    else:
        current = context.user_data.get('lang', 'hinglish')
        await update.message.reply_text("Select language:\n\n" + status_text(context),
                                        reply_markup=lang_keyboard(current))

async def reset_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_defaults(context)
    persona = context.user_data.get('persona', 'hackGPT')
    lang = context.user_data.get('lang', 'hinglish')
    context.user_data.clear()
    context.user_data['persona'] = persona
    context.user_data['lang'] = lang
    await update.message.reply_text("🔄 Reset!", reply_markup=main_menu_keyboard())

async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_defaults(context)
    q = update.callback_query
    await q.answer()
    data = q.data or ""

    if data == "menu:main":
        await q.edit_message_text("Main menu:\n\n" + status_text(context), reply_markup=main_menu_keyboard()); return
    if data == "menu:persona":
        cur = context.user_data.get('persona', 'hackGPT')
        await q.edit_message_text("Select persona:\n\n" + status_text(context), reply_markup=persona_keyboard(cur)); return
    if data == "menu:lang":
        cur = context.user_data.get('lang', 'hinglish')
        await q.edit_message_text("Select language:\n\n" + status_text(context), reply_markup=lang_keyboard(cur)); return
    if data == "menu:help":
        await q.edit_message_text("📚 Help\n\nUse buttons or commands:\n/start /help /persona /lang /reset\n\n" + status_text(context),
                                  reply_markup=main_menu_keyboard()); return
    if data == "menu:reset":
        persona = context.user_data.get('persona', 'hackGPT')
        lang = context.user_data.get('lang', 'hinglish')
        context.user_data.clear()
        context.user_data['persona'] = persona
        context.user_data['lang'] = lang
        await q.edit_message_text("🔄 Reset done!\n\n" + status_text(context), reply_markup=main_menu_keyboard()); return

    if data.startswith("persona:"):
        p = data.split(":", 1)[1]
        context.user_data['persona'] = p
        await q.edit_message_text(f"✅ Persona set to: {p}\n\n" + status_text(context), reply_markup=main_menu_keyboard()); return

    if data.startswith("lang:"):
        l = data.split(":", 1)[1]
        if l in SUPPORTED_LANGS:
            context.user_data['lang'] = l
            await q.edit_message_text(f"✅ Language set to: {SUPPORTED_LANGS[l]}\n\n" + status_text(context),
                                      reply_markup=main_menu_keyboard())
        else:
            await q.edit_message_text("❌ Invalid language\n\n" + status_text(context), reply_markup=main_menu_keyboard())
        return

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_defaults(context)
    text = update.message.text
    if not text: return
    persona = context.user_data.get('persona', 'hackGPT')
    lang = context.user_data.get('lang', 'hinglish')

    try: await update.message.chat.send_action('typing')
    except: pass

    prompt = build_prompt(text, lang)
    resp = get_ai_response_sync(prompt, persona)

    if len(resp) > 4096:
        for i in range(0, len(resp), 4096):
            await update.message.reply_text(resp[i:i+4096], reply_markup=main_menu_keyboard())
    else:
        await update.message.reply_text(resp, reply_markup=main_menu_keyboard())

async def error_handler(update, context):
    logger.error(f"Error: {context.error}")

async def setup_application():
    global application
    if not TELEGRAM_TOKEN or TELEGRAM_TOKEN == "dummy_token":
        logger.error("TELEGRAM_BOT_TOKEN not configured!")
        return None

    application = Application.builder().token(TELEGRAM_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("persona", set_persona))
    application.add_handler(CommandHandler("lang", set_language))
    application.add_handler(CommandHandler("reset", reset_chat))
    application.add_handler(CallbackQueryHandler(on_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_error_handler(error_handler)
    return application

async def run_polling():
    global application, bot_running
    application = await setup_application()
    if not application: return

    bot_running = True
    await application.initialize()
    await application.start()
    await application.updater.start_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)
    logger.info("✅ Bot polling started!")
    await asyncio.Event().wait()

import threading
def run_bot_in_thread():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(run_polling())

@app.route('/', methods=['GET'])
def index():
    return jsonify({"status": "running" if bot_running else "starting", "message": "HackGPT Bot Active!"}), 200

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"ok": True}), 200

@app.before_request
def startup():
    global bot_thread
    if bot_thread is None:
        bot_thread = threading.Thread(target=run_bot_in_thread, daemon=True)
        bot_thread.start()

bot_thread = None

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=PORT, debug=False, use_reloader=False, threaded=True)
    

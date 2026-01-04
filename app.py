#!/usr/bin/env python3
import os
import logging
import requests
import asyncio
import sqlite3
from datetime import datetime
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

# Admin IDs
ADMIN_IDS = [5451167865, 1529815801]

# Database setup
def init_db():
    conn = sqlite3.connect('bot_users.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        first_name TEXT,
        last_name TEXT,
        join_date TEXT,
        message_count INTEGER DEFAULT 0,
        last_active TEXT,
        is_banned INTEGER DEFAULT 0
    )''')
    conn.commit()
    conn.close()

init_db()

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

def get_db():
    return sqlite3.connect('bot_users.db')

def add_or_update_user(user):
    conn = get_db()
    c = conn.cursor()
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    c.execute('''INSERT OR IGNORE INTO users (user_id, username, first_name, last_name, join_date, last_active)
                 VALUES (?, ?, ?, ?, ?, ?)''',
              (user.id, user.username or '', user.first_name or '', user.last_name or '', now, now))
    c.execute('UPDATE users SET last_active = ?, username = ?, first_name = ?, last_name = ? WHERE user_id = ?',
              (now, user.username or '', user.first_name or '', user.last_name or '', user.id))
    conn.commit()
    conn.close()

def increment_message_count(user_id: int):
    conn = get_db()
    c = conn.cursor()
    c.execute('UPDATE users SET message_count = message_count + 1 WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()

def is_user_banned(user_id: int) -> bool:
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT is_banned FROM users WHERE user_id = ?', (user_id,))
    result = c.fetchone()
    conn.close()
    return result and result[0] == 1

def ban_user(user_id: int):
    conn = get_db()
    c = conn.cursor()
    c.execute('UPDATE users SET is_banned = 1 WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()

def unban_user(user_id: int):
    conn = get_db()
    c = conn.cursor()
    c.execute('UPDATE users SET is_banned = 0 WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()

def get_all_users():
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT user_id, username, first_name, join_date, message_count, last_active, is_banned FROM users')
    users = c.fetchall()
    conn.close()
    return users

def get_user_info(user_id: int):
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT user_id, username, first_name, last_name, join_date, message_count, last_active, is_banned FROM users WHERE user_id = ?', (user_id,))
    user = c.fetchone()
    conn.close()
    return user

def get_stats():
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT COUNT(*) FROM users')
    total_users = c.fetchone()[0]
    c.execute('SELECT COUNT(*) FROM users WHERE is_banned = 0')
    active_users = c.fetchone()[0]
    c.execute('SELECT SUM(message_count) FROM users')
    total_messages = c.fetchone()[0] or 0
    conn.close()
    return total_users, active_users, total_messages

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
        add_or_update_user(user)
        
        if is_user_banned(user.id):
            await update.message.reply_text("❌ You are banned from using this bot.")
            return
            
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
    user = update.effective_user
    if is_user_banned(user.id):
        await update.message.reply_text("❌ You are banned from using this bot.")
        return
        
    ensure_defaults(context)
    text = (
        "📚 Help\n\n"
        "Commands:\n"
        "/start\n/help\n/persona [hackGPT|DAN|chatGPT-DEV]\n/lang [en|hi|hinglish]\n/reset\n\n"
        "Tip: /start pe buttons milenge."
    )
    if is_admin(user.id):
        text += "\n\n🔑 Admin Commands:\n/adminstats\n/userlist\n/userinfo <user_id>\n/broadcast <message>\n/ban <user_id>\n/unban <user_id>"
    await update.message.reply_text(text, reply_markup=main_menu_keyboard())

async def set_persona(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if is_user_banned(user.id):
        await update.message.reply_text("❌ You are banned from using this bot.")
        return
        
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
    user = update.effective_user
    if is_user_banned(user.id):
        await update.message.reply_text("❌ You are banned from using this bot.")
        return
        
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
    user = update.effective_user
    if is_user_banned(user.id):
        await update.message.reply_text("❌ You are banned from using this bot.")
        return
        
    ensure_defaults(context)
    persona = context.user_data.get('persona', 'hackGPT')
    lang = context.user_data.get('lang', 'hinglish')
    context.user_data.clear()
    context.user_data['persona'] = persona
    context.user_data['lang'] = lang
    await update.message.reply_text("🔄 Reset!", reply_markup=main_menu_keyboard())

# Admin commands
async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id):
        await update.message.reply_text("❌ Admin access required.")
        return
    
    total, active, messages = get_stats()
    text = (
        "📊 Bot Statistics\n\n"
        f"👥 Total Users: {total}\n"
        f"✅ Active Users: {active}\n"
        f"🚫 Banned Users: {total - active}\n"
        f"💬 Total Messages: {messages}"
    )
    await update.message.reply_text(text)

async def user_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id):
        await update.message.reply_text("❌ Admin access required.")
        return
    
    users = get_all_users()
    if not users:
        await update.message.reply_text("👥 No users yet.")
        return
    
    text = "👥 User List\n\n"
    for u in users[:20]:  # First 20 users
        status = "🚫" if u[6] else "✅"
        text += f"{status} {u[0]} - {u[2]} (@{u[1] or 'none'})\nJoined: {u[3]}\nMessages: {u[4]}\n\n"
    
    if len(users) > 20:
        text += f"... and {len(users) - 20} more users."
    
    await update.message.reply_text(text)

async def user_info_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id):
        await update.message.reply_text("❌ Admin access required.")
        return
    
    if not context.args:
        await update.message.reply_text("❌ Usage: /userinfo <user_id>")
        return
    
    try:
        target_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ Invalid user ID.")
        return
    
    info = get_user_info(target_id)
    if not info:
        await update.message.reply_text("❌ User not found.")
        return
    
    text = (
        f"👤 User Info\n\n"
        f"ID: {info[0]}\n"
        f"Username: @{info[1] or 'none'}\n"
        f"Name: {info[2]} {info[3] or ''}\n"
        f"Joined: {info[4]}\n"
        f"Messages: {info[5]}\n"
        f"Last Active: {info[6]}\n"
        f"Status: {'Banned' if info[7] else 'Active'}"
    )
    await update.message.reply_text(text)

async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id):
        await update.message.reply_text("❌ Admin access required.")
        return
    
    if not context.args:
        await update.message.reply_text("❌ Usage: /broadcast <message>")
        return
    
    message = ' '.join(context.args)
    users = get_all_users()
    success = 0
    failed = 0
    
    for u in users:
        if u[6] == 0:  # Not banned
            try:
                await context.bot.send_message(chat_id=u[0], text=f"📢 Broadcast\n\n{message}")
                success += 1
            except Exception as e:
                logger.error(f"Broadcast error for {u[0]}: {e}")
                failed += 1
    
    await update.message.reply_text(f"✅ Broadcast sent!\nSuccess: {success}\nFailed: {failed}")

async def ban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id):
        await update.message.reply_text("❌ Admin access required.")
        return
    
    if not context.args:
        await update.message.reply_text("❌ Usage: /ban <user_id>")
        return
    
    try:
        target_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ Invalid user ID.")
        return
    
    if target_id in ADMIN_IDS:
        await update.message.reply_text("❌ Cannot ban admin.")
        return
    
    ban_user(target_id)
    await update.message.reply_text(f"✅ User {target_id} banned.")

async def unban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id):
        await update.message.reply_text("❌ Admin access required.")
        return
    
    if not context.args:
        await update.message.reply_text("❌ Usage: /unban <user_id>")
        return
    
    try:
        target_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ Invalid user ID.")
        return
    
    unban_user(target_id)
    await update.message.reply_text(f"✅ User {target_id} unbanned.")

async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.callback_query.from_user
    if is_user_banned(user.id):
        await update.callback_query.answer("❌ You are banned.", show_alert=True)
        return
        
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
    user = update.effective_user
    add_or_update_user(user)
    
    if is_user_banned(user.id):
        await update.message.reply_text("❌ You are banned from using this bot.")
        return
    
    increment_message_count(user.id)
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
    
    # Admin commands
    application.add_handler(CommandHandler("adminstats", admin_stats))
    application.add_handler(CommandHandler("userlist", user_list))
    application.add_handler(CommandHandler("userinfo", user_info_command))
    application.add_handler(CommandHandler("broadcast", broadcast_command))
    application.add_handler(CommandHandler("ban", ban_command))
    application.add_handler(CommandHandler("unban", unban_command))
    
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

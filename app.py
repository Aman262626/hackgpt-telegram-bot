#!/usr/bin/env python3
import os
import logging
import requests
from datetime import datetime
from flask import Flask, request, jsonify
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
DATABASE_URL = os.getenv('DATABASE_URL')
PORT = int(os.getenv('PORT', 10000))
WEBHOOK_URL = os.getenv('WEBHOOK_URL', 'https://hackgpt-telegram-bot.onrender.com')

if not TELEGRAM_TOKEN:
    logger.error("ERROR: TELEGRAM_BOT_TOKEN not found!")
    TELEGRAM_TOKEN = "dummy_token"

app = Flask(__name__)
application = None

SUPPORTED_LANGS = {"en": "English", "hi": "Hindi", "hinglish": "Hinglish"}
SUPPORTED_PERSONAS = ["hackGPT", "DAN", "chatGPT-DEV"]

ADMIN_IDS = [5451167865, 1529815801]

USE_POSTGRES = False

try:
    if DATABASE_URL and DATABASE_URL.startswith('postgres'):
        import psycopg2
        from psycopg2.extras import RealDictCursor
        USE_POSTGRES = True
        logger.info("Using PostgreSQL database")
        
        def get_db():
            return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
        
        def init_db():
            conn = get_db()
            c = conn.cursor()
            c.execute('''CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                join_date TIMESTAMP,
                message_count INTEGER DEFAULT 0,
                last_active TIMESTAMP,
                is_banned INTEGER DEFAULT 0
            )''')
            conn.commit()
            conn.close()
except Exception as e:
    logger.warning(f"PostgreSQL setup failed: {e}. Falling back to SQLite.")
    USE_POSTGRES = False

if not USE_POSTGRES:
    import sqlite3
    logger.info("Using SQLite database")
    
    def get_db():
        return sqlite3.connect('bot_users.db')
    
    def init_db():
        conn = get_db()
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

def add_or_update_user(user):
    conn = get_db()
    c = conn.cursor()
    now = datetime.now()
    
    if USE_POSTGRES:
        c.execute('''INSERT INTO users (user_id, username, first_name, last_name, join_date, last_active)
                     VALUES (%s, %s, %s, %s, %s, %s)
                     ON CONFLICT (user_id) DO UPDATE
                     SET last_active = %s, username = %s, first_name = %s, last_name = %s''',
                  (user.id, user.username or '', user.first_name or '', user.last_name or '', now, now,
                   now, user.username or '', user.first_name or '', user.last_name or ''))
    else:
        now_str = now.strftime('%Y-%m-%d %H:%M:%S')
        c.execute('''INSERT OR IGNORE INTO users (user_id, username, first_name, last_name, join_date, last_active)
                     VALUES (?, ?, ?, ?, ?, ?)''',
                  (user.id, user.username or '', user.first_name or '', user.last_name or '', now_str, now_str))
        c.execute('UPDATE users SET last_active = ?, username = ?, first_name = ?, last_name = ? WHERE user_id = ?',
                  (now_str, user.username or '', user.first_name or '', user.last_name or '', user.id))
    
    conn.commit()
    conn.close()

def increment_message_count(user_id: int):
    conn = get_db()
    c = conn.cursor()
    if USE_POSTGRES:
        c.execute('UPDATE users SET message_count = message_count + 1 WHERE user_id = %s', (user_id,))
    else:
        c.execute('UPDATE users SET message_count = message_count + 1 WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()

def is_user_banned(user_id: int) -> bool:
    conn = get_db()
    c = conn.cursor()
    if USE_POSTGRES:
        c.execute('SELECT is_banned FROM users WHERE user_id = %s', (user_id,))
        result = c.fetchone()
        conn.close()
        return result and result['is_banned'] == 1
    else:
        c.execute('SELECT is_banned FROM users WHERE user_id = ?', (user_id,))
        result = c.fetchone()
        conn.close()
        return result and result[0] == 1

def ban_user(user_id: int):
    conn = get_db()
    c = conn.cursor()
    if USE_POSTGRES:
        c.execute('UPDATE users SET is_banned = 1 WHERE user_id = %s', (user_id,))
    else:
        c.execute('UPDATE users SET is_banned = 1 WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()

def unban_user(user_id: int):
    conn = get_db()
    c = conn.cursor()
    if USE_POSTGRES:
        c.execute('UPDATE users SET is_banned = 0 WHERE user_id = %s', (user_id,))
    else:
        c.execute('UPDATE users SET is_banned = 0 WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()

def get_all_users():
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT user_id, username, first_name, join_date, message_count, last_active, is_banned FROM users')
    users = c.fetchall()
    conn.close()
    
    if USE_POSTGRES:
        return [(u['user_id'], u['username'], u['first_name'], str(u['join_date']), u['message_count'], str(u['last_active']), u['is_banned']) for u in users]
    return users

def get_user_info(user_id: int):
    conn = get_db()
    c = conn.cursor()
    if USE_POSTGRES:
        c.execute('SELECT user_id, username, first_name, last_name, join_date, message_count, last_active, is_banned FROM users WHERE user_id = %s', (user_id,))
        user = c.fetchone()
        conn.close()
        if user:
            return (user['user_id'], user['username'], user['first_name'], user['last_name'], str(user['join_date']), user['message_count'], str(user['last_active']), user['is_banned'])
        return None
    else:
        c.execute('SELECT user_id, username, first_name, last_name, join_date, message_count, last_active, is_banned FROM users WHERE user_id = ?', (user_id,))
        user = c.fetchone()
        conn.close()
        return user

def get_stats():
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT COUNT(*) as total FROM users')
    total_users = c.fetchone()
    c.execute('SELECT COUNT(*) as active FROM users WHERE is_banned = 0')
    active_users = c.fetchone()
    c.execute('SELECT SUM(message_count) as total_msgs FROM users')
    total_messages = c.fetchone()
    conn.close()
    
    if USE_POSTGRES:
        return total_users['total'], active_users['active'], total_messages['total_msgs'] or 0
    return total_users[0], active_users[0], total_messages[0] or 0

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
        return "Request timeout. Server busy hai."
    except Exception as e:
        logger.error(f"API error: {e}")
        return f"Error: {str(e)[:100]}"

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
            await update.message.reply_text("You are banned from using this bot.")
            return
            
        ensure_defaults(context)
        welcome = (
            f"Welcome {user.first_name}!\n\n"
            "Main HackGPT Bot hu!\n\n"
            "Buttons se settings change karo.\n\n"
            f"{status_text(context)}\n\n"
            "Just message karo!"
        )
        await update.message.reply_text(welcome, reply_markup=main_menu_keyboard())
    except Exception as e:
        logger.error(f"Start error: {e}")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if is_user_banned(user.id):
        await update.message.reply_text("You are banned.")
        return
        
    ensure_defaults(context)
    text = "Help\n\nCommands:\n/start\n/help\n/persona\n/lang\n/reset"
    if is_admin(user.id):
        text += "\n\nAdmin:\n/adminstats\n/userlist\n/userinfo\n/broadcast\n/ban\n/unban"
    await update.message.reply_text(text, reply_markup=main_menu_keyboard())

async def set_persona(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if is_user_banned(user.id):
        await update.message.reply_text("You are banned.")
        return
        
    ensure_defaults(context)
    if context.args:
        persona = ' '.join(context.args)
        context.user_data['persona'] = persona
        await update.message.reply_text(f"Persona: {persona}", reply_markup=main_menu_keyboard())
    else:
        current = context.user_data.get('persona', 'hackGPT')
        await update.message.reply_text("Select persona:\n\n" + status_text(context),
                                        reply_markup=persona_keyboard(current))

async def set_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if is_user_banned(user.id):
        await update.message.reply_text("You are banned.")
        return
        
    ensure_defaults(context)
    if context.args:
        lang = context.args[0].strip().lower()
        if lang not in SUPPORTED_LANGS:
            await update.message.reply_text("Invalid language")
            return
        context.user_data['lang'] = lang
        await update.message.reply_text(f"Language: {SUPPORTED_LANGS[lang]}",
                                        reply_markup=main_menu_keyboard())
    else:
        current = context.user_data.get('lang', 'hinglish')
        await update.message.reply_text("Select language:\n\n" + status_text(context),
                                        reply_markup=lang_keyboard(current))

async def reset_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if is_user_banned(user.id):
        await update.message.reply_text("You are banned.")
        return
        
    ensure_defaults(context)
    persona = context.user_data.get('persona', 'hackGPT')
    lang = context.user_data.get('lang', 'hinglish')
    context.user_data.clear()
    context.user_data['persona'] = persona
    context.user_data['lang'] = lang
    await update.message.reply_text("Reset!", reply_markup=main_menu_keyboard())

async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id):
        await update.message.reply_text("Admin access required.")
        return
    
    total, active, messages = get_stats()
    db_type = "PostgreSQL" if USE_POSTGRES else "SQLite"
    text = (
        f"Bot Statistics ({db_type})\n\n"
        f"Total Users: {total}\n"
        f"Active Users: {active}\n"
        f"Banned Users: {total - active}\n"
        f"Total Messages: {messages}"
    )
    await update.message.reply_text(text)

async def user_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id):
        await update.message.reply_text("Admin access required.")
        return
    
    users = get_all_users()
    if not users:
        await update.message.reply_text("No users yet.")
        return
    
    text = "User List\n\n"
    for u in users[:20]:
        status = "Banned" if u[6] else "Active"
        text += f"{status} {u[0]} - {u[2]} (@{u[1] or 'none'})\nJoined: {u[3]}\nMessages: {u[4]}\n\n"
    
    if len(users) > 20:
        text += f"... and {len(users) - 20} more users."
    
    await update.message.reply_text(text)

async def user_info_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id):
        await update.message.reply_text("Admin access required.")
        return
    
    if not context.args:
        await update.message.reply_text("Usage: /userinfo <user_id>")
        return
    
    try:
        target_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Invalid user ID.")
        return
    
    info = get_user_info(target_id)
    if not info:
        await update.message.reply_text("User not found.")
        return
    
    text = (
        f"User Info\n\n"
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
        await update.message.reply_text("Admin access required.")
        return
    
    if not context.args:
        await update.message.reply_text("Usage: /broadcast <message>")
        return
    
    message = ' '.join(context.args)
    users = get_all_users()
    success = 0
    failed = 0
    
    for u in users:
        if u[6] == 0:
            try:
                await context.bot.send_message(chat_id=u[0], text=f"Broadcast\n\n{message}")
                success += 1
            except Exception as e:
                logger.error(f"Broadcast error for {u[0]}: {e}")
                failed += 1
    
    await update.message.reply_text(f"Broadcast sent!\nSuccess: {success}\nFailed: {failed}")

async def ban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id):
        await update.message.reply_text("Admin access required.")
        return
    
    if not context.args:
        await update.message.reply_text("Usage: /ban <user_id>")
        return
    
    try:
        target_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Invalid user ID.")
        return
    
    if target_id in ADMIN_IDS:
        await update.message.reply_text("Cannot ban admin.")
        return
    
    ban_user(target_id)
    await update.message.reply_text(f"User {target_id} banned.")

async def unban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id):
        await update.message.reply_text("Admin access required.")
        return
    
    if not context.args:
        await update.message.reply_text("Usage: /unban <user_id>")
        return
    
    try:
        target_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Invalid user ID.")
        return
    
    unban_user(target_id)
    await update.message.reply_text(f"User {target_id} unbanned.")

async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.callback_query.from_user
    if is_user_banned(user.id):
        await update.callback_query.answer("You are banned.", show_alert=True)
        return
        
    ensure_defaults(context)
    q = update.callback_query
    await q.answer()
    data = q.data or ""

    if data == "menu:main":
        await q.edit_message_text("Main menu:\n\n" + status_text(context), reply_markup=main_menu_keyboard())
        return
    if data == "menu:persona":
        cur = context.user_data.get('persona', 'hackGPT')
        await q.edit_message_text("Select persona:\n\n" + status_text(context), reply_markup=persona_keyboard(cur))
        return
    if data == "menu:lang":
        cur = context.user_data.get('lang', 'hinglish')
        await q.edit_message_text("Select language:\n\n" + status_text(context), reply_markup=lang_keyboard(cur))
        return
    if data == "menu:help":
        await q.edit_message_text("Help\n\nUse buttons or commands" + status_text(context), reply_markup=main_menu_keyboard())
        return
    if data == "menu:reset":
        persona = context.user_data.get('persona', 'hackGPT')
        lang = context.user_data.get('lang', 'hinglish')
        context.user_data.clear()
        context.user_data['persona'] = persona
        context.user_data['lang'] = lang
        await q.edit_message_text("Reset done!\n\n" + status_text(context), reply_markup=main_menu_keyboard())
        return

    if data.startswith("persona:"):
        p = data.split(":", 1)[1]
        context.user_data['persona'] = p
        await q.edit_message_text(f"Persona set to: {p}\n\n" + status_text(context), reply_markup=main_menu_keyboard())
        return

    if data.startswith("lang:"):
        l = data.split(":", 1)[1]
        if l in SUPPORTED_LANGS:
            context.user_data['lang'] = l
            await q.edit_message_text(f"Language set to: {SUPPORTED_LANGS[l]}\n\n" + status_text(context), reply_markup=main_menu_keyboard())
        else:
            await q.edit_message_text("Invalid language\n\n" + status_text(context), reply_markup=main_menu_keyboard())
        return

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    add_or_update_user(user)
    
    if is_user_banned(user.id):
        await update.message.reply_text("You are banned.")
        return
    
    increment_message_count(user.id)
    ensure_defaults(context)
    text = update.message.text
    if not text:
        return
    persona = context.user_data.get('persona', 'hackGPT')
    lang = context.user_data.get('lang', 'hinglish')

    try:
        await update.message.chat.send_action('typing')
    except:
        pass

    prompt = build_prompt(text, lang)
    resp = get_ai_response_sync(prompt, persona)

    if len(resp) > 4096:
        for i in range(0, len(resp), 4096):
            await update.message.reply_text(resp[i:i+4096], reply_markup=main_menu_keyboard())
    else:
        await update.message.reply_text(resp, reply_markup=main_menu_keyboard())

async def error_handler(update, context):
    logger.error(f"Error: {context.error}")

def setup_application():
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

@app.route('/', methods=['GET'])
def index():
    return jsonify({"status": "active", "message": "HackGPT Bot is running!"}), 200

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"ok": True}), 200

@app.route(f'/{TELEGRAM_TOKEN}', methods=['POST'])
async def webhook():
    if application is None:
        return jsonify({"error": "Bot not initialized"}), 503
    
    try:
        update = Update.de_json(request.get_json(force=True), application.bot)
        await application.process_update(update)
        return jsonify({"ok": True}), 200
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    setup_application()
    if application:
        import asyncio
        async def set_webhook():
            webhook_url = f"{WEBHOOK_URL}/{TELEGRAM_TOKEN}"
            await application.bot.set_webhook(url=webhook_url)
            logger.info(f"Webhook set to: {webhook_url}")
        
        asyncio.run(set_webhook())
    
    app.run(host='0.0.0.0', port=PORT, debug=False)

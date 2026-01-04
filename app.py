#!/usr/bin/env python3
import os
import logging
import requests
import asyncio
from datetime import datetime
from flask import Flask, jsonify
from dotenv import load_dotenv
import threading

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

# Import bot manager
import bot_manager
from complete_integration import setup_complete_integration, handle_start_with_tracking

load_dotenv()

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
CUSTOM_API_URL = os.getenv('CUSTOM_API_URL', 'https://claude-opus-chatbot.onrender.com')
DATABASE_URL = os.getenv('DATABASE_URL')
PORT = int(os.getenv('PORT', 10000))

if not TELEGRAM_TOKEN:
    logger.error("ERROR: TELEGRAM_BOT_TOKEN not found!")
    TELEGRAM_TOKEN = "dummy_token"

app = Flask(__name__)
application = None
bot_running = False

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
bot_manager.init_client_bots_db()

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

def get_ai_response_sync(prompt: str, persona: str = "hackGPT", user_id: int = None) -> str:
    """
    Updated to use Claude Opus API
    API: https://claude-opus-chatbot.onrender.com
    Features: conversation memory, multi-language, real-time data
    """
    try:
        # Create conversation ID for memory feature
        conv_id = f"telegram_user_{user_id}" if user_id else None
        
        # Prepare request payload for Claude API
        payload = {
            "message": prompt,
            "conversation_id": conv_id,
            "use_memory": True if conv_id else False
        }
        
        logger.info(f"Sending request to Claude API: {CUSTOM_API_URL}/chat")
        response = requests.post(
            f"{CUSTOM_API_URL}/chat",
            json=payload,
            timeout=45,  # Increased timeout for Claude API
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 200:
            data = response.json()
            # Claude API returns 'response' field
            return data.get('response') or data.get('answer') or 'No response received from AI'
        else:
            logger.error(f"API Error {response.status_code}: {response.text}")
            return f"❌ API Error {response.status_code}. Please try again."
    
    except requests.exceptions.Timeout:
        logger.error("Claude API timeout")
        return "⏱️ Request timeout. Claude API busy hai, please try again."
    except requests.exceptions.ConnectionError:
        logger.error("Claude API connection error")
        return "🔌 Connection error. API server se connect nahi ho paya."
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return f"❌ Error: {str(e)[:100]}"

def ensure_defaults(context: ContextTypes.DEFAULT_TYPE):
    context.user_data.setdefault('persona', 'hackGPT')
    context.user_data.setdefault('lang', 'hinglish')

def status_text(context: ContextTypes.DEFAULT_TYPE) -> str:
    ensure_defaults(context)
    persona = context.user_data.get('persona', 'hackGPT')
    lang = context.user_data.get('lang', 'hinglish')
    return f"Current persona: {persona}\nCurrent language: {SUPPORTED_LANGS.get(lang, lang)}\n\n🤖 Powered by Claude Opus AI"

def main_menu_keyboard(is_admin_user: bool = False) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton("Persona", callback_data="menu:persona"),
         InlineKeyboardButton("Language", callback_data="menu:lang")],
        [InlineKeyboardButton("Help", callback_data="menu:help"),
         InlineKeyboardButton("Reset", callback_data="menu:reset")],
    ]
    if is_admin_user:
        buttons.append([InlineKeyboardButton("🔧 Admin Panel", callback_data="menu:admin")])
    return InlineKeyboardMarkup(buttons)

def admin_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 Statistics", callback_data="admin:stats"),
         InlineKeyboardButton("👥 User List", callback_data="admin:users")],
        [InlineKeyboardButton("🤖 Client Bots", callback_data="admin:clientbots")],
        [InlineKeyboardButton("⬅️ Back", callback_data="menu:main")],
    ])

def client_bots_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Add Bot", callback_data="clientbots:addbot")],
        [InlineKeyboardButton("📊 Bot Stats", callback_data="clientbots:stats"),
         InlineKeyboardButton("📋 Bot List", callback_data="clientbots:list")],
        [InlineKeyboardButton("⏳ Pending Approvals", callback_data="clientbots:pending")],
        [InlineKeyboardButton("⬅️ Back", callback_data="menu:admin")],
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
        await handle_start_with_tracking(update, context)
        add_or_update_user(user)

        if is_user_banned(user.id):
            await update.message.reply_text("You are banned.")
            return
            
        ensure_defaults(context)
        welcome = (
            f"🎉 Welcome {user.first_name}!\n\n"
            "🤖 Main HackGPT Bot hu, powered by Claude Opus AI!\n\n"
            "✨ Features:\n"
            "• Intelligent conversations with memory\n"
            "• Multi-language support\n"
            "• Real-time information\n\n"
            "Buttons se settings change karo.\n\n"
            f"{status_text(context)}\n\n"
            "💬 Just message karo aur main respond karunga!"
        )
        await update.message.reply_text(welcome, reply_markup=main_menu_keyboard(is_admin(user.id)))
    except Exception as e:
        logger.error(f"Start error: {e}")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if is_user_banned(user.id):
        await update.message.reply_text("You are banned.")
        return
        
    ensure_defaults(context)
    text = (
        "📖 Help - Claude Opus Bot\n\n"
        "Commands:\n"
        "/start - Start bot\n"
        "/help - Show help\n"
        "/persona - Change persona\n"
        "/lang - Change language\n"
        "/reset - Reset chat\n\n"
        "🤖 AI Features:\n"
        "• Conversation memory\n"
        "• Multi-language support\n"
        "• Real-time information\n"
        "• Natural conversations"
    )
    if is_admin(user.id):
        text += (
            "\n\n🔧 Admin Commands:\n"
            "/adminstats - Bot statistics\n"
            "/userlist - All users\n"
            "/userinfo <id> - User details\n"
            "/broadcast <msg> - Send to all\n"
            "/ban <id> - Ban user\n"
            "/unban <id> - Unban user\n"
            "\n🤖 Multi-Bot Management:\n"
            "/addbot <token> - Add client bot\n"
            "/listbots - List all client bots\n"
            "/approvebot <id> - Approve bot\n"
            "/enablebot <id> - Enable bot\n"
            "/disablebot <id> - Disable bot\n"
            "/deletebot <id> - Delete bot\n"
            "/botinfo <id> - Bot details"
        )
    await update.message.reply_text(text, reply_markup=main_menu_keyboard(is_admin(user.id)))

async def set_persona(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if is_user_banned(user.id):
        await update.message.reply_text("You are banned.")
        return
        
    ensure_defaults(context)
    if context.args:
        persona = ' '.join(context.args)
        context.user_data['persona'] = persona
        await update.message.reply_text(f"✅ Persona set: {persona}", reply_markup=main_menu_keyboard(is_admin(user.id)))
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
            await update.message.reply_text("❌ Invalid language")
            return
        context.user_data['lang'] = lang
        await update.message.reply_text(f"✅ Language set: {SUPPORTED_LANGS[lang]}",
                                        reply_markup=main_menu_keyboard(is_admin(user.id)))
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
    await update.message.reply_text("✅ Chat reset! Conversation memory cleared.", reply_markup=main_menu_keyboard(is_admin(user.id)))

async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id):
        await update.message.reply_text("Admin access required.")
        return
    
    total, active, messages = get_stats()
    db_type = "PostgreSQL" if USE_POSTGRES else "SQLite"
    text = (
        f"📊 Bot Statistics ({db_type})\n\n"
        f"👥 Total Users: {total}\n"
        f"✅ Active Users: {active}\n"
        f"🚫 Banned Users: {total - active}\n"
        f"💬 Total Messages: {messages}\n\n"
        f"🤖 AI: Claude Opus\n"
        f"🌐 API: claude-opus-chatbot.onrender.com"
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
    
    text = "👥 User List\n\n"
    for u in users[:20]:
        status = "🚫" if u[6] else "✅"
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
        f"👤 User Info\n\n"
        f"ID: {info[0]}\n"
        f"Username: @{info[1] or 'none'}\n"
        f"Name: {info[2]} {info[3] or ''}\n"
        f"Joined: {info[4]}\n"
        f"Messages: {info[5]}\n"
        f"Last Active: {info[6]}\n"
        f"Status: {'🚫 Banned' if info[7] else '✅ Active'}"
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
                await context.bot.send_message(chat_id=u[0], text=f"📢 Broadcast\n\n{message}")
                success += 1
            except Exception as e:
                logger.error(f"Broadcast error for {u[0]}: {e}")
                failed += 1
    
    await update.message.reply_text(f"✅ Broadcast sent!\nSuccess: {success}\nFailed: {failed}")

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
    await update.message.reply_text(f"🚫 User {target_id} banned.")

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
    await update.message.reply_text(f"✅ User {target_id} unbanned.")

# ========== MULTI-BOT MANAGEMENT COMMANDS ==========

async def addbot_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id):
        await update.message.reply_text("Admin access required.")
        return
    
    if not context.args:
        await update.message.reply_text("Usage: /addbot <bot_token>\n\nExample:\n/addbot 123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11")
        return
    
    bot_token = context.args[0].strip()
    success, message, bot_id = bot_manager.add_client_bot_request(
        bot_token, user.id, user.username or 'none', user.first_name
    )
    
    if success:
        await update.message.reply_text(f"✅ {message}\nBot ID: {bot_id}\n\nUse /approvebot {bot_id} to approve and activate.")
    else:
        await update.message.reply_text(f"❌ {message}")

async def listbots_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id):
        await update.message.reply_text("Admin access required.")
        return
    
    bots = bot_manager.get_all_client_bots()
    if not bots:
        await update.message.reply_text("🤖 No client bots registered yet.")
        return
    
    text = "🤖 Client Bots List\n\n"
    for b in bots[:15]:
        status = "✅" if b[5] else "❌"
        approved = "✔️" if b[6] else "⏳"
        running = "🟢" if bot_manager.is_bot_running(b[0]) else "🔴"
        text += f"{running} {status} Bot ID: {b[0]}\n@{b[1]} ({b[2]})\nOwner: {b[4]} (@{b[3]})\nApproved: {approved} | Users: {b[7]} | Msgs: {b[8]}\n\n"
    
    if len(bots) > 15:
        text += f"... and {len(bots) - 15} more bots."
    
    await update.message.reply_text(text)

async def approvebot_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id):
        await update.message.reply_text("Admin access required.")
        return
    
    if not context.args:
        await update.message.reply_text("Usage: /approvebot <bot_id>")
        return
    
    try:
        bot_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Invalid bot ID.")
        return
    
    success, message = bot_manager.approve_client_bot(bot_id)
    if success:
        await update.message.reply_text(f"✅ {message}\n\nUse /enablebot {bot_id} to start the bot.")
    else:
        await update.message.reply_text(f"❌ {message}")

async def enablebot_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id):
        await update.message.reply_text("Admin access required.")
        return
    
    if not context.args:
        await update.message.reply_text("Usage: /enablebot <bot_id>")
        return
    
    try:
        bot_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Invalid bot ID.")
        return
    
    # Enable in database
    success, message = bot_manager.enable_client_bot(bot_id)
    if not success:
        await update.message.reply_text(f"❌ {message}")
        return
    
    # Start the bot
    bot_data = bot_manager.get_client_bot(bot_id)
    if not bot_data:
        await update.message.reply_text("❌ Bot not found")
        return
    
    await update.message.reply_text("⏳ Starting bot...")
    
    def setup_client_handlers(app, client_bot_id):
        """Setup handlers for client bot"""
        # Same handlers as main bot but for client
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("help", help_command))
        app.add_handler(CommandHandler("persona", set_persona))
        app.add_handler(CommandHandler("lang", set_language))
        app.add_handler(CommandHandler("reset", reset_chat))
        app.add_handler(CallbackQueryHandler(on_callback))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        app.add_error_handler(error_handler)
    
    success, msg = await bot_manager.start_client_bot(bot_id, bot_data['bot_token'], setup_client_handlers)
    if success:
        await update.message.reply_text(f"✅ Bot @{bot_data['bot_username']} is now running!")
    else:
        await update.message.reply_text(f"❌ Failed to start bot: {msg}")

async def disablebot_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id):
        await update.message.reply_text("Admin access required.")
        return
    
    if not context.args:
        await update.message.reply_text("Usage: /disablebot <bot_id>")
        return
    
    try:
        bot_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Invalid bot ID.")
        return
    
    # Stop the bot if running
    if bot_manager.is_bot_running(bot_id):
        await update.message.reply_text("⏳ Stopping bot...")
        success, msg = await bot_manager.stop_client_bot(bot_id)
        if not success:
            await update.message.reply_text(f"⚠️ Warning: {msg}")
    
    # Disable in database
    success, message = bot_manager.disable_client_bot(bot_id)
    if success:
        await update.message.reply_text(f"✅ {message}")
    else:
        await update.message.reply_text(f"❌ {message}")

async def deletebot_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id):
        await update.message.reply_text("Admin access required.")
        return
    
    if not context.args:
        await update.message.reply_text("Usage: /deletebot <bot_id>")
        return
    
    try:
        bot_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Invalid bot ID.")
        return
    
    # Stop if running
    if bot_manager.is_bot_running(bot_id):
        await bot_manager.stop_client_bot(bot_id)
    
    # Delete from database
    success, message = bot_manager.delete_client_bot(bot_id)
    if success:
        await update.message.reply_text(f"✅ {message}")
    else:
        await update.message.reply_text(f"❌ {message}")

async def botinfo_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id):
        await update.message.reply_text("Admin access required.")
        return
    
    if not context.args:
        await update.message.reply_text("Usage: /botinfo <bot_id>")
        return
    
    try:
        bot_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Invalid bot ID.")
        return
    
    bot_data = bot_manager.get_client_bot(bot_id)
    if not bot_data:
        await update.message.reply_text("❌ Bot not found")
        return
    
    running = "🟢 Running" if bot_manager.is_bot_running(bot_id) else "🔴 Stopped"
    approved = "✔️ Approved" if bot_data['is_approved'] else "⏳ Pending"
    active = "✅ Active" if bot_data['is_active'] else "❌ Inactive"
    
    text = (
        f"🤖 Bot Info\n\n"
        f"Bot ID: {bot_data['bot_id']}\n"
        f"Username: @{bot_data['bot_username']}\n"
        f"Name: {bot_data['bot_first_name']}\n"
        f"Owner: {bot_data['owner_name']} (@{bot_data['owner_username']})\n"
        f"Owner ID: {bot_data['owner_user_id']}\n"
        f"Created: {bot_data['created_date']}\n"
        f"Status: {running}\n"
        f"Approved: {approved}\n"
        f"Active: {active}\n"
        f"Total Users: {bot_data['total_users']}\n"
        f"Total Messages: {bot_data['total_messages']}\n"
        f"Last Active: {bot_data['last_active'] or 'Never'}"
    )
    await update.message.reply_text(text)

# ========== END MULTI-BOT COMMANDS ==========

async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.callback_query.from_user
    if is_user_banned(user.id):
        await update.callback_query.answer("You are banned.", show_alert=True)
        return
        
    ensure_defaults(context)
    q = update.callback_query
    await q.answer()
    data = q.data or ""
    is_admin_user = is_admin(user.id)

    if data == "menu:main":
        await q.edit_message_text("Main menu:\n\n" + status_text(context), reply_markup=main_menu_keyboard(is_admin_user))
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
        help_text = (
            "📖 Help\n\n"
            "Use buttons or commands\n\n"
            + status_text(context)
        )
        await q.edit_message_text(help_text, reply_markup=main_menu_keyboard(is_admin_user))
        return
    if data == "menu:reset":
        persona = context.user_data.get('persona', 'hackGPT')
        lang = context.user_data.get('lang', 'hinglish')
        context.user_data.clear()
        context.user_data['persona'] = persona
        context.user_data['lang'] = lang
        await q.edit_message_text("✅ Reset! Conversation memory cleared.\n\n" + status_text(context), reply_markup=main_menu_keyboard(is_admin_user))
        return
    if data == "menu:admin":
        if not is_admin_user:
            await q.answer("Admin access required", show_alert=True)
            return
        await q.edit_message_text("🔧 Admin Panel\n\nSelect option:", reply_markup=admin_keyboard())
        return
    if data == "admin:stats":
        if not is_admin_user:
            await q.answer("Admin access required", show_alert=True)
            return
        total, active, messages = get_stats()
        db_type = "PostgreSQL" if USE_POSTGRES else "SQLite"
        text = (
            f"📊 Bot Statistics ({db_type})\n\n"
            f"👥 Total Users: {total}\n"
            f"✅ Active Users: {active}\n"
            f"🚫 Banned Users: {total - active}\n"
            f"💬 Total Messages: {messages}\n\n"
            f"🤖 AI: Claude Opus"
        )
        await q.edit_message_text(text, reply_markup=admin_keyboard())
        return
    if data == "admin:users":
        if not is_admin_user:
            await q.answer("Admin access required", show_alert=True)
            return
        users = get_all_users()
        if not users:
            await q.edit_message_text("No users yet.", reply_markup=admin_keyboard())
            return
        text = "👥 User List\n\n"
        for u in users[:10]:
            status = "🚫" if u[6] else "✅"
            text += f"{status} {u[0]} - {u[2]}\nMsgs: {u[4]}\n\n"
        if len(users) > 10:
            text += f"... and {len(users) - 10} more.\nUse /userlist for full list."
        await q.edit_message_text(text, reply_markup=admin_keyboard())
        return
    if data == "admin:clientbots":
        if not is_admin_user:
            await q.answer("Admin access required", show_alert=True)
            return
        await q.edit_message_text("🤖 Client Bots Management\n\nSelect option:", reply_markup=client_bots_keyboard())
        return
    
    # Add Bot button handler
    if data == "clientbots:addbot":
        if not is_admin_user:
            await q.answer("Admin access required", show_alert=True)
            return
        instructions = (
            "➕ Add New Client Bot\n\n"
            "🔑 To add a bot, send this command:\n"
            "/addbot <BOT_TOKEN>\n\n"
            "📝 Example:\n"
            "/addbot 123456:ABC-DEF1234ghIkl\n\n"
            "👉 Get token from @BotFather\n"
            "1. Open @BotFather in Telegram\n"
            "2. Send /newbot\n"
            "3. Follow instructions\n"
            "4. Copy the token\n"
            "5. Use /addbot command here\n\n"
            "✅ Bot will be added and wait for your approval!"
        )
        await q.edit_message_text(instructions, reply_markup=client_bots_keyboard())
        return
    
    if data == "clientbots:stats":
        if not is_admin_user:
            await q.answer("Admin access required", show_alert=True)
            return
        stats = bot_manager.get_client_bot_stats()
        text = (
            "📊 Client Bots Statistics\n\n"
            f"🤖 Total Bots: {stats['total_bots']}\n"
            f"✅ Active Bots: {stats['active_bots']}\n"
            f"⏳ Pending Approvals: {stats['pending_approvals']}\n"
            f"👥 Total Users: {stats['total_users']}\n"
            f"💬 Total Messages: {stats['total_messages']}"
        )
        await q.edit_message_text(text, reply_markup=client_bots_keyboard())
        return
    if data == "clientbots:list":
        if not is_admin_user:
            await q.answer("Admin access required", show_alert=True)
            return
        bots = bot_manager.get_all_client_bots()
        if not bots:
            await q.edit_message_text("🤖 No client bots yet.", reply_markup=client_bots_keyboard())
            return
        text = "🤖 Client Bots (Top 5)\n\n"
        for b in bots[:5]:
            status = "✅" if b[5] else "❌"
            running = "🟢" if bot_manager.is_bot_running(b[0]) else "🔴"
            text += f"{running} {status} ID:{b[0]} @{b[1]}\nOwner: @{b[3]}\n\n"
        text += "\nUse /listbots for full list"
        await q.edit_message_text(text, reply_markup=client_bots_keyboard())
        return
    if data == "clientbots:pending":
        if not is_admin_user:
            await q.answer("Admin access required", show_alert=True)
            return
        pending = bot_manager.get_pending_approvals()
        if not pending:
            await q.edit_message_text("✅ No pending approvals", reply_markup=client_bots_keyboard())
            return
        text = "⏳ Pending Approvals\n\n"
        for p in pending[:5]:
            text += f"ID: {p[0]} - @{p[1]}\nOwner: {p[4]} (@{p[3]})\nDate: {p[5]}\n\n"
        text += f"\nUse /approvebot <id> to approve"
        await q.edit_message_text(text, reply_markup=client_bots_keyboard())
        return

    if data.startswith("persona:"):
        p = data.split(":", 1)[1]
        context.user_data['persona'] = p
        await q.edit_message_text(f"✅ Persona set: {p}\n\n" + status_text(context), reply_markup=main_menu_keyboard(is_admin_user))
        return

    if data.startswith("lang:"):
        l = data.split(":", 1)[1]
        if l in SUPPORTED_LANGS:
            context.user_data['lang'] = l
            await q.edit_message_text(f"✅ Language set: {SUPPORTED_LANGS[l]}\n\n" + status_text(context), reply_markup=main_menu_keyboard(is_admin_user))
        else:
            await q.edit_message_text("❌ Invalid language\n\n" + status_text(context), reply_markup=main_menu_keyboard(is_admin_user))
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
    # Pass user_id for conversation memory
    resp = get_ai_response_sync(prompt, persona, user_id=user.id)

    if len(resp) > 4096:
        for i in range(0, len(resp), 4096):
            await update.message.reply_text(resp[i:i+4096], reply_markup=main_menu_keyboard(is_admin(user.id)))
    else:
        await update.message.reply_text(resp, reply_markup=main_menu_keyboard(is_admin(user.id)))

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
    application.add_handler(CommandHandler("adminstats", admin_stats))
    application.add_handler(CommandHandler("userlist", user_list))
    application.add_handler(CommandHandler("userinfo", user_info_command))
    application.add_handler(CommandHandler("broadcast", broadcast_command))
    application.add_handler(CommandHandler("ban", ban_command))
    application.add_handler(CommandHandler("unban", unban_command))
    
    # Multi-bot management commands
    application.add_handler(CommandHandler("addbot", addbot_command))
    application.add_handler(CommandHandler("listbots", listbots_command))
    application.add_handler(CommandHandler("approvebot", approvebot_command))
    application.add_handler(CommandHandler("enablebot", enablebot_command))
    application.add_handler(CommandHandler("disablebot", disablebot_command))
    application.add_handler(CommandHandler("deletebot", deletebot_command))
    application.add_handler(CommandHandler("botinfo", botinfo_command))
    
    application.add_handler(CallbackQueryHandler(on_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_error_handler(error_handler)
    
    # Setup complete integration
    setup_complete_integration(application)
    
    return application

async def run_polling():
    global application, bot_running
    application = await setup_application()
    if not application:
        return

    bot_running = True
    logger.info("Deleting webhook...")
    await application.bot.delete_webhook(drop_pending_updates=True)
    logger.info("Starting bot polling...")
    await application.initialize()
    await application.start()
    await application.updater.start_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)
    logger.info("Bot started successfully with Claude Opus AI!")
    logger.info("Multi-Bot Management System initialized!")
    await asyncio.Event().wait()

def run_bot_in_thread():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(run_polling())

@app.route('/', methods=['GET'])
def index():
    stats = bot_manager.get_client_bot_stats()
    return jsonify({
        "status": "running" if bot_running else "starting", 
        "message": "HackGPT Multi-Bot System - Powered by Claude Opus AI",
        "api": "claude-opus-chatbot.onrender.com",
        "features": ["conversation_memory", "multi_language", "real_time_data"],
        "client_bots": stats['total_bots'],
        "active_bots": stats['active_bots']
    }), 200

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"ok": True, "ai": "Claude Opus"}), 200

@app.before_request
def startup():
    global bot_thread
    if bot_thread is None:
        bot_thread = threading.Thread(target=run_bot_in_thread, daemon=True)
        bot_thread.start()
        logger.info("Bot thread started with Claude Opus AI")

bot_thread = None

if __name__ == '__main__':
    logger.info(f"Starting Flask on port {PORT}")
    logger.info("Multi-Bot Management System ready!")
    logger.info("AI Backend: Claude Opus (claude-opus-chatbot.onrender.com)")
    app.run(host='0.0.0.0', port=PORT, debug=False, use_reloader=False, threaded=True)

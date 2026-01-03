#!/usr/bin/env python3
import os
import logging
import requests
import asyncio
from flask import Flask, jsonify
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes
)

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Configuration
TELEGRAM_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
CUSTOM_API_URL = os.getenv('CUSTOM_API_URL', 'https://hackgpt-backend.onrender.com')
PORT = int(os.getenv('PORT', 10000))

if not TELEGRAM_TOKEN:
    logger.error("ERROR: TELEGRAM_BOT_TOKEN not found!")
    TELEGRAM_TOKEN = "dummy_token"

# Initialize Flask app
app = Flask(__name__)
application = None
bot_running = False

SUPPORTED_LANGS = {
    "en": "English",
    "hi": "Hindi",
    "hinglish": "Hinglish",
}


def build_prompt(user_text: str, lang: str) -> str:
    """Steer backend output language by prefixing a clear instruction."""
    if lang == "hi":
        return f"Please reply in Hindi (Devanagari).\n\nUser: {user_text}"
    if lang == "hinglish":
        return f"Please reply in Hinglish (mix Hindi + English, Roman script).\n\nUser: {user_text}"
    return f"Please reply in English.\n\nUser: {user_text}"


def get_ai_response_sync(prompt: str, persona: str = "hackGPT") -> str:
    """Call custom Flask API backend (synchronous)"""
    try:
        response = requests.post(
            f"{CUSTOM_API_URL}/chat",
            json={
                "message": prompt,
                "persona": persona,
                "temperature": 0.7,
                "max_tokens": 2000,
            },
            timeout=30,
        )

        if response.status_code == 200:
            data = response.json()
            return data.get('response') or data.get('answer') or 'No response received'
        else:
            return f"API Error {response.status_code}"
    except requests.exceptions.Timeout:
        return "⏱️ Request timeout. Server busy hai."
    except Exception as e:
        logger.error(f"API error: {e}")
        return f"❌ Error: {str(e)[:100]}"


# Command handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command handler"""
    try:
        user = update.effective_user

        # defaults
        context.user_data.setdefault('persona', 'hackGPT')
        context.user_data.setdefault('lang', 'hinglish')

        lang = context.user_data.get('lang', 'hinglish')
        welcome = (
            f"🤖 Welcome {user.first_name}!\n\n"
            "Main HackGPT Bot hu!\n\n"
            "Commands:\n"
            "/start - Start\n"
            "/help - Help\n"
            "/persona [name] - Set persona\n"
            "/lang [en|hi|hinglish] - Language set\n"
            "/reset - Reset chat\n\n"
            f"Current language: {SUPPORTED_LANGS.get(lang, lang)}\n"
            "Just message karo! 🚀"
        )
        await update.message.reply_text(welcome)
    except Exception as e:
        logger.error(f"Start error: {e}")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Help command handler"""
    try:
        help_text = (
            "📚 Help\n\n"
            "/start - Bot start karo\n"
            "/help - Ye help\n"
            "/persona [name] - Persona change\n"
            "/lang [en|hi|hinglish] - Language set\n"
            "/reset - Chat reset\n\n"
            "Examples:\n"
            "/lang hi\n"
            "/lang hinglish\n"
            "/persona DAN"
        )
        await update.message.reply_text(help_text)
    except Exception as e:
        logger.error(f"Help error: {e}")


async def set_persona(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set AI persona"""
    try:
        if context.args:
            persona = ' '.join(context.args)
            context.user_data['persona'] = persona
            await update.message.reply_text(f"✅ Persona: {persona}")
        else:
            current = context.user_data.get('persona', 'hackGPT')
            await update.message.reply_text(f"Current persona: {current}")
    except Exception as e:
        logger.error(f"Persona error: {e}")


async def set_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set response language"""
    try:
        if not context.args:
            current = context.user_data.get('lang', 'hinglish')
            await update.message.reply_text(
                f"Current language: {SUPPORTED_LANGS.get(current, current)}\n"
                "Use: /lang en  OR  /lang hi  OR  /lang hinglish"
            )
            return

        lang = context.args[0].strip().lower()
        if lang not in SUPPORTED_LANGS:
            await update.message.reply_text("❌ Invalid language. Use: /lang en | hi | hinglish")
            return

        context.user_data['lang'] = lang
        await update.message.reply_text(f"✅ Language set to: {SUPPORTED_LANGS[lang]}")
    except Exception as e:
        logger.error(f"Lang error: {e}")


async def reset_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Reset conversation"""
    try:
        # preserve settings
        persona = context.user_data.get('persona', 'hackGPT')
        lang = context.user_data.get('lang', 'hinglish')

        context.user_data.clear()
        context.user_data['persona'] = persona
        context.user_data['lang'] = lang

        await update.message.reply_text("🔄 Reset!")
    except Exception as e:
        logger.error(f"Reset error: {e}")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle user messages"""
    try:
        user_msg = update.message.text
        if not user_msg:
            return

        persona = context.user_data.get('persona', 'hackGPT')
        lang = context.user_data.get('lang', 'hinglish')

        try:
            await update.message.chat.send_action('typing')
        except:
            pass

        prompt = build_prompt(user_msg, lang)
        ai_response = get_ai_response_sync(prompt, persona)

        if len(ai_response) > 4096:
            for i in range(0, len(ai_response), 4096):
                try:
                    await update.message.reply_text(ai_response[i:i+4096])
                except Exception as e:
                    logger.error(f"Chunk send error: {e}")
        else:
            try:
                await update.message.reply_text(ai_response)
            except Exception as e:
                logger.error(f"Send error: {e}")
    except Exception as e:
        logger.error(f"Message handler error: {e}")
        try:
            await update.message.reply_text("❌ Error")
        except:
            pass


async def error_handler(update, context):
    """Log errors"""
    logger.error(f"Error: {context.error}")


async def setup_application():
    """Setup bot application"""
    global application

    if not TELEGRAM_TOKEN or TELEGRAM_TOKEN == "dummy_token":
        logger.error("TELEGRAM_BOT_TOKEN not configured!")
        return None

    try:
        logger.info("Setting up application...")
        application = Application.builder().token(TELEGRAM_TOKEN).build()

        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CommandHandler("persona", set_persona))
        application.add_handler(CommandHandler("lang", set_language))
        application.add_handler(CommandHandler("reset", reset_chat))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        application.add_error_handler(error_handler)

        logger.info("✅ Application setup complete!")
        return application
    except Exception as e:
        logger.error(f"Setup failed: {e}")
        return None


async def run_polling():
    """Run bot with polling"""
    global application, bot_running

    try:
        application = await setup_application()
        if not application:
            logger.error("Failed to setup application")
            return

        logger.info("Starting polling...")
        bot_running = True

        await application.initialize()
        await application.start()
        await application.updater.start_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True,
        )
        logger.info("✅ Bot polling started!")

        await asyncio.Event().wait()
    except Exception as e:
        logger.error(f"Polling error: {e}", exc_info=True)
    finally:
        if application:
            try:
                await application.updater.stop()
                await application.stop()
                await application.shutdown()
            except:
                pass
        bot_running = False


import threading


def run_bot_in_thread():
    """Run bot in background thread"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(run_polling())


# Flask routes
@app.route('/', methods=['GET'])
def index():
    """Health check"""
    return jsonify({
        "status": "running" if bot_running else "starting",
        "message": "HackGPT Bot Active!",
    }), 200


@app.route('/health', methods=['GET'])
def health():
    """Health endpoint"""
    return jsonify({"ok": True}), 200


@app.before_request
def startup():
    """Start bot on first request"""
    global bot_thread
    if bot_thread is None:
        logger.info("Starting bot thread...")
        bot_thread = threading.Thread(target=run_bot_in_thread, daemon=True)
        bot_thread.start()


bot_thread = None


if __name__ == '__main__':
    try:
        logger.info(f"Flask server: 0.0.0.0:{PORT}")
        app.run(host='0.0.0.0', port=PORT, debug=False, use_reloader=False, threaded=True)
    except Exception as e:
        logger.error(f"Flask error: {e}")

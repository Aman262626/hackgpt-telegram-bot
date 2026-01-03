#!/usr/bin/env python3
import os
import logging
import requests
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
import asyncio
import threading

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
    TELEGRAM_TOKEN = "dummy_token"  # Placeholder

# Initialize Flask app
app = Flask(__name__)

# Global variables
application = None
bot_thread = None
bot_running = False

def get_ai_response_sync(prompt: str, persona: str = "hackGPT") -> str:
    """Call custom Flask API backend (synchronous)"""
    try:
        response = requests.post(
            f"{CUSTOM_API_URL}/api/chat",
            json={
                "prompt": prompt,
                "persona": persona,
                "temperature": 0.7,
                "max_tokens": 2000
            },
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            return data.get('response', 'No response received')
        else:
            return f"API Error {response.status_code}"
    
    except requests.exceptions.Timeout:
        return "⏱️ Request timeout. Server response time zyada hai."
    except Exception as e:
        logger.error(f"API call error: {e}")
        return f"❌ Error: {str(e)[:100]}"

# Command handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command handler"""
    try:
        user = update.effective_user
        welcome_message = f"""🤖 Welcome {user.first_name}!

Main HackGPT Bot hu, powered by custom Flask API.

Commands:
/start - Bot ko start karo
/help - Help message
/persona [name] - Persona set karo
/reset - Chat reset karo

Just message karo kuch bhi! 🚀"""
        await update.message.reply_text(welcome_message)
    except Exception as e:
        logger.error(f"Start command error: {e}")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Help command handler"""
    try:
        help_text = """📚 HackGPT Bot Help

Commands:
/start - Bot start
/help - Ye help message
/persona [name] - AI persona set karo
/reset - Conversation clear

Personas: hackGPT, DAN, chatGPT-DEV

Example:
/persona DAN
What is SQL injection?"""
        await update.message.reply_text(help_text)
    except Exception as e:
        logger.error(f"Help command error: {e}")

async def set_persona(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set AI persona"""
    try:
        if context.args:
            persona = ' '.join(context.args)
            context.user_data['persona'] = persona
            await update.message.reply_text(f"✅ Persona set to: {persona}")
        else:
            current = context.user_data.get('persona', 'hackGPT')
            await update.message.reply_text(f"Current persona: {current}")
    except Exception as e:
        logger.error(f"Persona error: {e}")

async def reset_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Reset conversation"""
    try:
        context.user_data.clear()
        await update.message.reply_text("🔄 Conversation reset!")
    except Exception as e:
        logger.error(f"Reset error: {e}")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle user messages"""
    try:
        user_message = update.message.text
        if not user_message:
            return
            
        persona = context.user_data.get('persona', 'hackGPT')
        
        # Send typing action
        try:
            await update.message.chat.send_action('typing')
        except:
            pass
        
        # Get response from API
        ai_response = get_ai_response_sync(user_message, persona)
        
        # Send response (split if too long)
        if len(ai_response) > 4096:
            for i in range(0, len(ai_response), 4096):
                chunk = ai_response[i:i+4096]
                try:
                    await update.message.reply_text(chunk)
                except Exception as e:
                    logger.error(f"Error sending chunk: {e}")
        else:
            try:
                await update.message.reply_text(ai_response)
            except Exception as e:
                logger.error(f"Error sending message: {e}")
    except Exception as e:
        logger.error(f"Message handler error: {e}")
        try:
            await update.message.reply_text("❌ Error processing message")
        except:
            pass

async def error_handler(update, context):
    """Log errors"""
    logger.error(f"Telegram error: {context.error}")

async def setup_application():
    """Initialize bot application with long polling"""
    global application
    
    if not TELEGRAM_TOKEN or TELEGRAM_TOKEN == "dummy_token":
        logger.error("TELEGRAM_BOT_TOKEN not configured!")
        return None
    
    logger.info("Initializing bot application...")
    
    try:
        # Create application with long polling (NOT webhook)
        application = Application.builder().token(TELEGRAM_TOKEN).build()
        
        # Add handlers
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CommandHandler("persona", set_persona))
        application.add_handler(CommandHandler("reset", reset_chat))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        
        # Add error handler
        application.add_error_handler(error_handler)
        
        # Initialize
        await application.initialize()
        logger.info("✅ Bot application initialized!")
        
        return application
    except Exception as e:
        logger.error(f"Failed to initialize bot: {e}")
        return None

async def run_bot():
    """Run bot with long polling"""
    global application, bot_running
    
    try:
        application = await setup_application()
        if not application:
            logger.error("Failed to setup application")
            return
        
        logger.info("Starting bot with long polling...")
        bot_running = True
        await application.start()
        await application.updater.start_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True
        )
        logger.info("✅ Bot polling started!")
        await application.updater.idle()
    except Exception as e:
        logger.error(f"Bot error: {e}", exc_info=True)
    finally:
        if application:
            try:
                await application.stop()
                await application.shutdown()
            except:
                pass
        bot_running = False

def run_bot_thread():
    """Run bot in separate thread"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(run_bot())
    except Exception as e:
        logger.error(f"Thread error: {e}")
    finally:
        loop.close()

# Flask routes
@app.route('/', methods=['GET'])
def index():
    """Health check endpoint"""
    return jsonify({
        "status": "running" if bot_running else "initializing",
        "message": "HackGPT Telegram Bot is active!"
    }), 200

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({"status": "ok"}), 200

@app.before_request
def startup():
    """Start bot thread on first request"""
    global bot_thread, application
    
    if bot_thread is None:
        logger.info("Starting bot thread...")
        bot_thread = threading.Thread(target=run_bot_thread, daemon=True)
        bot_thread.start()

if __name__ == '__main__':
    try:
        logger.info(f"Starting Flask server on 0.0.0.0:{PORT}")
        app.run(host='0.0.0.0', port=PORT, debug=False, use_reloader=False, threaded=True)
    except Exception as e:
        logger.error(f"Flask startup error: {e}")

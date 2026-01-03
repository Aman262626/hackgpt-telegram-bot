#!/usr/bin/env python3
import os
import logging
import asyncio
import requests
from flask import Flask, request, jsonify
from dotenv import load_dotenv
from telegram import Update, Bot
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
WEBHOOK_URL = os.getenv('WEBHOOK_URL', '')
PORT = int(os.getenv('PORT', 10000))

# Validate token
if not TELEGRAM_TOKEN:
    logger.error("ERROR: TELEGRAM_BOT_TOKEN not found in environment variables!")
    raise ValueError("TELEGRAM_BOT_TOKEN is required")

# Initialize Flask app
app = Flask(__name__)

# Global application object
application = None
bot_loop = None

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
            return f"Error: API returned status {response.status_code}"
    
    except requests.exceptions.Timeout:
        return "⏱️ Request timeout. API response time bahut zyada hai."
    except Exception as e:
        logger.error(f"API call error: {e}")
        return f"❌ Error calling API: {str(e)}"

# Command handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command handler"""
    user = update.effective_user
    welcome_message = f"""
🤖 **Welcome {user.mention_html()}!**

Main HackGPT Bot hu, powered by custom Flask API backend.

**Available Commands:**
/start - Bot ko start karo
/help - Help message dikhao
/persona [name] - Persona change karo (hackGPT, DAN, chatGPT-DEV)
/reset - Conversation reset karo

**Direct message bhejo** aur main tumhare sawaal ka jawab dunga! 🚀
    """
    await update.message.reply_html(welcome_message)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Help command handler"""
    help_text = """
📚 **HackGPT Bot Help**

**Commands:**
• /start - Bot shuru karo
• /help - Ye message
• /persona [name] - AI persona set karo
• /reset - Chat history clear karo

**Personas:**
• hackGPT (default)
• DAN
• chatGPT-DEV

**Example:**
`/persona DAN`
`What is SQL injection?`
    """
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def set_persona(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set AI persona"""
    if context.args:
        persona = context.args[0]
        context.user_data['persona'] = persona
        await update.message.reply_text(f"✅ Persona set to: **{persona}**", parse_mode='Markdown')
    else:
        current_persona = context.user_data.get('persona', 'hackGPT')
        await update.message.reply_text(
            f"Current persona: **{current_persona}**\n\nUse: `/persona [hackGPT|DAN|chatGPT-DEV]`",
            parse_mode='Markdown'
        )

async def reset_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Reset conversation"""
    context.user_data.clear()
    await update.message.reply_text("🔄 Conversation reset ho gaya!")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle user messages"""
    user_message = update.message.text
    persona = context.user_data.get('persona', 'hackGPT')
    
    try:
        # Send typing action
        await update.message.chat.send_action('typing')
        
        # Get response from custom API
        loop = asyncio.get_event_loop()
        ai_response = await loop.run_in_executor(None, get_ai_response_sync, user_message, persona)
        
        # Send response
        await update.message.reply_text(ai_response)
    except Exception as e:
        logger.error(f"Error handling message: {e}")
        await update.message.reply_text(f"❌ Error: {str(e)}")

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Log errors"""
    logger.error(f"Update {update} caused error {context.error}")

# Flask routes
@app.route('/', methods=['GET'])
def index():
    """Health check endpoint"""
    return jsonify({"status": "running", "message": "HackGPT Telegram Bot is active!"}), 200

@app.route('/webhook', methods=['POST'])
def webhook():
    """Handle webhook from Telegram"""
    try:
        if not application:
            logger.error("Application not initialized")
            return jsonify({"error": "Bot not ready"}), 500
        
        data = request.get_json(force=True)
        update = Update.de_json(data, application.bot)
        
        # Process update in new event loop
        asyncio.run(application.process_update(update))
        
        return jsonify({"status": "ok"}), 200
    except Exception as e:
        logger.error(f"Webhook error: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500

async def setup_application():
    """Initialize bot application"""
    global application
    
    logger.info("Initializing bot application...")
    
    # Create application
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("persona", set_persona))
    application.add_handler(CommandHandler("reset", reset_chat))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Add error handler
    application.add_error_handler(error_handler)
    
    # Initialize application
    await application.initialize()
    
    # Set webhook if URL provided
    if WEBHOOK_URL:
        webhook_url = f"{WEBHOOK_URL}/webhook"
        logger.info(f"Setting webhook to: {webhook_url}")
        await application.bot.set_webhook(url=webhook_url)
        logger.info("✅ Webhook set successfully!")
    else:
        logger.warning("⚠️ WEBHOOK_URL not set! Bot will not receive updates.")
    
    logger.info("✅ Bot application initialized successfully!")
    return application

@app.before_request
def before_request():
    """Initialize bot before first request"""
    global application
    if application is None:
        try:
            application = asyncio.run(setup_application())
        except Exception as e:
            logger.error(f"Failed to initialize bot: {e}", exc_info=True)
            raise

if __name__ == '__main__':
    try:
        logger.info(f"Starting HackGPT Telegram Bot on 0.0.0.0:{PORT}")
        app.run(host='0.0.0.0', port=PORT, debug=False, use_reloader=False)
    except Exception as e:
        logger.error(f"Failed to start Flask app: {e}", exc_info=True)
        raise

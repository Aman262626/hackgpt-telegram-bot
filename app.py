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
WEBHOOK_URL = os.getenv('WEBHOOK_URL')
PORT = int(os.getenv('PORT', 10000))

# Initialize Flask app
app = Flask(__name__)

# Global application object
application = None
initialized = False

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
    try:
        user = update.effective_user
        welcome_message = f"""
🤖 Welcome {user.mention_html()}!

Main HackGPT Bot hu, powered by custom Flask API backend.

Available Commands:
/start - Bot ko start karo
/help - Help message dikhao
/persona [name] - Persona change karo
/reset - Conversation reset karo

Direct message bhejo aur main tumhare sawaal ka jawab dunga! 🚀
        """
        await update.message.reply_html(welcome_message)
    except Exception as e:
        logger.error(f"Start command error: {e}")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Help command handler"""
    try:
        help_text = """
📚 HackGPT Bot Help

Commands:
• /start - Bot shuru karo
• /help - Ye message
• /persona [name] - AI persona set karo
• /reset - Chat history clear karo

Personas:
• hackGPT (default)
• DAN
• chatGPT-DEV
        """
        await update.message.reply_text(help_text, parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Help command error: {e}")

async def set_persona(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set AI persona"""
    try:
        if context.args:
            persona = context.args[0]
            context.user_data['persona'] = persona
            await update.message.reply_text(f"✅ Persona set to: {persona}")
        else:
            current_persona = context.user_data.get('persona', 'hackGPT')
            await update.message.reply_text(f"Current persona: {current_persona}")
    except Exception as e:
        logger.error(f"Set persona error: {e}")

async def reset_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Reset conversation"""
    try:
        context.user_data.clear()
        await update.message.reply_text("🔄 Conversation reset ho gaya!")
    except Exception as e:
        logger.error(f"Reset error: {e}")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle user messages"""
    try:
        user_message = update.message.text
        persona = context.user_data.get('persona', 'hackGPT')
        
        # Send typing action
        await update.message.chat.send_action('typing')
        
        # Get response from custom API
        loop = asyncio.get_event_loop()
        ai_response = await loop.run_in_executor(None, get_ai_response_sync, user_message, persona)
        
        # Send response in chunks if too long
        if len(ai_response) > 4096:
            for chunk in [ai_response[i:i+4096] for i in range(0, len(ai_response), 4096)]:
                await update.message.reply_text(chunk)
        else:
            await update.message.reply_text(ai_response)
    except Exception as e:
        logger.error(f"Error handling message: {e}")
        try:
            await update.message.reply_text(f"❌ Error: {str(e)[:100]}")
        except:
            pass

async def error_handler(update, context):
    """Log errors"""
    logger.error(f"Error: {context.error}")

# Flask routes
@app.route('/', methods=['GET'])
def index():
    """Health check endpoint"""
    return jsonify({"status": "running", "message": "HackGPT Telegram Bot is active!"}), 200

@app.route('/webhook', methods=['POST'])
def webhook():
    """Handle webhook from Telegram"""
    try:
        global application
        
        if not application:
            logger.error("Application not initialized")
            return jsonify({"error": "Bot not ready"}), 503
        
        data = request.get_json(force=True)
        update = Update.de_json(data, application.bot)
        
        if update:
            # Process update asynchronously without blocking
            asyncio.create_task(application.process_update(update))
        
        return jsonify({"status": "ok"}), 200
    except Exception as e:
        logger.error(f"Webhook error: {e}", exc_info=True)
        return jsonify({"error": "Webhook processing failed"}), 200

async def setup_application():
    """Initialize bot application"""
    global application
    
    if not TELEGRAM_TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN is required")
    
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
    
    logger.info("✅ Bot application initialized successfully!")
    return application

@app.before_request
def before_request():
    """Initialize bot on first request"""
    global application, initialized
    
    if not initialized and TELEGRAM_TOKEN:
        try:
            logger.info("Setting up application...")
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            application = loop.run_until_complete(setup_application())
            initialized = True
            logger.info("Application ready!")
        except Exception as e:
            logger.error(f"Failed to initialize bot: {e}", exc_info=True)

if __name__ == '__main__':
    try:
        logger.info(f"Starting HackGPT Telegram Bot on 0.0.0.0:{PORT}")
        app.run(host='0.0.0.0', port=PORT, debug=False, use_reloader=False)
    except Exception as e:
        logger.error(f"Failed to start Flask app: {e}", exc_info=True)

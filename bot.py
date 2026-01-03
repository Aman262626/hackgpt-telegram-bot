#!/usr/bin/env python3
import os
import logging
import requests
import asyncio
from flask import Flask, request
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

# Initialize Flask app
app = Flask(__name__)

# Global bot application
bot_application = None

# Function to call custom Flask API
def get_ai_response_sync(prompt: str, persona: str = "hackGPT") -> str:
    """Call custom Flask API backend (synchronous version)"""
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
    
    # Send typing action
    await update.message.chat.send_action('typing')
    
    # Get response from custom API (sync version in executor)
    loop = asyncio.get_event_loop()
    ai_response = await loop.run_in_executor(None, get_ai_response_sync, user_message, persona)
    
    # Send response
    await update.message.reply_text(ai_response)

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Log errors"""
    logger.error(f"Update {update} caused error {context.error}")

# Flask routes
@app.route('/', methods=['GET'])
def index():
    """Health check endpoint"""
    return {"status": "running", "message": "HackGPT Telegram Bot is active!"}, 200

@app.route('/webhook', methods=['POST'])
def webhook():
    """Handle webhook requests from Telegram"""
    try:
        data = request.get_json(force=True)
        update = Update.de_json(data, bot_application.bot)
        
        # Process update in asyncio context
        asyncio.run(bot_application.process_update(update))
        
        return 'OK', 200
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return str(e), 500

def setup_bot():
    """Setup bot application"""
    global bot_application
    
    if not TELEGRAM_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN not found!")
        raise ValueError("TELEGRAM_BOT_TOKEN is required")
    
    # Create application
    bot_application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Register handlers
    bot_application.add_handler(CommandHandler("start", start))
    bot_application.add_handler(CommandHandler("help", help_command))
    bot_application.add_handler(CommandHandler("persona", set_persona))
    bot_application.add_handler(CommandHandler("reset", reset_chat))
    bot_application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Register error handler
    bot_application.add_error_handler(error_handler)
    
    # Initialize and set webhook
    async def init_bot():
        await bot_application.initialize()
        
        if WEBHOOK_URL:
            webhook_url = f"{WEBHOOK_URL}/webhook"
            await bot_application.bot.set_webhook(url=webhook_url)
            logger.info(f"Webhook set to: {webhook_url}")
        else:
            logger.warning("WEBHOOK_URL not set! Bot may not work properly.")
    
    # Run initialization
    asyncio.run(init_bot())
    
    logger.info("Bot setup complete!")
    return bot_application

if __name__ == '__main__':
    try:
        # Setup bot
        setup_bot()
        
        # Run Flask app
        logger.info(f"Starting Flask server on 0.0.0.0:{PORT}")
        app.run(host='0.0.0.0', port=PORT, debug=False)
        
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")
        raise

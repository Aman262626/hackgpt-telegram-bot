#!/usr/bin/env python3
import os
import logging
import requests
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes
)
from flask import Flask, request

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
RENDER_EXTERNAL_URL = os.getenv('RENDER_EXTERNAL_URL', '')
PORT = int(os.getenv('PORT', 8443))

# Flask app for webhook
app = Flask(__name__)

# Function to call your custom Flask API
async def get_ai_response(prompt: str, persona: str = "hackGPT") -> str:
    """Call custom Flask API backend"""
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
    
    # Get response from custom API
    ai_response = await get_ai_response(user_message, persona)
    
    # Send response
    await update.message.reply_text(ai_response)

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Log errors"""
    logger.error(f"Update {update} caused error {context.error}")

# Webhook routes
@app.route('/')
def index():
    return "HackGPT Telegram Bot is running! 🚀", 200

@app.route('/health')
def health():
    return "OK", 200

@app.route(f'/{TELEGRAM_TOKEN}', methods=['POST'])
async def webhook():
    """Handle webhook updates"""
    try:
        update = Update.de_json(request.get_json(force=True), application.bot)
        await application.process_update(update)
        return "OK", 200
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return "Error", 500

# Global application variable
application = None

async def setup_webhook():
    """Setup webhook for Render"""
    global application
    
    if not TELEGRAM_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN not found in environment variables!")
        return None
    
    # Create application
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Register handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("persona", set_persona))
    application.add_handler(CommandHandler("reset", reset_chat))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Register error handler
    application.add_error_handler(error_handler)
    
    # Initialize application
    await application.initialize()
    await application.bot.initialize()
    
    # Set webhook
    webhook_url = f"{RENDER_EXTERNAL_URL}/{TELEGRAM_TOKEN}"
    await application.bot.set_webhook(url=webhook_url)
    
    logger.info(f"Webhook set to: {webhook_url}")
    logger.info("Bot started successfully with webhook mode!")
    
    return application

def main():
    """Start the bot with webhook"""
    import asyncio
    
    # Setup webhook
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(setup_webhook())
    
    # Run Flask app
    app.run(host='0.0.0.0', port=PORT)

if __name__ == '__main__':
    main()

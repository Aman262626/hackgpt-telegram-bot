#!/usr/bin/env python3
import os
import logging
import requests
from flask import Flask, request
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
WEBHOOK_URL = os.getenv('WEBHOOK_URL', '')  # Will be set in Render
PORT = int(os.getenv('PORT', 10000))

# Initialize Flask app for webhook
app = Flask(__name__)

# Initialize bot application
bot_app = None

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

@app.route('/', methods=['GET'])
def index():
    """Health check endpoint for Render"""
    return {"status": "Bot is running", "message": "HackGPT Telegram Bot is active!"}, 200

@app.route('/webhook', methods=['POST'])
async def webhook():
    """Handle incoming webhook requests from Telegram"""
    try:
        update = Update.de_json(request.get_json(force=True), bot_app.bot)
        await bot_app.process_update(update)
        return 'OK', 200
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return 'Error', 500

async def setup_application():
    """Setup bot application"""
    global bot_app
    
    if not TELEGRAM_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN not found in environment variables!")
        return None
    
    # Create application
    bot_app = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Register handlers
    bot_app.add_handler(CommandHandler("start", start))
    bot_app.add_handler(CommandHandler("help", help_command))
    bot_app.add_handler(CommandHandler("persona", set_persona))
    bot_app.add_handler(CommandHandler("reset", reset_chat))
    bot_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Register error handler
    bot_app.add_error_handler(error_handler)
    
    # Initialize application
    await bot_app.initialize()
    
    # Set webhook
    if WEBHOOK_URL:
        webhook_url = f"{WEBHOOK_URL}/webhook"
        await bot_app.bot.set_webhook(url=webhook_url)
        logger.info(f"Webhook set to: {webhook_url}")
    
    logger.info("Bot application setup complete!")
    return bot_app

if __name__ == '__main__':
    import asyncio
    
    # Setup bot in async context
    loop = asyncio.get_event_loop()
    loop.run_until_complete(setup_application())
    
    # Run Flask app
    logger.info(f"Starting Flask server on port {PORT}")
    app.run(host='0.0.0.0', port=PORT, debug=False)

#!/usr/bin/env python3
"""Client Bot Runner - Manages running client bot instances"""
import logging
import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import bot_manager

logger = logging.getLogger(__name__)

# Client bot message handlers
async def client_start(update: Update, context: ContextTypes.DEFAULT_TYPE, bot_id: int):
    """Start command handler for client bots"""
    user_id = update.effective_user.id
    username = update.effective_user.username or "Unknown"
    
    await update.message.reply_text(
        f"🤖 **Welcome to this Bot!**\n\n"
        f"👤 User: @{username}\n"
        f"🆔 Your ID: `{user_id}`\n\n"
        f"This is a client bot powered by DarkGpt Multi-Bot System!\n\n"
        f"Send any message to interact!",
        parse_mode='Markdown'
    )
    
    logger.info(f"Client bot {bot_id}: User {user_id} started")

async def client_help(update: Update, context: ContextTypes.DEFAULT_TYPE, bot_id: int):
    """Help command handler for client bots"""
    await update.message.reply_text(
        f"🤖 **Bot Help**\n\n"
        f"Available Commands:\n"
        f"/start - Start the bot\n"
        f"/help - Show this help\n\n"
        f"Send any message to chat with the bot!",
        parse_mode='Markdown'
    )

async def client_message(update: Update, context: ContextTypes.DEFAULT_TYPE, bot_id: int):
    """Message handler for client bots"""
    user_msg = update.message.text
    user_id = update.effective_user.id
    
    # Simple echo response (customize as needed)
    await update.message.reply_text(
        f"✅ Received: {user_msg}\n\n"
        f"🤖 Bot ID: {bot_id}\n"
        f"This is a test response from client bot!",
        parse_mode='Markdown'
    )
    
    # Update stats
    bot_manager.update_bot_stats(bot_id, messages=1)
    
    logger.info(f"Client bot {bot_id}: Message from user {user_id}")

def setup_client_handlers(application: Application, bot_id: int):
    """Setup handlers for a client bot"""
    # Start command
    application.add_handler(
        CommandHandler("start", lambda u, c: client_start(u, c, bot_id))
    )
    
    # Help command
    application.add_handler(
        CommandHandler("help", lambda u, c: client_help(u, c, bot_id))
    )
    
    # Message handler
    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            lambda u, c: client_message(u, c, bot_id)
        )
    )
    
    logger.info(f"Handlers setup for client bot {bot_id}")

async def start_all_active_bots():
    """Start all approved and active client bots on system startup"""
    try:
        import sqlite3
        conn = sqlite3.connect('bot_users.db')
        c = conn.cursor()
        c.execute('SELECT bot_id, bot_token FROM client_bots WHERE is_approved = 1 AND is_active = 1')
        active_bots = c.fetchall()
        conn.close()
        
        started_count = 0
        for bot_id, bot_token in active_bots:
            try:
                success, message = await bot_manager.start_client_bot(
                    bot_id, 
                    bot_token, 
                    setup_client_handlers
                )
                if success:
                    started_count += 1
                    logger.info(f"Started client bot {bot_id}")
                else:
                    logger.error(f"Failed to start client bot {bot_id}: {message}")
            except Exception as e:
                logger.error(f"Error starting client bot {bot_id}: {e}")
        
        logger.info(f"Client bot startup complete: {started_count}/{len(active_bots)} bots started")
        return started_count
    except Exception as e:
        logger.error(f"Error in start_all_active_bots: {e}")
        return 0

async def stop_all_client_bots():
    """Stop all running client bots gracefully"""
    running_bots = bot_manager.get_running_bots()
    stopped_count = 0
    
    for bot_id in running_bots:
        try:
            success, message = await bot_manager.stop_client_bot(bot_id)
            if success:
                stopped_count += 1
                logger.info(f"Stopped client bot {bot_id}")
        except Exception as e:
            logger.error(f"Error stopping client bot {bot_id}: {e}")
    
    logger.info(f"Stopped {stopped_count} client bots")
    return stopped_count

# Export functions
__all__ = [
    'setup_client_handlers',
    'start_all_active_bots',
    'stop_all_client_bots'
]

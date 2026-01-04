#!/usr/bin/env python3
"""Client Bot Command Handlers - Auto-Integration Module"""
import logging
from telegram import Update
from telegram.ext import CommandHandler, ContextTypes
import bot_manager
from client_bot_runner import setup_client_handlers, start_all_active_bots, stop_all_client_bots

logger = logging.getLogger(__name__)

# Admin IDs - Update this in your app.py ADMIN_IDS
ADMIN_IDS = [7827293530]  # Replace with your admin IDs

async def handle_enable_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Enable and start a client bot - Enhanced version"""
    user_id = update.effective_user.id
    
    # Admin check
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Unauthorized access!")
        return
    
    # Validate arguments
    if not context.args:
        await update.message.reply_text(
            "❌ Usage: /enablebot <bot_id>\n\n"
            "Example: /enablebot 1"
        )
        return
    
    if not context.args[0].isdigit():
        await update.message.reply_text("❌ Bot ID must be a number!")
        return
    
    bot_id = int(context.args[0])
    
    # Get bot details
    bot_info = bot_manager.get_client_bot(bot_id)
    if not bot_info:
        await update.message.reply_text(f"❌ Bot ID {bot_id} not found!")
        return
    
    # Check if approved
    if bot_info['is_approved'] != 1:
        await update.message.reply_text(
            f"❌ Bot not approved yet!\n\n"
            f"Use: /approvebot {bot_id}"
        )
        return
    
    # Check if already running
    if bot_manager.is_bot_running(bot_id):
        await update.message.reply_text(f"⚠️ Bot {bot_id} is already running!")
        return
    
    # Enable in database
    success, message = bot_manager.enable_client_bot(bot_id)
    if not success:
        await update.message.reply_text(f"❌ Database error: {message}")
        return
    
    # Send processing message
    processing_msg = await update.message.reply_text("⏳ Starting bot...")
    
    # Actually START the bot instance
    try:
        success, start_msg = await bot_manager.start_client_bot(
            bot_id, 
            bot_info['bot_token'], 
            setup_client_handlers
        )
        
        if success:
            await processing_msg.edit_text(
                f"✅ **Bot Started Successfully!**\n\n"
                f"🆔 Bot ID: `{bot_id}`\n"
                f"🤖 Username: @{bot_info['bot_username']}\n"
                f"📛 Name: {bot_info['bot_first_name']}\n"
                f"👤 Owner: @{bot_info['owner_username']}\n\n"
                f"✨ Bot is now **LIVE** and running!\n"
                f"Users can interact with @{bot_info['bot_username']}",
                parse_mode='Markdown'
            )
            logger.info(f"✅ Client bot {bot_id} started by admin {user_id}")
        else:
            await processing_msg.edit_text(
                f"❌ **Failed to start bot!**\n\n"
                f"Error: {start_msg}\n\n"
                f"Check bot token or try again."
            )
            # Rollback database
            bot_manager.disable_client_bot(bot_id)
            logger.error(f"❌ Failed to start client bot {bot_id}: {start_msg}")
    
    except Exception as e:
        await processing_msg.edit_text(f"❌ Error: {str(e)[:200]}")
        bot_manager.disable_client_bot(bot_id)
        logger.error(f"Exception starting bot {bot_id}: {e}")

async def handle_disable_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Disable and stop a client bot"""
    user_id = update.effective_user.id
    
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Unauthorized access!")
        return
    
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text(
            "❌ Usage: /disablebot <bot_id>\n\n"
            "Example: /disablebot 1"
        )
        return
    
    bot_id = int(context.args[0])
    
    # Check if bot exists
    bot_info = bot_manager.get_client_bot(bot_id)
    if not bot_info:
        await update.message.reply_text(f"❌ Bot ID {bot_id} not found!")
        return
    
    processing_msg = await update.message.reply_text("⏳ Stopping bot...")
    
    # Stop the bot instance if running
    if bot_manager.is_bot_running(bot_id):
        try:
            success, stop_msg = await bot_manager.stop_client_bot(bot_id)
            if not success:
                await processing_msg.edit_text(f"❌ Failed to stop: {stop_msg}")
                return
        except Exception as e:
            await processing_msg.edit_text(f"❌ Error stopping: {str(e)[:200]}")
            return
    
    # Disable in database
    success, message = bot_manager.disable_client_bot(bot_id)
    
    if success:
        await processing_msg.edit_text(
            f"✅ **Bot Stopped Successfully!**\n\n"
            f"🆔 Bot ID: `{bot_id}`\n"
            f"🤖 @{bot_info['bot_username']}\n\n"
            f"🛑 Bot is now offline.",
            parse_mode='Markdown'
        )
        logger.info(f"🛑 Client bot {bot_id} stopped by admin {user_id}")
    else:
        await processing_msg.edit_text(f"❌ {message}")

async def handle_bot_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Check status of a specific bot or all bots"""
    user_id = update.effective_user.id
    
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Unauthorized access!")
        return
    
    if context.args and context.args[0].isdigit():
        # Specific bot status
        bot_id = int(context.args[0])
        bot_info = bot_manager.get_client_bot(bot_id)
        
        if not bot_info:
            await update.message.reply_text(f"❌ Bot {bot_id} not found!")
            return
        
        status_emoji = "🟢" if bot_manager.is_bot_running(bot_id) else "🔴"
        approved_emoji = "✅" if bot_info['is_approved'] == 1 else "⏳"
        active_emoji = "🟢" if bot_info['is_active'] == 1 else "🔴"
        
        await update.message.reply_text(
            f"📊 **Bot Status**\n\n"
            f"🆔 Bot ID: `{bot_id}`\n"
            f"🤖 Username: @{bot_info['bot_username']}\n"
            f"📛 Name: {bot_info['bot_first_name']}\n\n"
            f"Status: {status_emoji} {'Running' if bot_manager.is_bot_running(bot_id) else 'Stopped'}\n"
            f"Approved: {approved_emoji} {'Yes' if bot_info['is_approved'] == 1 else 'No'}\n"
            f"Active: {active_emoji} {'Yes' if bot_info['is_active'] == 1 else 'No'}\n\n"
            f"👤 Owner: @{bot_info['owner_username']}\n"
            f"📅 Created: {bot_info['created_date']}\n"
            f"📊 Users: {bot_info['total_users']}\n"
            f"💬 Messages: {bot_info['total_messages']}",
            parse_mode='Markdown'
        )
    else:
        # All bots status
        running_bots = bot_manager.get_running_bots()
        stats = bot_manager.get_client_bot_stats()
        
        await update.message.reply_text(
            f"📊 **Client Bots Overview**\n\n"
            f"🤖 Total Bots: {stats['total_bots']}\n"
            f"🟢 Active: {stats['active_bots']}\n"
            f"▶️ Running Now: {len(running_bots)}\n"
            f"⏳ Pending: {stats['pending_approvals']}\n\n"
            f"👥 Total Users: {stats['total_users']}\n"
            f"💬 Total Messages: {stats['total_messages']}\n\n"
            f"Running Bot IDs: {', '.join(map(str, running_bots)) if running_bots else 'None'}",
            parse_mode='Markdown'
        )

def register_client_bot_handlers(application):
    """Register all client bot command handlers"""
    application.add_handler(CommandHandler("enablebot", handle_enable_bot))
    application.add_handler(CommandHandler("disablebot", handle_disable_bot))
    application.add_handler(CommandHandler("botstatus", handle_bot_status))
    logger.info("✅ Client bot command handlers registered")

async def startup_client_bots():
    """Auto-start all active client bots on system startup"""
    try:
        logger.info("🚀 Starting active client bots...")
        started_count = await start_all_active_bots()
        logger.info(f"✅ Started {started_count} client bots")
        return started_count
    except Exception as e:
        logger.error(f"❌ Error in startup_client_bots: {e}")
        return 0

async def shutdown_client_bots():
    """Gracefully stop all client bots on system shutdown"""
    try:
        logger.info("🛑 Stopping all client bots...")
        stopped_count = await stop_all_client_bots()
        logger.info(f"✅ Stopped {stopped_count} client bots")
        return stopped_count
    except Exception as e:
        logger.error(f"❌ Error in shutdown_client_bots: {e}")
        return 0

# Export functions
__all__ = [
    'register_client_bot_handlers',
    'startup_client_bots',
    'shutdown_client_bots',
    'handle_enable_bot',
    'handle_disable_bot',
    'handle_bot_status'
]

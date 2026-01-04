#!/usr/bin/env python3
"""Broadcast Command Handlers - Easy Integration"""
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes, ConversationHandler
import broadcast_manager

logger = logging.getLogger(__name__)

# Admin IDs
ADMIN_IDS = [7827293530]  # Update with your admin IDs

# Conversation states
BROADCAST_MESSAGE = 1

async def handle_broadcast_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start broadcast - Ask for message"""
    user_id = update.effective_user.id
    
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Unauthorized!")
        return ConversationHandler.END
    
    total_users = broadcast_manager.get_total_members()
    
    await update.message.reply_text(
        f"📢 **Broadcast Message**\n\n"
        f"👥 Total Users: {total_users}\n\n"
        f"📝 Send the message you want to broadcast:\n\n"
        f"(Send /cancel to cancel)",
        parse_mode='Markdown'
    )
    
    return BROADCAST_MESSAGE

async def handle_broadcast_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive broadcast message and confirm"""
    user_id = update.effective_user.id
    message_text = update.message.text
    
    # Save pending broadcast
    broadcast_manager.save_pending_broadcast(user_id, message_text)
    
    total_users = broadcast_manager.get_total_members()
    
    # Confirmation keyboard
    keyboard = [
        [
            InlineKeyboardButton("✅ Confirm & Send", callback_data="broadcast_confirm"),
            InlineKeyboardButton("❌ Cancel", callback_data="broadcast_cancel")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"📢 **Broadcast Preview**\n\n"
        f"Message:\n{message_text}\n\n"
        f"👥 Will be sent to: {total_users} users\n\n"
        f"Confirm to send?",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    
    return ConversationHandler.END

async def handle_broadcast_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Execute broadcast after confirmation"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    # Get pending broadcast
    pending = broadcast_manager.get_pending_broadcast(user_id)
    if not pending:
        await query.edit_message_text("❌ No pending broadcast found!")
        return
    
    # Send processing message
    await query.edit_message_text("⏳ Broadcasting message... Please wait.")
    
    # Execute broadcast
    result = await broadcast_manager.execute_broadcast(
        context.bot,
        user_id,
        pending['message_text']
    )
    
    # Clear pending
    broadcast_manager.clear_pending_broadcast(user_id)
    
    # Send result
    if 'error' in result:
        await query.edit_message_text(
            f"❌ **Broadcast Failed!**\n\n"
            f"Error: {result['error']}"
        )
    else:
        await query.edit_message_text(
            f"✅ **Broadcast Completed!**\n\n"
            f"👥 Total Users: {result['total']}\n"
            f"✅ Successful: {result['successful']}\n"
            f"❌ Failed: {result['failed']}\n"
            f"📊 Success Rate: {result['success_rate']}%",
            parse_mode='Markdown'
        )

async def handle_broadcast_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel broadcast"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    broadcast_manager.clear_pending_broadcast(user_id)
    
    await query.edit_message_text("❌ Broadcast cancelled.")

async def handle_broadcast_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show broadcast history"""
    user_id = update.effective_user.id
    
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Unauthorized!")
        return
    
    history = broadcast_manager.get_broadcast_history(user_id, limit=5)
    stats = broadcast_manager.get_broadcast_stats()
    
    if not history:
        await update.message.reply_text("📊 No broadcast history yet.")
        return
    
    text = f"📊 **Broadcast History**\n\n"
    text += f"📢 Total Broadcasts: {stats['total_broadcasts']}\n"
    text += f"✅ Messages Sent: {stats['total_messages_sent']}\n"
    text += f"❌ Failed: {stats['total_failed']}\n"
    text += f"📈 Success Rate: {stats['success_rate']}%\n\n"
    text += "**Recent Broadcasts:**\n\n"
    
    for i, h in enumerate(history, 1):
        text += f"{i}. {h['message_text']}\n"
        text += f"   • Users: {h['total_users']} | Success: {h['successful']} | Failed: {h['failed']}\n"
        text += f"   • Date: {h['date']}\n\n"
    
    await update.message.reply_text(text, parse_mode='Markdown')

async def handle_recent_members(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show recent members who joined"""
    user_id = update.effective_user.id
    
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Unauthorized!")
        return
    
    members = broadcast_manager.get_recent_members(limit=10)
    total = broadcast_manager.get_total_members()
    
    if not members:
        await update.message.reply_text("👥 No members yet.")
        return
    
    text = f"👥 **Recent Members**\n\n"
    text += f"📊 Total Members: {total}\n\n"
    
    for i, m in enumerate(members, 1):
        name = m['first_name']
        if m['last_name']:
            name += f" {m['last_name']}"
        username = f"@{m['username']}" if m['username'] else "No username"
        
        text += f"{i}. {name}\n"
        text += f"   • {username} | ID: `{m['user_id']}`\n"
        text += f"   • Joined: {m['join_date']}\n\n"
    
    await update.message.reply_text(text, parse_mode='Markdown')

async def handle_new_member_auto_notify(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Auto-notify admin when new member joins (add this to /start handler)"""
    user_id = update.effective_user.id
    username = update.effective_user.username
    first_name = update.effective_user.first_name
    last_name = update.effective_user.last_name
    
    # Log member join
    is_new = broadcast_manager.log_member_join(user_id, username, first_name, last_name)
    
    # Notify admins if new member
    if is_new:
        for admin_id in ADMIN_IDS:
            try:
                await broadcast_manager.notify_admin_new_member(
                    context.bot,
                    admin_id,
                    user_id,
                    username,
                    first_name,
                    last_name
                )
            except Exception as e:
                logger.error(f"Failed to notify admin {admin_id}: {e}")

def get_broadcast_conversation_handler():
    """Get broadcast conversation handler"""
    return ConversationHandler(
        entry_points=[CommandHandler('broadcast', handle_broadcast_start)],
        states={
            BROADCAST_MESSAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_broadcast_message)]
        },
        fallbacks=[CommandHandler('cancel', lambda u, c: ConversationHandler.END)]
    )

def register_broadcast_handlers(application):
    """Register all broadcast handlers"""
    # Conversation handler for broadcast
    application.add_handler(get_broadcast_conversation_handler())
    
    # Callback query handlers
    application.add_handler(CallbackQueryHandler(handle_broadcast_confirm, pattern="^broadcast_confirm$"))
    application.add_handler(CallbackQueryHandler(handle_broadcast_cancel, pattern="^broadcast_cancel$"))
    
    # Command handlers
    application.add_handler(CommandHandler('broadcasthistory', handle_broadcast_history))
    application.add_handler(CommandHandler('recentmembers', handle_recent_members))
    
    logger.info("✅ Broadcast handlers registered")

# Export functions
__all__ = [
    'register_broadcast_handlers',
    'handle_new_member_auto_notify'
]

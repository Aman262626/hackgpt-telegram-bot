#!/usr/bin/env python3
"""Enhanced Admin Panel with Broadcast & Member Management"""
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CommandHandler, CallbackQueryHandler, ContextTypes
import broadcast_manager
import bot_manager

logger = logging.getLogger(__name__)

# Admin IDs
ADMIN_IDS = [7827293530]

async def enhanced_admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show enhanced admin panel with all features"""
    user_id = update.effective_user.id
    
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Unauthorized!")
        return
    
    # Get stats
    total_users = broadcast_manager.get_total_members()
    bot_stats = bot_manager.get_client_bot_stats()
    broadcast_stats = broadcast_manager.get_broadcast_stats()
    
    keyboard = [
        [
            InlineKeyboardButton("📊 Statistics", callback_data="admin_stats"),
            InlineKeyboardButton("👥 User List", callback_data="admin_users")
        ],
        [
            InlineKeyboardButton("🤖 Client Bots", callback_data="admin_client_bots"),
            InlineKeyboardButton("⏳ Pending Approvals", callback_data="admin_pending")
        ],
        [
            InlineKeyboardButton("📢 Broadcast Message", callback_data="admin_broadcast"),
            InlineKeyboardButton("📈 Broadcast History", callback_data="admin_broadcast_history")
        ],
        [
            InlineKeyboardButton("🎉 Recent Members", callback_data="admin_recent_members"),
            InlineKeyboardButton("🔄 Refresh", callback_data="admin_refresh")
        ],
        [
            InlineKeyboardButton("⬅️ Back", callback_data="admin_back")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = (
        f"🔧 **Admin Panel**\n\n"
        f"📊 **Overview:**\n"
        f"• Total Users: {total_users}\n"
        f"• Client Bots: {bot_stats['total_bots']} ({bot_stats['active_bots']} active)\n"
        f"• Pending Approvals: {bot_stats['pending_approvals']}\n"
        f"• Total Broadcasts: {broadcast_stats['total_broadcasts']}\n\n"
        f"Select an option:"
    )
    
    if update.callback_query:
        await update.callback_query.edit_message_text(
            text=text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text(
            text=text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

async def handle_admin_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle broadcast button - redirect to /broadcast command"""
    query = update.callback_query
    await query.answer()
    
    total_users = broadcast_manager.get_total_members()
    
    keyboard = [[
        InlineKeyboardButton("⬅️ Back to Admin Panel", callback_data="admin_panel")
    ]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        f"📢 **Broadcast Message**\n\n"
        f"👥 Total Users: {total_users}\n\n"
        f"To start broadcast, use:\n"
        f"`/broadcast`\n\n"
        f"This will guide you through the broadcast process.",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def handle_admin_broadcast_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show broadcast history in admin panel"""
    query = update.callback_query
    await query.answer()
    
    history = broadcast_manager.get_broadcast_history(limit=5)
    stats = broadcast_manager.get_broadcast_stats()
    
    keyboard = [[
        InlineKeyboardButton("⬅️ Back to Admin Panel", callback_data="admin_panel")
    ]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if not history:
        await query.edit_message_text(
            "📊 No broadcast history yet.",
            reply_markup=reply_markup
        )
        return
    
    text = f"📊 **Broadcast History**\n\n"
    text += f"📢 Total: {stats['total_broadcasts']}\n"
    text += f"✅ Sent: {stats['total_messages_sent']}\n"
    text += f"📈 Success Rate: {stats['success_rate']}%\n\n"
    text += "**Recent Broadcasts:**\n\n"
    
    for i, h in enumerate(history, 1):
        text += f"{i}. {h['message_text']}\n"
        text += f"   Success: {h['successful']}/{h['total_users']} | {h['date']}\n\n"
    
    await query.edit_message_text(
        text=text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def handle_admin_recent_members(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show recent members in admin panel"""
    query = update.callback_query
    await query.answer()
    
    members = broadcast_manager.get_recent_members(limit=8)
    total = broadcast_manager.get_total_members()
    
    keyboard = [[
        InlineKeyboardButton("⬅️ Back to Admin Panel", callback_data="admin_panel")
    ]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if not members:
        await query.edit_message_text(
            "👥 No members yet.",
            reply_markup=reply_markup
        )
        return
    
    text = f"🎉 **Recent Members**\n\n"
    text += f"📊 Total: {total}\n\n"
    
    for i, m in enumerate(members, 1):
        name = m['first_name']
        if m['last_name']:
            name += f" {m['last_name']}"
        username = f"@{m['username']}" if m['username'] else "No username"
        
        text += f"{i}. {name}\n"
        text += f"   {username} | `{m['user_id']}`\n\n"
    
    await query.edit_message_text(
        text=text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

def register_enhanced_admin_handlers(application):
    """Register enhanced admin panel handlers"""
    application.add_handler(CommandHandler('adminpanel', enhanced_admin_panel))
    application.add_handler(CallbackQueryHandler(enhanced_admin_panel, pattern="^admin_panel$"))
    application.add_handler(CallbackQueryHandler(enhanced_admin_panel, pattern="^admin_refresh$"))
    application.add_handler(CallbackQueryHandler(handle_admin_broadcast, pattern="^admin_broadcast$"))
    application.add_handler(CallbackQueryHandler(handle_admin_broadcast_history, pattern="^admin_broadcast_history$"))
    application.add_handler(CallbackQueryHandler(handle_admin_recent_members, pattern="^admin_recent_members$"))
    
    logger.info("✅ Enhanced admin panel handlers registered")

__all__ = ['register_enhanced_admin_handlers', 'enhanced_admin_panel']

#!/usr/bin/env python3
"""Enhanced Admin Panel with Broadcast & Member Management"""
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CommandHandler, CallbackQueryHandler, ContextTypes
import broadcast_manager
import bot_manager

logger = logging.getLogger(__name__)

# Admin IDs - UPDATED
ADMIN_IDS = [5451167865, 1529815801]

async def enhanced_admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show enhanced admin panel with all features"""
    user_id = update.effective_user.id
    
    if user_id not in ADMIN_IDS:
        if update.callback_query:
            await update.callback_query.answer("⛔ Unauthorized!", show_alert=True)
        else:
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

async def handle_admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show statistics in admin panel"""
    query = update.callback_query
    await query.answer()
    
    total_users = broadcast_manager.get_total_members()
    bot_stats = bot_manager.get_client_bot_stats()
    broadcast_stats = broadcast_manager.get_broadcast_stats()
    
    keyboard = [[
        InlineKeyboardButton("⬅️ Back to Admin Panel", callback_data="admin_panel")
    ]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = (
        f"📊 **Statistics**\n\n"
        f"👥 **Users:**\n"
        f"• Total Members: {total_users}\n\n"
        f"🤖 **Client Bots:**\n"
        f"• Total Bots: {bot_stats['total_bots']}\n"
        f"• Active Bots: {bot_stats['active_bots']}\n"
        f"• Pending Approvals: {bot_stats['pending_approvals']}\n"
        f"• Total Bot Users: {bot_stats['total_users']}\n"
        f"• Total Bot Messages: {bot_stats['total_messages']}\n\n"
        f"📢 **Broadcasts:**\n"
        f"• Total Broadcasts: {broadcast_stats['total_broadcasts']}\n"
        f"• Messages Sent: {broadcast_stats['total_messages_sent']}\n"
        f"• Success Rate: {broadcast_stats['success_rate']}%"
    )
    
    await query.edit_message_text(
        text=text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def handle_admin_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user list in admin panel"""
    query = update.callback_query
    await query.answer()
    
    members = broadcast_manager.get_recent_members(limit=10)
    total = broadcast_manager.get_total_members()
    
    keyboard = [[
        InlineKeyboardButton("⬅️ Back to Admin Panel", callback_data="admin_panel")
    ]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if not members:
        await query.edit_message_text(
            "👥 No users yet.",
            reply_markup=reply_markup
        )
        return
    
    text = f"👥 **User List** (Top 10)\n\n"
    text += f"📊 Total: {total}\n\n"
    
    for i, m in enumerate(members, 1):
        name = m['first_name']
        if m['last_name']:
            name += f" {m['last_name']}"
        username = f"@{m['username']}" if m['username'] else "No username"
        
        text += f"{i}. {name}\n"
        text += f"   {username} | ID: `{m['user_id']}`\n\n"
    
    await query.edit_message_text(
        text=text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def handle_admin_client_bots(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show client bots in admin panel"""
    query = update.callback_query
    await query.answer()
    
    bots = bot_manager.get_all_client_bots()
    
    keyboard = [[
        InlineKeyboardButton("⬅️ Back to Admin Panel", callback_data="admin_panel")
    ]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if not bots:
        await query.edit_message_text(
            "🤖 No client bots yet.\n\nUse /addbot <token> to add a bot.",
            reply_markup=reply_markup
        )
        return
    
    text = f"🤖 **Client Bots** (Top 5)\n\n"
    
    for i, b in enumerate(bots[:5], 1):
        status = "✅" if b[5] else "❌"
        approved = "✔️" if b[6] else "⏳"
        running = "🟢" if bot_manager.is_bot_running(b[0]) else "🔴"
        
        text += f"{i}. {running} {status} @{b[1]}\n"
        text += f"   ID: {b[0]} | Owner: @{b[3]}\n"
        text += f"   Approved: {approved} | Users: {b[7]}\n\n"
    
    text += "\nUse /listbots for full list"
    
    await query.edit_message_text(
        text=text,
        reply_markup=reply_markup
    )

async def handle_admin_pending(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show pending bot approvals"""
    query = update.callback_query
    await query.answer()
    
    pending = bot_manager.get_pending_approvals()
    
    keyboard = [[
        InlineKeyboardButton("⬅️ Back to Admin Panel", callback_data="admin_panel")
    ]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if not pending:
        await query.edit_message_text(
            "✅ No pending approvals!",
            reply_markup=reply_markup
        )
        return
    
    text = f"⏳ **Pending Approvals**\n\n"
    
    for i, p in enumerate(pending[:5], 1):
        text += f"{i}. @{p[1]} ({p[2]})\n"
        text += f"   ID: {p[0]} | Owner: {p[4]} (@{p[3]})\n"
        text += f"   Date: {p[5]}\n\n"
    
    text += "\nUse /approvebot <id> to approve"
    
    await query.edit_message_text(
        text=text,
        reply_markup=reply_markup
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
        msg_preview = h['message_text'][:30] + "..." if len(h['message_text']) > 30 else h['message_text']
        text += f"{i}. {msg_preview}\n"
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

async def handle_admin_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle back button - return to main menu"""
    query = update.callback_query
    await query.answer()
    
    # Import here to avoid circular import
    from app import main_menu_keyboard, status_text, is_admin
    
    user_id = query.from_user.id
    await query.edit_message_text(
        "Main menu:\n\n" + status_text(context),
        reply_markup=main_menu_keyboard(is_admin(user_id))
    )

def register_enhanced_admin_handlers(application):
    """Register enhanced admin panel handlers"""
    # Command handler
    application.add_handler(CommandHandler('adminpanel', enhanced_admin_panel))
    
    # Main panel callbacks
    application.add_handler(CallbackQueryHandler(enhanced_admin_panel, pattern="^admin_panel$"))
    application.add_handler(CallbackQueryHandler(enhanced_admin_panel, pattern="^admin_refresh$"))
    
    # Feature callbacks
    application.add_handler(CallbackQueryHandler(handle_admin_stats, pattern="^admin_stats$"))
    application.add_handler(CallbackQueryHandler(handle_admin_users, pattern="^admin_users$"))
    application.add_handler(CallbackQueryHandler(handle_admin_client_bots, pattern="^admin_client_bots$"))
    application.add_handler(CallbackQueryHandler(handle_admin_pending, pattern="^admin_pending$"))
    application.add_handler(CallbackQueryHandler(handle_admin_broadcast, pattern="^admin_broadcast$"))
    application.add_handler(CallbackQueryHandler(handle_admin_broadcast_history, pattern="^admin_broadcast_history$"))
    application.add_handler(CallbackQueryHandler(handle_admin_recent_members, pattern="^admin_recent_members$"))
    application.add_handler(CallbackQueryHandler(handle_admin_back, pattern="^admin_back$"))
    
    logger.info("✅ Enhanced admin panel handlers registered")

__all__ = ['register_enhanced_admin_handlers', 'enhanced_admin_panel']

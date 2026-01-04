#!/usr/bin/env python3
"""Broadcast System - Master & Client Bot Broadcasting"""
import logging
import sqlite3
import asyncio
from datetime import datetime
from typing import List, Optional
from telegram import Bot, Update
from telegram.ext import ContextTypes
import bot_manager

logger = logging.getLogger(__name__)

# Admin notification settings
ADMIN_IDS = [7827293530]  # Update with your admin IDs

def init_broadcast_db():
    """Initialize broadcast and user tracking database"""
    conn = sqlite3.connect('bot_users.db')
    c = conn.cursor()
    
    # Client bot users table
    c.execute('''CREATE TABLE IF NOT EXISTS client_bot_users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        bot_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        username TEXT,
        first_name TEXT,
        last_name TEXT,
        joined_date TEXT NOT NULL,
        is_active INTEGER DEFAULT 1,
        last_interaction TEXT,
        UNIQUE(bot_id, user_id)
    )''')
    
    # Broadcast history table
    c.execute('''CREATE TABLE IF NOT EXISTS broadcast_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        broadcast_type TEXT NOT NULL,
        bot_id INTEGER,
        sender_id INTEGER NOT NULL,
        message_text TEXT NOT NULL,
        sent_count INTEGER DEFAULT 0,
        failed_count INTEGER DEFAULT 0,
        sent_date TEXT NOT NULL
    )''')
    
    conn.commit()
    conn.close()
    logger.info("Broadcast database initialized")

def add_client_bot_user(bot_id: int, user_id: int, username: str, first_name: str, last_name: str = None) -> tuple:
    """Add or update a client bot user"""
    conn = sqlite3.connect('bot_users.db')
    c = conn.cursor()
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    try:
        # Check if user exists
        c.execute('SELECT id FROM client_bot_users WHERE bot_id = ? AND user_id = ?', (bot_id, user_id))
        existing = c.fetchone()
        
        if existing:
            # Update existing user
            c.execute('''UPDATE client_bot_users 
                        SET username = ?, first_name = ?, last_name = ?, is_active = 1, last_interaction = ?
                        WHERE bot_id = ? AND user_id = ?''',
                     (username, first_name, last_name, now, bot_id, user_id))
            conn.commit()
            return (False, "User updated")  # False = not new
        else:
            # Add new user
            c.execute('''INSERT INTO client_bot_users 
                        (bot_id, user_id, username, first_name, last_name, joined_date, last_interaction)
                        VALUES (?, ?, ?, ?, ?, ?, ?)''',
                     (bot_id, user_id, username, first_name, last_name, now, now))
            conn.commit()
            
            # Update bot stats
            bot_manager.update_bot_stats(bot_id, users=1)
            
            return (True, "New user added")  # True = new user
    except Exception as e:
        logger.error(f"Error adding user: {e}")
        return (False, str(e))
    finally:
        conn.close()

def get_client_bot_users(bot_id: int) -> List[int]:
    """Get all active user IDs for a client bot"""
    conn = sqlite3.connect('bot_users.db')
    c = conn.cursor()
    try:
        c.execute('SELECT user_id FROM client_bot_users WHERE bot_id = ? AND is_active = 1', (bot_id,))
        return [row[0] for row in c.fetchall()]
    finally:
        conn.close()

def get_all_client_bot_users() -> List[tuple]:
    """Get all active users across all client bots with bot info"""
    conn = sqlite3.connect('bot_users.db')
    c = conn.cursor()
    try:
        c.execute('''SELECT DISTINCT cbu.user_id, cb.bot_id, cb.bot_token 
                    FROM client_bot_users cbu
                    JOIN client_bots cb ON cbu.bot_id = cb.bot_id
                    WHERE cbu.is_active = 1 AND cb.is_active = 1''')
        return c.fetchall()
    finally:
        conn.close()

def get_user_stats(bot_id: int = None) -> dict:
    """Get user statistics"""
    conn = sqlite3.connect('bot_users.db')
    c = conn.cursor()
    try:
        if bot_id:
            c.execute('SELECT COUNT(*) FROM client_bot_users WHERE bot_id = ? AND is_active = 1', (bot_id,))
            active = c.fetchone()[0]
            c.execute('SELECT COUNT(*) FROM client_bot_users WHERE bot_id = ?', (bot_id,))
            total = c.fetchone()[0]
        else:
            c.execute('SELECT COUNT(*) FROM client_bot_users WHERE is_active = 1')
            active = c.fetchone()[0]
            c.execute('SELECT COUNT(*) FROM client_bot_users')
            total = c.fetchone()[0]
        
        return {'active_users': active, 'total_users': total}
    finally:
        conn.close()

async def master_broadcast(bot_token: str, message_text: str, sender_id: int) -> dict:
    """Master broadcast - Send message to all client bot users"""
    try:
        users_data = get_all_client_bot_users()
        sent_count = 0
        failed_count = 0
        
        # Group users by bot
        bot_users = {}
        for user_id, bot_id, token in users_data:
            if bot_id not in bot_users:
                bot_users[bot_id] = {'token': token, 'users': []}
            bot_users[bot_id]['users'].append(user_id)
        
        # Send to each bot's users
        for bot_id, data in bot_users.items():
            try:
                bot = Bot(token=data['token'])
                for user_id in data['users']:
                    try:
                        await bot.send_message(
                            chat_id=user_id,
                            text=f"📢 **Broadcast Message**\n\n{message_text}\n\n_From Master Admin_",
                            parse_mode='Markdown'
                        )
                        sent_count += 1
                        await asyncio.sleep(0.05)  # Rate limiting
                    except Exception as e:
                        failed_count += 1
                        logger.error(f"Failed to send to user {user_id}: {e}")
                await bot.close()
            except Exception as e:
                logger.error(f"Error with bot {bot_id}: {e}")
                failed_count += len(data['users'])
        
        # Save to history
        conn = sqlite3.connect('bot_users.db')
        c = conn.cursor()
        c.execute('''INSERT INTO broadcast_history 
                    (broadcast_type, sender_id, message_text, sent_count, failed_count, sent_date)
                    VALUES (?, ?, ?, ?, ?, ?)''',
                 ('master', sender_id, message_text, sent_count, failed_count, 
                  datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        conn.commit()
        conn.close()
        
        return {
            'success': True,
            'sent': sent_count,
            'failed': failed_count,
            'total': sent_count + failed_count
        }
    except Exception as e:
        logger.error(f"Master broadcast error: {e}")
        return {'success': False, 'error': str(e)}

async def client_broadcast(bot_id: int, message_text: str, sender_id: int) -> dict:
    """Client broadcast - Send message to specific bot's users only"""
    try:
        # Get bot info
        bot_info = bot_manager.get_client_bot(bot_id)
        if not bot_info:
            return {'success': False, 'error': 'Bot not found'}
        
        # Check ownership
        if bot_info['owner_user_id'] != sender_id and sender_id not in ADMIN_IDS:
            return {'success': False, 'error': 'Unauthorized'}
        
        # Get users
        user_ids = get_client_bot_users(bot_id)
        if not user_ids:
            return {'success': False, 'error': 'No users found'}
        
        bot = Bot(token=bot_info['bot_token'])
        sent_count = 0
        failed_count = 0
        
        for user_id in user_ids:
            try:
                await bot.send_message(
                    chat_id=user_id,
                    text=f"📢 **Broadcast Message**\n\n{message_text}\n\n_From Bot Admin_",
                    parse_mode='Markdown'
                )
                sent_count += 1
                await asyncio.sleep(0.05)
            except Exception as e:
                failed_count += 1
                logger.error(f"Failed to send to user {user_id}: {e}")
        
        await bot.close()
        
        # Save to history
        conn = sqlite3.connect('bot_users.db')
        c = conn.cursor()
        c.execute('''INSERT INTO broadcast_history 
                    (broadcast_type, bot_id, sender_id, message_text, sent_count, failed_count, sent_date)
                    VALUES (?, ?, ?, ?, ?, ?, ?)''',
                 ('client', bot_id, sender_id, message_text, sent_count, failed_count,
                  datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        conn.commit()
        conn.close()
        
        return {
            'success': True,
            'sent': sent_count,
            'failed': failed_count,
            'total': len(user_ids)
        }
    except Exception as e:
        logger.error(f"Client broadcast error: {e}")
        return {'success': False, 'error': str(e)}

async def notify_admin_new_user(admin_bot_token: str, bot_id: int, user_id: int, username: str, first_name: str):
    """Send notification to admins when new user joins a client bot"""
    try:
        bot_info = bot_manager.get_client_bot(bot_id)
        if not bot_info:
            return
        
        notification_text = (
            f"🆕 **New User Joined!**\n\n"
            f"🤖 Bot: @{bot_info['bot_username']}\n"
            f"🆔 Bot ID: {bot_id}\n\n"
            f"👤 User: {first_name}\n"
            f"📝 Username: @{username if username else 'No username'}\n"
            f"🔢 User ID: `{user_id}`\n\n"
            f"📊 Total Users: {get_user_stats(bot_id)['active_users']}"
        )
        
        admin_bot = Bot(token=admin_bot_token)
        for admin_id in ADMIN_IDS:
            try:
                await admin_bot.send_message(
                    chat_id=admin_id,
                    text=notification_text,
                    parse_mode='Markdown'
                )
            except Exception as e:
                logger.error(f"Failed to notify admin {admin_id}: {e}")
        await admin_bot.close()
    except Exception as e:
        logger.error(f"Error sending admin notification: {e}")

# Export functions
__all__ = [
    'init_broadcast_db',
    'add_client_bot_user',
    'get_client_bot_users',
    'master_broadcast',
    'client_broadcast',
    'notify_admin_new_user',
    'get_user_stats'
]

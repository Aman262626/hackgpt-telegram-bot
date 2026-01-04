#!/usr/bin/env python3
"""Broadcast Manager - Message broadcasting system with member tracking"""
import logging
import sqlite3
import asyncio
from datetime import datetime
from typing import List, Optional
from telegram import Bot
from telegram.error import TelegramError

logger = logging.getLogger(__name__)

# Store pending broadcasts per admin
pending_broadcasts = {}

def init_broadcast_db():
    """Initialize broadcast and member tracking database"""
    conn = sqlite3.connect('bot_users.db')
    c = conn.cursor()
    
    # Broadcast history table
    c.execute('''CREATE TABLE IF NOT EXISTS broadcast_history (
        broadcast_id INTEGER PRIMARY KEY AUTOINCREMENT,
        admin_user_id INTEGER NOT NULL,
        message_text TEXT NOT NULL,
        total_users INTEGER DEFAULT 0,
        successful_sends INTEGER DEFAULT 0,
        failed_sends INTEGER DEFAULT 0,
        broadcast_date TEXT NOT NULL,
        status TEXT DEFAULT 'completed'
    )''')
    
    # Member join notifications table
    c.execute('''CREATE TABLE IF NOT EXISTS member_notifications (
        notification_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        username TEXT,
        first_name TEXT,
        last_name TEXT,
        join_date TEXT NOT NULL,
        notified INTEGER DEFAULT 0
    )''')
    
    conn.commit()
    conn.close()
    logger.info("Broadcast database initialized")

def log_member_join(user_id: int, username: str, first_name: str, last_name: str) -> bool:
    """Log new member join"""
    try:
        conn = sqlite3.connect('bot_users.db')
        c = conn.cursor()
        
        # Check if already logged
        c.execute('SELECT user_id FROM member_notifications WHERE user_id = ?', (user_id,))
        if c.fetchone():
            conn.close()
            return False  # Already logged
        
        # Insert new member
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        c.execute('''INSERT INTO member_notifications 
                     (user_id, username, first_name, last_name, join_date, notified)
                     VALUES (?, ?, ?, ?, ?, 0)''',
                  (user_id, username, first_name, last_name, now))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Error logging member join: {e}")
        return False

async def notify_admin_new_member(bot: Bot, admin_id: int, user_id: int, username: str, first_name: str, last_name: str) -> bool:
    """Send notification to admin about new member"""
    try:
        full_name = f"{first_name} {last_name}" if last_name else first_name
        username_text = f"@{username}" if username else "No username"
        
        message = (
            f"🎉 **New Member Joined!**\n\n"
            f"👤 Name: {full_name}\n"
            f"🆔 User ID: `{user_id}`\n"
            f"📱 Username: {username_text}\n"
            f"📅 Joined: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            f"Total Members: {get_total_members()}"
        )
        
        await bot.send_message(
            chat_id=admin_id,
            text=message,
            parse_mode='Markdown'
        )
        
        # Mark as notified
        conn = sqlite3.connect('bot_users.db')
        c = conn.cursor()
        c.execute('UPDATE member_notifications SET notified = 1 WHERE user_id = ?', (user_id,))
        conn.commit()
        conn.close()
        
        return True
    except Exception as e:
        logger.error(f"Error notifying admin: {e}")
        return False

def get_total_members() -> int:
    """Get total member count"""
    try:
        conn = sqlite3.connect('bot_users.db')
        c = conn.cursor()
        c.execute('SELECT COUNT(DISTINCT user_id) FROM users')
        count = c.fetchone()[0]
        conn.close()
        return count
    except:
        return 0

def get_recent_members(limit: int = 10) -> List[dict]:
    """Get recent members who joined"""
    try:
        conn = sqlite3.connect('bot_users.db')
        c = conn.cursor()
        c.execute('''SELECT user_id, username, first_name, last_name, join_date 
                     FROM member_notifications 
                     ORDER BY join_date DESC LIMIT ?''', (limit,))
        members = c.fetchall()
        conn.close()
        
        return [{
            'user_id': m[0],
            'username': m[1],
            'first_name': m[2],
            'last_name': m[3],
            'join_date': m[4]
        } for m in members]
    except Exception as e:
        logger.error(f"Error getting recent members: {e}")
        return []

def save_pending_broadcast(admin_id: int, message_text: str, media_type: str = None, media_id: str = None):
    """Save broadcast message for admin confirmation"""
    pending_broadcasts[admin_id] = {
        'message_text': message_text,
        'media_type': media_type,
        'media_id': media_id,
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }

def get_pending_broadcast(admin_id: int) -> Optional[dict]:
    """Get pending broadcast for admin"""
    return pending_broadcasts.get(admin_id)

def clear_pending_broadcast(admin_id: int):
    """Clear pending broadcast for admin"""
    if admin_id in pending_broadcasts:
        del pending_broadcasts[admin_id]

async def execute_broadcast(bot: Bot, admin_id: int, message_text: str, user_ids: List[int] = None) -> dict:
    """Execute broadcast message to all users or specified users"""
    try:
        # Get all user IDs if not provided
        if user_ids is None:
            conn = sqlite3.connect('bot_users.db')
            c = conn.cursor()
            c.execute('SELECT DISTINCT user_id FROM users')
            user_ids = [row[0] for row in c.fetchall()]
            conn.close()
        
        total_users = len(user_ids)
        successful = 0
        failed = 0
        
        logger.info(f"Starting broadcast to {total_users} users")
        
        # Send messages
        for user_id in user_ids:
            try:
                await bot.send_message(
                    chat_id=user_id,
                    text=message_text,
                    parse_mode='Markdown'
                )
                successful += 1
                
                # Small delay to avoid rate limits
                await asyncio.sleep(0.05)
            except TelegramError as e:
                failed += 1
                logger.warning(f"Failed to send to {user_id}: {e}")
                continue
        
        # Save broadcast history
        conn = sqlite3.connect('bot_users.db')
        c = conn.cursor()
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        c.execute('''INSERT INTO broadcast_history 
                     (admin_user_id, message_text, total_users, successful_sends, failed_sends, broadcast_date, status)
                     VALUES (?, ?, ?, ?, ?, ?, 'completed')''',
                  (admin_id, message_text, total_users, successful, failed, now))
        conn.commit()
        conn.close()
        
        result = {
            'total': total_users,
            'successful': successful,
            'failed': failed,
            'success_rate': round((successful/total_users)*100, 2) if total_users > 0 else 0
        }
        
        logger.info(f"Broadcast completed: {result}")
        return result
        
    except Exception as e:
        logger.error(f"Error executing broadcast: {e}")
        return {'total': 0, 'successful': 0, 'failed': 0, 'success_rate': 0, 'error': str(e)}

def get_broadcast_history(admin_id: int = None, limit: int = 10) -> List[dict]:
    """Get broadcast history"""
    try:
        conn = sqlite3.connect('bot_users.db')
        c = conn.cursor()
        
        if admin_id:
            c.execute('''SELECT broadcast_id, message_text, total_users, successful_sends, 
                         failed_sends, broadcast_date, status 
                         FROM broadcast_history 
                         WHERE admin_user_id = ?
                         ORDER BY broadcast_date DESC LIMIT ?''', (admin_id, limit))
        else:
            c.execute('''SELECT broadcast_id, message_text, total_users, successful_sends, 
                         failed_sends, broadcast_date, status 
                         FROM broadcast_history 
                         ORDER BY broadcast_date DESC LIMIT ?''', (limit,))
        
        history = c.fetchall()
        conn.close()
        
        return [{
            'broadcast_id': h[0],
            'message_text': h[1][:50] + '...' if len(h[1]) > 50 else h[1],
            'total_users': h[2],
            'successful': h[3],
            'failed': h[4],
            'date': h[5],
            'status': h[6]
        } for h in history]
    except Exception as e:
        logger.error(f"Error getting broadcast history: {e}")
        return []

def get_broadcast_stats() -> dict:
    """Get overall broadcast statistics"""
    try:
        conn = sqlite3.connect('bot_users.db')
        c = conn.cursor()
        
        c.execute('SELECT COUNT(*) FROM broadcast_history')
        total_broadcasts = c.fetchone()[0]
        
        c.execute('SELECT SUM(successful_sends) FROM broadcast_history')
        total_sent = c.fetchone()[0] or 0
        
        c.execute('SELECT SUM(failed_sends) FROM broadcast_history')
        total_failed = c.fetchone()[0] or 0
        
        conn.close()
        
        return {
            'total_broadcasts': total_broadcasts,
            'total_messages_sent': total_sent,
            'total_failed': total_failed,
            'success_rate': round((total_sent/(total_sent+total_failed))*100, 2) if (total_sent+total_failed) > 0 else 0
        }
    except Exception as e:
        logger.error(f"Error getting broadcast stats: {e}")
        return {'total_broadcasts': 0, 'total_messages_sent': 0, 'total_failed': 0, 'success_rate': 0}

# Export functions
__all__ = [
    'init_broadcast_db',
    'log_member_join',
    'notify_admin_new_member',
    'get_total_members',
    'get_recent_members',
    'save_pending_broadcast',
    'get_pending_broadcast',
    'clear_pending_broadcast',
    'execute_broadcast',
    'get_broadcast_history',
    'get_broadcast_stats'
]

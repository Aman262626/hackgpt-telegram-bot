#!/usr/bin/env python3
"""Multi-Bot Management System - Bot Manager Module"""
import logging
import asyncio
import sqlite3
from datetime import datetime
from typing import Dict, Optional
from telegram import Bot
from telegram.ext import Application

logger = logging.getLogger(__name__)

# Global registry of running client bots
client_bots: Dict[int, Application] = {}
bot_threads: Dict[int, asyncio.Task] = {}

def init_client_bots_db():
    """Initialize client bots database table"""
    conn = sqlite3.connect('bot_users.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS client_bots (
        bot_id INTEGER PRIMARY KEY AUTOINCREMENT,
        bot_token TEXT UNIQUE NOT NULL,
        bot_username TEXT,
        bot_first_name TEXT,
        owner_user_id INTEGER NOT NULL,
        owner_username TEXT,
        owner_name TEXT,
        created_date TEXT NOT NULL,
        is_active INTEGER DEFAULT 0,
        is_approved INTEGER DEFAULT 0,
        last_active TEXT,
        total_users INTEGER DEFAULT 0,
        total_messages INTEGER DEFAULT 0
    )''')
    conn.commit()
    conn.close()
    logger.info("Client bots database initialized")

def verify_bot_token(bot_token: str) -> tuple:
    """Verify bot token synchronously"""
    try:
        # Create a new event loop for this thread if needed
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        async def _verify():
            try:
                bot = Bot(token=bot_token)
                bot_info = await bot.get_me()
                await bot.close()
                return (True, bot_info.username, bot_info.first_name)
            except Exception as e:
                return (False, None, str(e))
        
        # Run the async verification
        if loop.is_running():
            # If loop is already running, create a new one
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(lambda: asyncio.run(_verify()))
                return future.result(timeout=10)
        else:
            return loop.run_until_complete(_verify())
            
    except Exception as e:
        logger.error(f"Token verification error: {e}")
        return (False, None, str(e))

def add_client_bot_request(bot_token: str, owner_id: int, owner_username: str, owner_name: str) -> tuple:
    """Add a new client bot request (pending approval)"""
    conn = sqlite3.connect('bot_users.db')
    c = conn.cursor()
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    try:
        # Check if token already exists
        c.execute('SELECT bot_id, owner_user_id FROM client_bots WHERE bot_token = ?', (bot_token,))
        existing = c.fetchone()
        if existing:
            return (False, "Bot token already registered", None)
        
        # Verify token
        success, bot_username, bot_first_name = verify_bot_token(bot_token)
        if not success:
            error_msg = str(bot_first_name)[:100] if bot_first_name else "Invalid token"
            return (False, f"Invalid bot token: {error_msg}", None)
        
        # Insert new bot request
        c.execute('''INSERT INTO client_bots 
                     (bot_token, bot_username, bot_first_name, owner_user_id, owner_username, owner_name, created_date, is_active, is_approved)
                     VALUES (?, ?, ?, ?, ?, ?, ?, 0, 0)''',
                  (bot_token, bot_username, bot_first_name, owner_id, owner_username, owner_name, now))
        bot_id = c.lastrowid
        conn.commit()
        return (True, f"Bot @{bot_username} registered! Waiting for admin approval.", bot_id)
    except Exception as e:
        logger.error(f"Error adding bot: {e}")
        return (False, f"Error: {str(e)[:100]}", None)
    finally:
        conn.close()

def approve_client_bot(bot_id: int) -> tuple:
    """Approve a client bot request"""
    conn = sqlite3.connect('bot_users.db')
    c = conn.cursor()
    try:
        c.execute('UPDATE client_bots SET is_approved = 1 WHERE bot_id = ?', (bot_id,))
        conn.commit()
        if c.rowcount > 0:
            return (True, "Bot approved successfully!")
        return (False, "Bot not found")
    finally:
        conn.close()

def enable_client_bot(bot_id: int) -> tuple:
    """Enable/activate a client bot"""
    conn = sqlite3.connect('bot_users.db')
    c = conn.cursor()
    try:
        c.execute('SELECT is_approved FROM client_bots WHERE bot_id = ?', (bot_id,))
        result = c.fetchone()
        if not result:
            return (False, "Bot not found")
        if result[0] != 1:
            return (False, "Bot not approved yet")
        
        c.execute('UPDATE client_bots SET is_active = 1, last_active = ? WHERE bot_id = ?',
                  (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), bot_id))
        conn.commit()
        return (True, "Bot enabled successfully!")
    finally:
        conn.close()

def disable_client_bot(bot_id: int) -> tuple:
    """Disable/deactivate a client bot"""
    conn = sqlite3.connect('bot_users.db')
    c = conn.cursor()
    try:
        c.execute('UPDATE client_bots SET is_active = 0 WHERE bot_id = ?', (bot_id,))
        conn.commit()
        if c.rowcount > 0:
            return (True, "Bot disabled successfully!")
        return (False, "Bot not found")
    finally:
        conn.close()

def delete_client_bot(bot_id: int) -> tuple:
    """Delete a client bot completely"""
    conn = sqlite3.connect('bot_users.db')
    c = conn.cursor()
    try:
        c.execute('DELETE FROM client_bots WHERE bot_id = ?', (bot_id,))
        conn.commit()
        if c.rowcount > 0:
            return (True, "Bot deleted successfully!")
        return (False, "Bot not found")
    finally:
        conn.close()

def get_client_bot(bot_id: int) -> Optional[dict]:
    """Get client bot details"""
    conn = sqlite3.connect('bot_users.db')
    c = conn.cursor()
    try:
        c.execute('SELECT * FROM client_bots WHERE bot_id = ?', (bot_id,))
        result = c.fetchone()
        if result:
            return {
                'bot_id': result[0],
                'bot_token': result[1],
                'bot_username': result[2],
                'bot_first_name': result[3],
                'owner_user_id': result[4],
                'owner_username': result[5],
                'owner_name': result[6],
                'created_date': result[7],
                'is_active': result[8],
                'is_approved': result[9],
                'last_active': result[10],
                'total_users': result[11],
                'total_messages': result[12]
            }
        return None
    finally:
        conn.close()

def get_all_client_bots() -> list:
    """Get all client bots"""
    conn = sqlite3.connect('bot_users.db')
    c = conn.cursor()
    try:
        c.execute('SELECT bot_id, bot_username, bot_first_name, owner_username, owner_name, is_active, is_approved, total_users, total_messages FROM client_bots ORDER BY created_date DESC')
        return c.fetchall()
    finally:
        conn.close()

def get_user_client_bots(owner_id: int) -> list:
    """Get all client bots owned by a user"""
    conn = sqlite3.connect('bot_users.db')
    c = conn.cursor()
    try:
        c.execute('SELECT bot_id, bot_username, bot_first_name, is_active, is_approved, total_users, total_messages FROM client_bots WHERE owner_user_id = ? ORDER BY created_date DESC', (owner_id,))
        return c.fetchall()
    finally:
        conn.close()

def get_pending_approvals() -> list:
    """Get all pending bot approval requests"""
    conn = sqlite3.connect('bot_users.db')
    c = conn.cursor()
    try:
        c.execute('SELECT bot_id, bot_username, bot_first_name, owner_username, owner_name, created_date FROM client_bots WHERE is_approved = 0 ORDER BY created_date DESC')
        return c.fetchall()
    finally:
        conn.close()

def get_client_bot_stats() -> dict:
    """Get overall client bots statistics"""
    conn = sqlite3.connect('bot_users.db')
    c = conn.cursor()
    try:
        c.execute('SELECT COUNT(*) FROM client_bots')
        total = c.fetchone()[0]
        c.execute('SELECT COUNT(*) FROM client_bots WHERE is_active = 1')
        active = c.fetchone()[0]
        c.execute('SELECT COUNT(*) FROM client_bots WHERE is_approved = 0')
        pending = c.fetchone()[0]
        c.execute('SELECT SUM(total_users) FROM client_bots WHERE is_active = 1')
        total_users = c.fetchone()[0] or 0
        c.execute('SELECT SUM(total_messages) FROM client_bots WHERE is_active = 1')
        total_messages = c.fetchone()[0] or 0
        
        return {
            'total_bots': total,
            'active_bots': active,
            'pending_approvals': pending,
            'total_users': total_users,
            'total_messages': total_messages
        }
    finally:
        conn.close()

async def start_client_bot(bot_id: int, bot_token: str, setup_handlers_func) -> tuple:
    """Start a client bot instance"""
    try:
        if bot_id in client_bots:
            return (False, "Bot already running")
        
        # Create application
        application = Application.builder().token(bot_token).build()
        
        # Setup handlers using provided function
        setup_handlers_func(application, bot_id)
        
        # Initialize and start
        await application.initialize()
        await application.bot.delete_webhook(drop_pending_updates=True)
        await application.start()
        await application.updater.start_polling(allowed_updates=None, drop_pending_updates=True)
        
        # Store in registry
        client_bots[bot_id] = application
        
        logger.info(f"Client bot {bot_id} started successfully")
        return (True, "Bot started successfully")
    except Exception as e:
        logger.error(f"Error starting client bot {bot_id}: {e}")
        return (False, f"Error: {str(e)[:100]}")

async def stop_client_bot(bot_id: int) -> tuple:
    """Stop a running client bot instance"""
    try:
        if bot_id not in client_bots:
            return (False, "Bot not running")
        
        application = client_bots[bot_id]
        await application.updater.stop()
        await application.stop()
        await application.shutdown()
        
        del client_bots[bot_id]
        
        logger.info(f"Client bot {bot_id} stopped successfully")
        return (True, "Bot stopped successfully")
    except Exception as e:
        logger.error(f"Error stopping client bot {bot_id}: {e}")
        return (False, f"Error: {str(e)[:100]}")

def is_bot_running(bot_id: int) -> bool:
    """Check if a client bot is currently running"""
    return bot_id in client_bots

def get_running_bots() -> list:
    """Get list of all running bot IDs"""
    return list(client_bots.keys())

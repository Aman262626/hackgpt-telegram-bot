#!/usr/bin/env python3
"""Complete Integration Module - Auto-setup for all features"""
import logging
import sys

logger = logging.getLogger(__name__)

# Import all required modules
try:
    import bot_manager
    import broadcast_manager
    from client_bot_commands import register_client_bot_handlers
    from broadcast_commands import register_broadcast_handlers, handle_new_member_auto_notify
    from admin_panel_enhanced import register_enhanced_admin_handlers
    from startup_client_bots import schedule_auto_start
    import threading
except ImportError as e:
    logger.error(f"Import error: {e}")
    sys.exit(1)

def initialize_all_databases():
    """Initialize all database tables"""
    try:
        logger.info("Initializing databases...")
        bot_manager.init_client_bots_db()
        broadcast_manager.init_broadcast_db()
        logger.info("✅ All databases initialized")
        return True
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        return False

def register_all_handlers(application):
    """Register all command handlers"""
    try:
        logger.info("Registering handlers...")
        
        # Client bot management handlers
        register_client_bot_handlers(application)
        logger.info("✅ Client bot handlers registered")
        
        # Broadcast handlers
        register_broadcast_handlers(application)
        logger.info("✅ Broadcast handlers registered")
        
        # Enhanced admin panel handlers
        register_enhanced_admin_handlers(application)
        logger.info("✅ Admin panel handlers registered")
        
        logger.info("✅ All handlers registered successfully")
        return True
    except Exception as e:
        logger.error(f"Handler registration failed: {e}")
        return False

def start_background_tasks():
    """Start background tasks (client bots auto-start)"""
    try:
        logger.info("Starting background tasks...")
        threading.Thread(target=schedule_auto_start, daemon=True).start()
        logger.info("✅ Background tasks started")
        return True
    except Exception as e:
        logger.error(f"Background tasks failed: {e}")
        return False

async def handle_start_with_tracking(update, context):
    """Enhanced /start handler with member tracking"""
    # Track new member and notify admin
    await handle_new_member_auto_notify(update, context)
    
    # Return success for further handling
    return True

def setup_complete_integration(application, start_handler_exists=False):
    """Complete setup - Call this from your main app"""
    try:
        logger.info("🚀 Starting complete integration setup...")
        
        # Step 1: Initialize databases
        if not initialize_all_databases():
            logger.error("❌ Database setup failed")
            return False
        
        # Step 2: Register all handlers
        if not register_all_handlers(application):
            logger.error("❌ Handler registration failed")
            return False
        
        # Step 3: Start background tasks
        if not start_background_tasks():
            logger.warning("⚠️ Background tasks not started")
        
        logger.info("✅ Complete integration setup successful!")
        logger.info("📝 Available commands:")
        logger.info("   - /adminpanel - Enhanced admin panel")
        logger.info("   - /broadcast - Broadcast message")
        logger.info("   - /enablebot <id> - Enable client bot")
        logger.info("   - /disablebot <id> - Disable client bot")
        logger.info("   - /botstatus - Check bot status")
        logger.info("   - /recentmembers - View recent members")
        logger.info("   - /broadcasthistory - View broadcast history")
        
        return True
    except Exception as e:
        logger.error(f"❌ Complete integration setup failed: {e}")
        return False

# Export main function
__all__ = [
    'setup_complete_integration',
    'handle_start_with_tracking',
    'initialize_all_databases',
    'register_all_handlers',
    'start_background_tasks'
]

# Auto-run message
if __name__ == '__main__':
    print("""\n
╔══════════════════════════════════════════════════════════╗
║     🤖 COMPLETE INTEGRATION MODULE 🤖                    ║
╚══════════════════════════════════════════════════════════╝

✅ Features Included:
   📢 Broadcast System
   🎉 Member Join Notifications  
   🤖 Client Bot Management
   📊 Enhanced Admin Panel
   📈 Statistics & Analytics

📝 Integration Steps:

1️⃣  Import in your app.py:
    from complete_integration import setup_complete_integration, handle_start_with_tracking

2️⃣  After creating application, call:
    setup_complete_integration(application)

3️⃣  In your /start handler, add:
    await handle_start_with_tracking(update, context)

4️⃣  That's it! All features will work automatically.

🎯 New Commands Available:
   /adminpanel - Enhanced admin panel with all features
   /broadcast - Send broadcast message to all users
   /enablebot <id> - Start a client bot
   /disablebot <id> - Stop a client bot
   /botstatus - Check bot status
   /recentmembers - View recent members
   /broadcasthistory - View broadcast history

🚀 Ready to deploy!

""")

#!/usr/bin/env python3
"""Auto-startup script for client bots - Webhook Compatible"""
import logging
import asyncio
import time
from client_bot_runner import start_all_active_bots
import bot_manager

logger = logging.getLogger(__name__)

async def auto_start_bots():
    """Auto-start all active client bots after delay"""
    try:
        # Wait for main bot to initialize
        await asyncio.sleep(5)
        
        logger.info("🚀 Auto-starting active client bots...")
        started_count = await start_all_active_bots()
        logger.info(f"✅ Auto-started {started_count} client bots")
        return started_count
    except Exception as e:
        logger.error(f"❌ Error auto-starting bots: {e}")
        return 0

def schedule_auto_start():
    """Schedule auto-start in background"""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(auto_start_bots())
    except Exception as e:
        logger.error(f"Error in schedule_auto_start: {e}")

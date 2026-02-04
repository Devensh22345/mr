import logging
from datetime import datetime
from pyrogram import Client
from config import config
from database import db

async def log_to_main(message: str, level: str = "INFO"):
    """Log to main log group and database"""
    try:
        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        
        # Log to console
        print(f"[{timestamp}] [{level}] {message}")
        
        # Log to database
        await db.logs.insert_one({
            "timestamp": datetime.utcnow(),
            "level": level,
            "message": message
        })
        
        # Send to main log group if configured
        if config.MAIN_LOG_GROUP:
            from bot import bot
            try:
                await bot.send_message(
                    config.MAIN_LOG_GROUP,
                    f"`[{timestamp}] [{level}]`\n{message}"
                )
            except Exception as e:
                print(f"Failed to send log to group: {e}")
    except Exception as e:
        print(f"Logging error: {e}")

async def log_to_channel(channel_id: int, message: str, bot_instance: Client = None):
    """Log to specific channel"""
    try:
        if channel_id:
            if bot_instance:
                await bot_instance.send_message(channel_id, message)
            else:
                from bot import bot
                await bot.send_message(channel_id, message)
    except Exception as e:
        await log_to_main(f"Error logging to channel {channel_id}: {e}", "ERROR")

async def log_action(user_id: int, action: str, details: str = None):
    """Log user action"""
    user_info = await db.users.find_one({"user_id": user_id})
    username = user_info.get("username", str(user_id)) if user_info else str(user_id)
    
    log_msg = f"👤 User: {username}\n🔧 Action: {action}"
    if details:
        log_msg += f"\n📝 Details: {details}"
    
    await log_to_main(log_msg, "ACTION")

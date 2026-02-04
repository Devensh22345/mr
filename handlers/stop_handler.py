from pyrogram import filters
from pyrogram.types import Message
from config import config
from utils.logger import log_action

class StopHandler:
    def __init__(self, bot):
        self.bot = bot
    
    async def handle_stop_command(self, message: Message):
        """Handle /stop command to stop reporting"""
        if config.stop_reporting:
            await message.reply("⚠️ Reporting was already stopped.")
        else:
            config.stop_reporting = True
            await message.reply("⏹️ **Reporting stopped!**\nAll reporting operations will be stopped.")
            
            await log_action(message.from_user.id, "Stopped reporting", "Admin")
    
    async def handle_cancel_command(self, message: Message):
        """Handle /cancel command to stop current operation"""
        if config.cancel_operation:
            await message.reply("⚠️ Operation was already cancelled.")
        else:
            config.cancel_operation = True
            await message.reply("❌ **Operation cancelled!**\nCurrent process will be stopped.")
            
            # Reset after short delay
            import asyncio
            await asyncio.sleep(2)
            config.cancel_operation = False
            
            await log_action(message.from_user.id, "Cancelled operation", "Admin")

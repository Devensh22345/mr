from pyrogram import filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram import Client
import asyncio
from database import db
from config import config
from utils.logger import log_to_channel, log_action
import re

class LeaveHandler:
    def __init__(self, bot):
        self.bot = bot
        self.leave_tasks = {}
    
    async def handle_leave_command(self, message: Message):
        if not config.is_admin(message.from_user.id):
            await message.reply("❌ Admin only command.")
            return
        
        await message.reply(
            "👋 **Leave Groups/Channels**\n\n"
            "Send the group/channel link, username, or ID to leave:\n\n"
            "Examples:\n"
            "• `@groupname`\n"
            "• `t.me/groupname`\n"
            "• `-1001234567890` (group ID)\n\n"
            "For chat folders, send the folder link.\n\n"
            "Type /cancel to cancel."
        )
        
        self.leave_tasks[message.from_user.id] = {"step": "waiting_link"}
        
        await log_action(message.from_user.id, "Started leave process", "Admin")
    
    @staticmethod
    def is_valid_link(self, link: str) -> bool:
        """Check if link is a valid Telegram link"""
        patterns = [
            r'^@[a-zA-Z0-9_]{5,32}$',
            r'^t\.me/[a-zA-Z0-9_]{5,32}$',
            r'^https://t\.me/[a-zA-Z0-9_]{5,32}$',
            r'^https://t\.me/addlist/[a-zA-Z0-9]+$',  # Chat folder link
            r'^-100\d+$',
        ]
        
        for pattern in patterns:
            if re.match(pattern, link):
                return True
        
        return False
    
    async def handle_callback(self, callback_query: CallbackQuery):
        data = callback_query.data
        
        if data.startswith("start_leave:"):
            target_user_id = int(data.split(":")[1])
            
            if target_user_id not in self.leave_tasks:
                await callback_query.answer("❌ Task expired", show_alert=True)
                return
            
            task_data = self.leave_tasks[target_user_id]
            await self.execute_leave(callback_query, task_data)
        
        elif data == "cancel_leave":
            user_id = callback_query.from_user.id
            if user_id in self.leave_tasks:
                del self.leave_tasks[user_id]
            
            await callback_query.message.edit_text("❌ Leave operation cancelled.")
        
        await callback_query.answer()
    
    async def process_message(self, message: Message):
        # Skip commands
        if message.text and message.text.startswith("/"):
            return
        
        user_id = message.from_user.id
        
        if user_id not in self.leave_tasks:
            return
        
        task_data = self.leave_tasks[user_id]
        
        if task_data.get("step") == "waiting_link":
            link = message.text.strip()
            
            if not link:
                await message.reply("❌ Invalid link. Please send a valid link.")
                return
            
            # Validate link
            if not self.is_valid_link(link):
                await message.reply("❌ Invalid link format. Please send a valid Telegram link.")
                return
            
            task_data["link"] = link
            task_data["step"] = "confirm"
            
            # Get active accounts
            accounts = await db.accounts.find({"is_active": True}).to_list(length=100)
            
            if not accounts:
                await message.reply("❌ No active accounts found.")
                del self.leave_tasks[user_id]
                return
            
            task_data["accounts"] = accounts
            
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Start Leaving", callback_data=f"start_leave:{user_id}")],
                [InlineKeyboardButton("❌ Cancel", callback_data="cancel_leave")]
            ])
            
            await message.reply(
                f"👋 **Leave Confirmation**\n\n"
                f"🔗 **Link:** `{link}`\n"
                f"📱 **Accounts:** {len(accounts)} active accounts\n\n"
                f"⚠️ **Are you sure you want to proceed?**",
                reply_markup=keyboard
            )
            
            self.leave_tasks[user_id] = task_data
    
    async def execute_leave(self, callback_query: CallbackQuery, task_data: dict):
        user_id = callback_query.from_user.id
        link = task_data["link"]
        accounts = task_data["accounts"]
        
        await callback_query.message.edit_text("🚀 Starting to leave...")
        
        success_count = 0
        fail_count = 0
        results = []
        
        # Log start
        if config.LEAVE_LOG_CHANNEL:
            log_msg = f"👋 **Leave Started**\n\n"
            log_msg += f"👤 **By:** {callback_query.from_user.mention}\n"
            log_msg += f"🔗 **Link:** `{link}`\n"
            log_msg += f"📱 **Accounts:** {len(accounts)}\n"
            await log_to_channel(config.LEAVE_LOG_CHANNEL, log_msg)
        
        from pyrogram import Client
        
        for i, account in enumerate(accounts):
            if config.cancel_operation:
                await callback_query.message.edit_text("⏹️ Operation cancelled by user.")
                return
            
            try:
                client = Client("leave_session", session_string=account["session_string"])
                await client.connect()
                
                try:
                    # Try to leave
                    if link.startswith("https://t.me/addlist/"):
                        # Chat folder - handle differently
                        results.append(f"⚠️ {account['phone']}: Chat folders not supported yet")
                        fail_count += 1
                        await client.disconnect()
                        continue
                    
                    # Get chat entity
                    if link.startswith("@"):
                        chat = await client.get_chat(link)
                    elif link.startswith("t.me/"):
                        chat = await client.get_chat(link)
                    elif link.startswith("https://t.me/"):
                        chat = await client.get_chat(link)
                    elif link.startswith("-100"):
                        chat = await client.get_chat(int(link))
                    else:
                        results.append(f"❌ {account['phone']}: Unsupported link format")
                        fail_count += 1
                        await client.disconnect()
                        continue
                    
                    # Leave the chat
                    await client.leave_chat(chat.id)
                    
                    results.append(f"✅ {account['phone']}: Left successfully")
                    success_count += 1
                    
                    # Small delay after leaving
                    await asyncio.sleep(2)
                
                except Exception as e:
                    error_msg = str(e)
                    if "Not found" in error_msg or "CHANNEL_INVALID" in error_msg:
                        results.append(f"❌ {account['phone']}: Chat not found")
                    elif "USER_NOT_PARTICIPANT" in error_msg:
                        results.append(f"ℹ️ {account['phone']}: Not a member")
                        success_count += 1  # Count as success (already not member)
                    elif "CHAT_ADMIN_REQUIRED" in error_msg:
                        results.append(f"🛡️ {account['phone']}: Admin required to leave")
                    else:
                        results.append(f"❌ {account['phone']}: {error_msg[:50]}")
                    fail_count += 1
                
                await client.disconnect()
                await asyncio.sleep(2)  # Delay between accounts
            
            except Exception as e:
                results.append(f"❌ {account['phone']}: Connection error - {str(e)[:50]}")
                fail_count += 1
            
            # Update progress every 10 accounts
            if (i + 1) % 10 == 0:
                progress = f"👋 **Progress:** {i + 1}/{len(accounts)}\n"
                progress += f"✅ Success: {success_count}\n"
                progress += f"❌ Failed: {fail_count}"
                await callback_query.message.edit_text(progress)
        
        # Final result
        result_text = f"👋 **Leave Complete!**\n\n"
        result_text += f"🔗 **Link:** `{link}`\n"
        result_text += f"✅ **Success:** {success_count}\n"
        result_text += f"❌ **Failed:** {fail_count}\n"
        result_text += f"📊 **Total:** {len(accounts)}\n\n"
        
        if results:
            result_text += "**Detailed Results:**\n"
            for res in results[:20]:  # Show first 20 results
                result_text += f"{res}\n"
            
            if len(results) > 20:
                result_text += f"\n... and {len(results) - 20} more"
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Leave Another", callback_data="leave_again")],
            [InlineKeyboardButton("⬅️ Back", callback_data="back_to_admin")]
        ])
        
        await callback_query.message.edit_text(result_text, reply_markup=keyboard)
        
        # Log completion
        if config.LEAVE_LOG_CHANNEL:
            log_msg = f"👋 **Leave Completed**\n\n"
            log_msg += f"✅ **Success:** {success_count}\n"
            log_msg += f"❌ **Failed:** {fail_count}\n"
            log_msg += f"🔗 **Link:** `{link}`\n"
            await log_to_channel(config.LEAVE_LOG_CHANNEL, log_msg)
        
        # Cleanup
        if user_id in self.leave_tasks:
            del self.leave_tasks[user_id]

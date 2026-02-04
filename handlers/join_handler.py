from pyrogram import filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram import Client
import asyncio
from database import db
from config import config
from utils.logger import log_to_channel, log_action
import re

class JoinHandler:
    def __init__(self, bot):
        self.bot = bot
        self.join_tasks = {}
    
    async def handle_join_command(self, message: Message):
        if not config.is_admin(message.from_user.id):
            await message.reply("❌ Admin only command.")
            return
        
        await message.reply(
            "👥 **Join Groups/Channels**\n\n"
            "Send the group/channel link, username, or ID:\n\n"
            "Examples:\n"
            "• `@groupname`\n"
            "• `t.me/groupname`\n"
            "• `-1001234567890` (group ID)\n"
            "• `https://t.me/joinchat/xxxxxx` (invite link)\n\n"
            "For chat folders, send the folder link.\n\n"
            "Type /cancel to cancel."
        )
        
        self.join_tasks[message.from_user.id] = {"step": "waiting_link"}
        
        await log_action(message.from_user.id, "Started join process", "Admin")
    
    @staticmethod
    def is_valid_link(link: str) -> bool:
        """Check if link is a valid Telegram link"""
        patterns = [
            r'^@[a-zA-Z0-9_]{5,32}$',
            r'^t\.me/[a-zA-Z0-9_]{5,32}$',
            r'^https://t\.me/[a-zA-Z0-9_]{5,32}$',
            r'^https://t\.me/joinchat/[a-zA-Z0-9_-]+$',
            r'^-100\d+$',
            r'^https://t\.me/addlist/[a-zA-Z0-9]+$',  # Chat folder link
        ]
        
        for pattern in patterns:
            if re.match(pattern, link):
                return True
        
        return False
    
    async def handle_callback(self, callback_query: CallbackQuery):
        data = callback_query.data
        
        if data.startswith("start_join:"):
            target_user_id = int(data.split(":")[1])
            
            if target_user_id not in self.join_tasks:
                await callback_query.answer("❌ Task expired", show_alert=True)
                return
            
            task_data = self.join_tasks[target_user_id]
            await self.execute_join(callback_query, task_data)
        
        elif data == "cancel_join":
            user_id = callback_query.from_user.id
            if user_id in self.join_tasks:
                del self.join_tasks[user_id]
            
            await callback_query.message.edit_text("❌ Join operation cancelled.")
        
        await callback_query.answer()
    
    async def process_message(self, message: Message):
        # Skip commands
        if message.text and message.text.startswith("/"):
            return
        
        user_id = message.from_user.id
        
        if user_id not in self.join_tasks:
            return
        
        task_data = self.join_tasks[user_id]
        
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
                del self.join_tasks[user_id]
                return
            
            task_data["accounts"] = accounts
            
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Start Joining", callback_data=f"start_join:{user_id}")],
                [InlineKeyboardButton("❌ Cancel", callback_data="cancel_join")]
            ])
            
            await message.reply(
                f"👥 **Join Confirmation**\n\n"
                f"🔗 **Link:** `{link}`\n"
                f"📱 **Accounts:** {len(accounts)} active accounts\n\n"
                f"⚠️ **Are you sure you want to proceed?**",
                reply_markup=keyboard
            )
            
            self.join_tasks[user_id] = task_data
    
    async def execute_join(self, callback_query: CallbackQuery, task_data: dict):
        user_id = callback_query.from_user.id
        link = task_data["link"]
        accounts = task_data["accounts"]
        
        await callback_query.message.edit_text("🚀 Starting to join...")
        
        success_count = 0
        fail_count = 0
        results = []
        
        # Log start
        if config.JOIN_LOG_CHANNEL:
            log_msg = f"👥 **Join Started**\n\n"
            log_msg += f"👤 **By:** {callback_query.from_user.mention}\n"
            log_msg += f"🔗 **Link:** `{link}`\n"
            log_msg += f"📱 **Accounts:** {len(accounts)}\n"
            await log_to_channel(config.JOIN_LOG_CHANNEL, log_msg)
        
        from pyrogram import Client
        
        for i, account in enumerate(accounts):
            if config.cancel_operation:
                await callback_query.message.edit_text("⏹️ Operation cancelled by user.")
                return
            
            try:
                client = Client("join_session", session_string=account["session_string"])
                await client.connect()
                
                try:
                    # Try to join
                    if link.startswith("https://t.me/joinchat/"):
                        # Invite link
                        await client.join_chat(link)
                    elif link.startswith("https://t.me/addlist/"):
                        # Chat folder - handle differently
                        # For now, skip chat folders
                        results.append(f"⚠️ {account['phone']}: Chat folders not supported yet")
                        fail_count += 1
                        await client.disconnect()
                        continue
                    elif link.startswith("@"):
                        # Username
                        await client.join_chat(link)
                    elif link.startswith("t.me/"):
                        # Short link
                        await client.join_chat(link)
                    elif link.startswith("-100"):
                        # Group ID - can't join by ID directly
                        results.append(f"❌ {account['phone']}: Cannot join by group ID")
                        fail_count += 1
                        await client.disconnect()
                        continue
                    else:
                        results.append(f"❌ {account['phone']}: Unsupported link format")
                        fail_count += 1
                        await client.disconnect()
                        continue
                    
                    results.append(f"✅ {account['phone']}: Joined successfully")
                    success_count += 1
                    
                    # Small delay after successful join
                    await asyncio.sleep(3)
                
                except Exception as e:
                    error_msg = str(e)
                    if "FLOOD_WAIT" in error_msg:
                        results.append(f"⏳ {account['phone']}: Flood wait")
                    elif "USER_ALREADY_PARTICIPANT" in error_msg:
                        results.append(f"ℹ️ {account['phone']}: Already a member")
                        success_count += 1  # Count as success
                    elif "INVITE_REQUEST_SENT" in error_msg:
                        results.append(f"📨 {account['phone']}: Join request sent")
                        success_count += 1  # Count as success
                    elif "CHANNEL_PRIVATE" in error_msg or "CHANNEL_PUBLIC_GROUP_NA" in error_msg:
                        results.append(f"🔒 {account['phone']}: Private channel/group")
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
                progress = f"👥 **Progress:** {i + 1}/{len(accounts)}\n"
                progress += f"✅ Success: {success_count}\n"
                progress += f"❌ Failed: {fail_count}"
                await callback_query.message.edit_text(progress)
        
        # Final result
        result_text = f"👥 **Join Complete!**\n\n"
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
            [InlineKeyboardButton("🔄 Join Another", callback_data="join_again")],
            [InlineKeyboardButton("⬅️ Back", callback_data="back_to_admin")]
        ])
        
        await callback_query.message.edit_text(result_text, reply_markup=keyboard)
        
        # Log completion
        if config.JOIN_LOG_CHANNEL:
            log_msg = f"👥 **Join Completed**\n\n"
            log_msg += f"✅ **Success:** {success_count}\n"
            log_msg += f"❌ **Failed:** {fail_count}\n"
            log_msg += f"🔗 **Link:** `{link}`\n"
            await log_to_channel(config.JOIN_LOG_CHANNEL, log_msg)
        
        # Cleanup
        if user_id in self.join_tasks:
            del self.join_tasks[user_id]
    
    async def handle_join_again(self, callback_query: CallbackQuery):
        await self.handle_join_command(callback_query.message)

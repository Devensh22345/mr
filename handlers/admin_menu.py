from pyrogram import filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from database import db
from config import config
from utils.logger import log_to_main, log_to_channel, log_action
from utils.helpers import create_paginated_keyboard, parse_account_numbers
import asyncio
from bson import ObjectId

class AdminMenuHandler:
    def __init__(self, bot):
        self.bot = bot
        self.admin_data = {}
    
    async def handle_admin_command(self, message: Message):
        """Handle /admin command"""
        if not config.is_admin(message.from_user.id):
            await message.reply("❌ You are not authorized to use this command.")
            return
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("👥 All Accounts", callback_data="admin_all_accounts")],
            [InlineKeyboardButton("🗑 Remove Accounts", callback_data="admin_remove")],
            [InlineKeyboardButton("🔄 Refresh Accounts", callback_data="admin_refresh")],
            [InlineKeyboardButton("📢 Set String Channel", callback_data="admin_set_string")],
            [InlineKeyboardButton("❌ Remove String Channel", callback_data="admin_remove_string")],
            [InlineKeyboardButton("👑 Admin Management", callback_data="admin_management")],
            [InlineKeyboardButton("⚙️ Account Settings", callback_data="account_settings")],
            [InlineKeyboardButton("📊 Log Channels", callback_data="log_channels")]
        ])
        
        await message.reply(
            "👑 **Admin Panel**\n\n"
            "Select an option:",
            reply_markup=keyboard
        )
        
        await log_action(message.from_user.id, "Opened admin panel", "Admin")
    
    async def handle_callback(self, callback_query: CallbackQuery):
        data = callback_query.data
        user_id = callback_query.from_user.id
        
        if not config.is_admin(user_id):
            await callback_query.answer("❌ Unauthorized", show_alert=True)
            return
        
        if data == "admin_all_accounts":
            await self.show_all_accounts(callback_query)
        
        elif data == "admin_remove":
            await self.show_admin_remove_options(callback_query)
        
        elif data == "admin_refresh":
            await self.admin_refresh_accounts(callback_query)
        
        elif data == "admin_set_string":
            await callback_query.message.edit_text(
                "📢 **Set String Channel**\n\n"
                "Send the channel ID (with -100 prefix) for storing session strings:\n"
                "Example: `-1001234567890`\n\n"
                "Type /cancel to cancel."
            )
            self.admin_data[user_id] = {"action": "set_string_channel"}
        
        elif data == "admin_remove_string":
            config.STRING_CHANNEL = None
            await callback_query.message.edit_text(
                "✅ String channel removed.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("⬅️ Back", callback_data="back_to_admin")]
                ])
            )
            await log_action(user_id, "Removed string channel", "Admin")
        
        elif data == "admin_management":
            await self.show_admin_management(callback_query)
        
        elif data == "account_settings":
            # This will now be handled by AdminAccountSettings handler
            # We'll route it through the callback system
            from bot import admin_account_settings
            await admin_account_settings.handle_account_settings(callback_query)
            return
        
        elif data == "log_channels":
            await self.show_log_channels_menu(callback_query)
        
        elif data.startswith("admin_accounts_page:"):
            page = int(data.split(":")[1])
            await self.show_all_accounts(callback_query, page)
        
        elif data.startswith("admin_remove_option:"):
            option = data.split(":")[1]
            await self.handle_admin_remove_option(callback_query, option)
        
        elif data == "admin_remove_inactive":
            await self.admin_remove_inactive(callback_query)
        
        elif data == "confirm_remove_all_admin":
            await self.confirm_remove_all_admin(callback_query)
        
        elif data.startswith("remove_user_accs:"):
            user_id_to_remove = int(data.split(":")[1])
            await self.remove_user_accounts(callback_query, user_id_to_remove)
        
        elif data == "back_to_admin":
            await self.handle_admin_command(callback_query.message)
        
        await callback_query.answer()
    
    async def show_all_accounts(self, callback_query: CallbackQuery, page: int = 0):
        total_accounts = await db.accounts.count_documents({})
        active_accounts = await db.accounts.count_documents({"is_active": True})
        frozen_accounts = await db.accounts.count_documents({"is_frozen": True})
        
        accounts = await db.accounts.find({}).sort("created_at", -1).skip(page * 10).limit(10).to_list(length=10)
        
        text = f"📊 **All Accounts**\n\n"
        text += f"📈 **Statistics:**\n"
        text += f"• Total: {total_accounts}\n"
        text += f"• Active: {active_accounts}\n"
        text += f"• Inactive: {total_accounts - active_accounts}\n"
        text += f"• Frozen: {frozen_accounts}\n\n"
        text += f"📋 **Accounts (Page {page + 1}):**\n\n"
        
        for i, acc in enumerate(accounts, page * 10 + 1):
            status = "🟢" if acc.get("is_active", True) else "🔴"
            frozen = "❄️" if acc.get("is_frozen", False) else ""
            
            user_info = await db.users.find_one({"user_id": acc["user_id"]})
            username = f"@{user_info['username']}" if user_info and user_info.get("username") else f"ID: {acc['user_id']}"
            
            text += f"{i}. {status}{frozen} {acc.get('name', 'Unknown')}\n"
            text += f"   📱 {acc.get('phone')}\n"
            text += f"   👤 Owner: {username}\n\n"
        
        total_pages = (total_accounts + 9) // 10
        
        keyboard = []
        if total_pages > 1:
            nav_buttons = []
            if page > 0:
                nav_buttons.append(InlineKeyboardButton("⬅️", callback_data=f"admin_accounts_page:{page-1}"))
            nav_buttons.append(InlineKeyboardButton(f"{page+1}/{total_pages}", callback_data="none"))
            if page < total_pages - 1:
                nav_buttons.append(InlineKeyboardButton("➡️", callback_data=f"admin_accounts_page:{page+1}"))
            keyboard.append(nav_buttons)
        
        keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data="back_to_admin")])
        
        await callback_query.message.edit_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    async def show_admin_remove_options(self, callback_query: CallbackQuery):
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("Remove User's All Accounts", callback_data="admin_remove_option:user")],
            [InlineKeyboardButton("Remove All Accounts", callback_data="admin_remove_option:all")],
            [InlineKeyboardButton("Remove by Numbers", callback_data="admin_remove_option:numbers")],
            [InlineKeyboardButton("⬅️ Back", callback_data="back_to_admin")]
        ])
        
        await callback_query.message.edit_text(
            "🗑 **Admin Remove Options**\n\n"
            "Select removal type:",
            reply_markup=keyboard
        )
    
    async def handle_admin_remove_option(self, callback_query: CallbackQuery, option: str):
        user_id = callback_query.from_user.id
        
        if option == "user":
            # Get all users with accounts
            pipeline = [
                {"$group": {"_id": "$user_id", "count": {"$sum": 1}}},
                {"$sort": {"count": -1}}
            ]
            user_accounts = await db.accounts.aggregate(pipeline).to_list(length=50)
            
            if not user_accounts:
                await callback_query.message.edit_text("No users found with accounts.")
                return
            
            keyboard = []
            for user_acc in user_accounts[:10]:  # Show first 10 users
                user_info = await db.users.find_one({"user_id": user_acc["_id"]})
                username = f"@{user_info['username']}" if user_info and user_info.get("username") else f"ID: {user_acc['_id']}"
                keyboard.append([
                    InlineKeyboardButton(
                        f"{username} ({user_acc['count']} accounts)",
                        callback_data=f"remove_user_accs:{user_acc['_id']}"
                    )
                ])
            
            keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data="admin_remove")])
            
            await callback_query.message.edit_text(
                "Select user to remove all accounts:",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        
        elif option == "all":
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Confirm Remove ALL", callback_data="confirm_remove_all_admin")],
                [InlineKeyboardButton("❌ Cancel", callback_data="admin_remove")]
            ])
            await callback_query.message.edit_text(
                "⚠️ **WARNING: REMOVE ALL ACCOUNTS**\n\n"
                "This will remove **ALL** accounts from **ALL** users!\n"
                "This action is irreversible!\n\n"
                "Are you absolutely sure?",
                reply_markup=keyboard
            )
        
        elif option == "numbers":
            await callback_query.message.edit_text(
                "Send account numbers to remove (from the all accounts list):\n\n"
                "Format:\n"
                "• Comma separated: `1,3,5`\n"
                "• Range: `1-5`\n"
                "• Mixed: `1,3-5,7`\n\n"
                "Type /cancel to cancel."
            )
            self.admin_data[user_id] = {"action": "remove_by_numbers"}
    
    async def admin_refresh_accounts(self, callback_query: CallbackQuery):
        await callback_query.message.edit_text("🔄 Checking all accounts... This may take a while.")
        
        accounts = await db.accounts.find({}).to_list(length=None)
        active_count = 0
        inactive_count = 0
        frozen_count = 0
        
        from pyrogram import Client
        
        for account in accounts:
            try:
                client = Client("temp_session", session_string=account["session_string"])
                await client.connect()
                me = await client.get_me()
                await client.disconnect()
                
                await db.accounts.update_one(
                    {"_id": account["_id"]},
                    {
                        "$set": {
                            "is_active": True,
                            "is_frozen": False,
                            "name": f"{me.first_name or ''} {me.last_name or ''}".strip(),
                            "username": me.username,
                            "last_checked": asyncio.get_event_loop().time()
                        }
                    }
                )
                active_count += 1
            except Exception as e:
                error_msg = str(e)
                is_frozen = any(x in error_msg for x in ["FLOOD", "SESSION_REVOKED", "AUTH_KEY_DUPLICATED"])
                
                await db.accounts.update_one(
                    {"_id": account["_id"]},
                    {
                        "$set": {
                            "is_active": False,
                            "is_frozen": is_frozen,
                            "last_checked": asyncio.get_event_loop().time()
                        }
                    }
                )
                inactive_count += 1
                if is_frozen:
                    frozen_count += 1
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🗑 Remove All Inactive", callback_data="admin_remove_inactive")],
            [InlineKeyboardButton("⬅️ Back", callback_data="back_to_admin")]
        ])
        
        await callback_query.message.edit_text(
            f"✅ **Global Account Check Completed!**\n\n"
            f"📊 **Statistics:**\n"
            f"🟢 Active: {active_count}\n"
            f"🔴 Inactive: {inactive_count}\n"
            f"❄️ Frozen: {frozen_count}\n"
            f"📈 Total: {active_count + inactive_count}\n\n"
            f"**Note:** Inactive accounts may be deleted, banned, or have revoked sessions.",
            reply_markup=keyboard
        )
        
        await log_action(callback_query.from_user.id, "Refreshed all accounts", 
                        f"Active: {active_count}, Inactive: {inactive_count}, Frozen: {frozen_count}")
    
    async def admin_remove_inactive(self, callback_query: CallbackQuery):
        user_id = callback_query.from_user.id
        
        # Find and count inactive accounts before deletion
        inactive_count = await db.accounts.count_documents({"is_active": False})
        
        if inactive_count == 0:
            await callback_query.message.edit_text(
                "✅ No inactive accounts to remove.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("⬅️ Back", callback_data="back_to_admin")]
                ])
            )
            return
        
        # Delete inactive accounts
        result = await db.accounts.delete_many({"is_active": False})
        
        # Update user account lists
        all_users = await db.users.find({}).to_list(length=None)
        for user in all_users:
            user_accounts = await db.accounts.find({"user_id": user["user_id"]}).to_list(length=None)
            account_phones = [acc["phone"] for acc in user_accounts]
            await db.users.update_one(
                {"user_id": user["user_id"]},
                {"$set": {"accounts": account_phones}}
            )
        
        await callback_query.message.edit_text(
            f"✅ Removed {result.deleted_count} inactive accounts.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ Back", callback_data="back_to_admin")]
            ])
        )
        
        await log_action(user_id, "Removed all inactive accounts", f"Count: {result.deleted_count}")
    
    async def confirm_remove_all_admin(self, callback_query: CallbackQuery):
        user_id = callback_query.from_user.id
        
        # Delete all accounts
        result = await db.accounts.delete_many({})
        
        # Clear all users' account lists
        await db.users.update_many({}, {"$set": {"accounts": []}})
        
        await callback_query.message.edit_text(
            f"✅ Removed all {result.deleted_count} accounts from the database.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ Back to Admin", callback_data="back_to_admin")]
            ])
        )
        
        await log_action(user_id, "Removed ALL accounts", f"Count: {result.deleted_count}")
    
    async def remove_user_accounts(self, callback_query: CallbackQuery, target_user_id: int):
        user_id = callback_query.from_user.id
        
        # Get user info
        user_info = await db.users.find_one({"user_id": target_user_id})
        username = f"@{user_info['username']}" if user_info and user_info.get("username") else f"ID: {target_user_id}"
        
        # Delete user's accounts
        result = await db.accounts.delete_many({"user_id": target_user_id})
        
        # Clear user's account list
        await db.users.update_one(
            {"user_id": target_user_id},
            {"$set": {"accounts": []}}
        )
        
        await callback_query.message.edit_text(
            f"✅ Removed {result.deleted_count} accounts from user {username}.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ Back", callback_data="admin_remove")]
            ])
        )
        
        await log_action(user_id, f"Removed user accounts", f"User: {target_user_id}, Count: {result.deleted_count}")
    
    async def show_admin_management(self, callback_query: CallbackQuery):
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ Add Admin", callback_data="add_admin")],
            [InlineKeyboardButton("➖ Remove Admin", callback_data="remove_admin")],
            [InlineKeyboardButton("📋 List Admins", callback_data="list_admins")],
            [InlineKeyboardButton("⬅️ Back", callback_data="back_to_admin")]
        ])
        
        await callback_query.message.edit_text(
            "👑 **Admin Management**\n\n"
            "Select an option:",
            reply_markup=keyboard
        )
    
    async def show_log_channels_menu(self, callback_query: CallbackQuery):
        text = "📊 **Log Channels**\n\n"
        text += f"• String Channel: {config.STRING_CHANNEL or 'Not set'}\n"
        text += f"• Report Log: {config.REPORT_LOG_CHANNEL or 'Not set'}\n"
        text += f"• Send Log: {config.SEND_LOG_CHANNEL or 'Not set'}\n"
        text += f"• OTP Log: {config.OTP_LOG_CHANNEL or 'Not set'}\n"
        text += f"• Join Log: {config.JOIN_LOG_CHANNEL or 'Not set'}\n"
        text += f"• Leave Log: {config.LEAVE_LOG_CHANNEL or 'Not set'}\n"
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("Set Report Log", callback_data="set_report_log"),
             InlineKeyboardButton("Remove", callback_data="remove_report_log")],
            [InlineKeyboardButton("Set Send Log", callback_data="set_send_log"),
             InlineKeyboardButton("Remove", callback_data="remove_send_log")],
            [InlineKeyboardButton("Set OTP Log", callback_data="set_otp_log"),
             InlineKeyboardButton("Remove", callback_data="remove_otp_log")],
            [InlineKeyboardButton("Set Join Log", callback_data="set_join_log"),
             InlineKeyboardButton("Remove", callback_data="remove_join_log")],
            [InlineKeyboardButton("Set Leave Log", callback_data="set_leave_log"),
             InlineKeyboardButton("Remove", callback_data="remove_leave_log")],
            [InlineKeyboardButton("⬅️ Back", callback_data="back_to_admin")]
        ])
        
        await callback_query.message.edit_text(text, reply_markup=keyboard)
    
    async def process_message(self, message: Message):
        user_id = message.from_user.id
        
        if user_id not in self.admin_data:
            return
        
        data = self.admin_data[user_id]
        action = data.get("action")
        
        if action == "set_string_channel":
            try:
                channel_id = int(message.text)
                config.STRING_CHANNEL = channel_id
                
                await message.reply(f"✅ String channel set to: {channel_id}")
                del self.admin_data[user_id]
                
                await log_action(user_id, "Set string channel", f"Channel: {channel_id}")
            except:
                await message.reply("❌ Invalid channel ID. Please try again.")
        
        elif action == "remove_by_numbers":
            try:
                numbers = parse_account_numbers(message.text)
                
                # Get all accounts sorted by creation date
                all_accounts = await db.accounts.find({}).sort("created_at", 1).to_list(length=None)
                
                removed_count = 0
                for num in numbers:
                    if 1 <= num <= len(all_accounts):
                        account = all_accounts[num-1]
                        await db.accounts.delete_one({"_id": account["_id"]})
                        
                        # Remove from user's account list
                        await db.users.update_one(
                            {"user_id": account["user_id"]},
                            {"$pull": {"accounts": account["phone"]}}
                        )
                        
                        removed_count += 1
                
                await message.reply(f"✅ Removed {removed_count} accounts.")
                del self.admin_data[user_id]
                
                await log_action(user_id, "Removed accounts by numbers", f"Count: {removed_count}")
            except Exception as e:
                await message.reply(f"❌ Error: {str(e)}")

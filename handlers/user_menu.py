from pyrogram import filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from database import db
from utils.logger import log_to_main, log_action
from utils.helpers import create_paginated_keyboard, parse_account_numbers
import asyncio
from bson import ObjectId

class UserMenuHandler:
    def __init__(self, bot):
        self.bot = bot
        self.user_data = {}
    
    async def handle_set_command(self, message: Message):
        """Handle /set command for user settings"""
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📱 My Accounts", callback_data="user_accounts")],
            [InlineKeyboardButton("🗑 Remove Account", callback_data="user_remove")],
            [InlineKeyboardButton("🔄 Refresh Accounts", callback_data="user_refresh")],
            [InlineKeyboardButton("📝 Set Log Channel", callback_data="user_set_log")],
            [InlineKeyboardButton("❌ Remove Log Channel", callback_data="user_remove_log")]
        ])
        
        await message.reply(
            "⚙️ **User Settings Menu**\n\n"
            "Select an option:",
            reply_markup=keyboard
        )
        
        await log_action(message.from_user.id, "Opened user settings")
    
    async def handle_callback(self, callback_query: CallbackQuery):
        data = callback_query.data
        user_id = callback_query.from_user.id
        
        if data == "user_accounts":
            await self.show_user_accounts(callback_query)
        
        elif data == "user_remove":
            await self.show_remove_options(callback_query)
        
        elif data == "user_refresh":
            await self.refresh_accounts(callback_query)
        
        elif data == "user_set_log":
            await callback_query.message.edit_text(
                "📝 **Set Log Channel**\n\n"
                "Please forward a message from the channel you want to set as log channel, "
                "or send the channel ID (with -100 prefix for supergroups).\n\n"
                "Example: `-1001234567890`\n\n"
                "Type /cancel to cancel."
            )
            self.user_data[user_id] = {"action": "set_log"}
        
        elif data == "user_remove_log":
            await self.remove_log_channel(callback_query)
        
        elif data.startswith("account_page:"):
            page = int(data.split(":")[1])
            await self.show_accounts_page(callback_query, page)
        
        elif data.startswith("remove_option:"):
            option = data.split(":")[1]
            await self.handle_remove_option(callback_query, option)
        
        elif data.startswith("remove_acc:"):
            account_id = data.split(":")[1]
            await self.remove_single_account(callback_query, account_id)
        
        elif data == "confirm_remove_all":
            await self.confirm_remove_all(callback_query)
        
        elif data == "remove_inactive":
            await self.remove_inactive_accounts(callback_query)
        
        await callback_query.answer()
    
    async def show_user_accounts(self, callback_query: CallbackQuery, page: int = 0):
        user_id = callback_query.from_user.id
        
        accounts = await db.accounts.find(
            {"user_id": user_id}
        ).sort("created_at", -1).to_list(length=100)
        
        if not accounts:
            await callback_query.message.edit_text(
                "📭 **No Accounts Found**\n\n"
                "You haven't added any accounts yet.\n"
                "Use /login to add your first account.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔐 Login Account", callback_data="start_login")]
                ])
            )
            return
        
        text = "📱 **Your Accounts**\n\n"
        for i, acc in enumerate(accounts[page*10:(page+1)*10], page*10 + 1):
            status = "🟢" if acc.get("is_active", True) else "🔴"
            frozen = "❄️" if acc.get("is_frozen", False) else ""
            text += f"{i}. {status}{frozen} {acc.get('name', 'Unknown')}\n"
            text += f"   📱 {acc.get('phone')}\n"
            if acc.get("username"):
                text += f"   👤 @{acc['username']}\n"
            text += f"   📅 Added: {acc['created_at'].strftime('%Y-%m-%d')}\n\n"
        
        total = len(accounts)
        pages = (total + 9) // 10
        
        keyboard = []
        if pages > 1:
            nav_buttons = []
            if page > 0:
                nav_buttons.append(InlineKeyboardButton("⬅️", callback_data=f"account_page:{page-1}"))
            nav_buttons.append(InlineKeyboardButton(f"{page+1}/{pages}", callback_data="none"))
            if page < pages - 1:
                nav_buttons.append(InlineKeyboardButton("➡️", callback_data=f"account_page:{page+1}"))
            keyboard.append(nav_buttons)
        
        keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data="back_to_menu")])
        
        await callback_query.message.edit_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    async def show_remove_options(self, callback_query: CallbackQuery):
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🗑 Remove Single Account", callback_data="remove_option:single")],
            [InlineKeyboardButton("🗑 Remove Multiple Accounts", callback_data="remove_option:multiple")],
            [InlineKeyboardButton("🗑 Remove All Accounts", callback_data="remove_option:all")],
            [InlineKeyboardButton("⬅️ Back", callback_data="back_to_menu")]
        ])
        
        await callback_query.message.edit_text(
            "🗑 **Remove Accounts**\n\n"
            "Select removal option:",
            reply_markup=keyboard
        )
    
    async def handle_remove_option(self, callback_query: CallbackQuery, option: str):
        user_id = callback_query.from_user.id
        
        if option == "single":
            accounts = await db.accounts.find(
                {"user_id": user_id}
            ).sort("created_at", 1).to_list(length=50)
            
            if not accounts:
                await callback_query.message.edit_text(
                    "📭 No accounts to remove.",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("⬅️ Back", callback_data="user_remove")]
                    ])
                )
                return
            
            keyboard = []
            for i, acc in enumerate(accounts[:10], 1):
                keyboard.append([
                    InlineKeyboardButton(
                        f"{i}. {acc['phone']}",
                        callback_data=f"remove_acc:{acc['_id']}"
                    )
                ])
            
            keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data="user_remove")])
            
            await callback_query.message.edit_text(
                "Select account to remove:",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        
        elif option == "multiple":
            accounts = await db.accounts.find(
                {"user_id": user_id}
            ).sort("created_at", 1).to_list(length=None)
            
            if not accounts:
                await callback_query.message.edit_text(
                    "📭 No accounts to remove.",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("⬅️ Back", callback_data="user_remove")]
                    ])
                )
                return
            
            text = "Your accounts:\n\n"
            for i, acc in enumerate(accounts, 1):
                text += f"{i}. {acc['phone']}\n"
            
            text += "\nSend account numbers to remove:\n"
            text += "• Comma separated: `1,3,5`\n"
            text += "• Range: `1-5`\n"
            text += "• Mixed: `1,3-5,7`\n\n"
            text += "Type /cancel to cancel."
            
            await callback_query.message.edit_text(text)
            self.user_data[user_id] = {"action": "remove_multiple", "accounts": accounts}
        
        elif option == "all":
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Confirm Remove All", callback_data="confirm_remove_all")],
                [InlineKeyboardButton("❌ Cancel", callback_data="user_remove")]
            ])
            await callback_query.message.edit_text(
                "⚠️ **Warning: Remove All Accounts**\n\n"
                "This will permanently remove **ALL** your accounts!\n"
                "This action cannot be undone.\n\n"
                "Are you sure you want to continue?",
                reply_markup=keyboard
            )
    
    async def remove_single_account(self, callback_query: CallbackQuery, account_id: str):
        from bson import ObjectId
        
        try:
            account = await db.accounts.find_one({"_id": ObjectId(account_id)})
            if not account:
                await callback_query.message.edit_text("❌ Account not found.")
                return
            
            if account["user_id"] != callback_query.from_user.id:
                await callback_query.message.edit_text("❌ You don't own this account.")
                return
            
            await db.accounts.delete_one({"_id": ObjectId(account_id)})
            
            # Update user's account list
            await db.users.update_one(
                {"user_id": callback_query.from_user.id},
                {"$pull": {"accounts": account["phone"]}}
            )
            
            await callback_query.message.edit_text(
                f"✅ Account removed successfully!\n"
                f"📱 Phone: {account['phone']}",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("⬅️ Back", callback_data="user_remove")]
                ])
            )
            
            await log_action(callback_query.from_user.id, "Removed account", f"Phone: {account['phone']}")
        
        except Exception as e:
            await callback_query.message.edit_text(f"❌ Error: {str(e)}")
    
    async def confirm_remove_all(self, callback_query: CallbackQuery):
        user_id = callback_query.from_user.id
        
        # Get all user accounts
        accounts = await db.accounts.find({"user_id": user_id}).to_list(length=None)
        
        if not accounts:
            await callback_query.message.edit_text(
                "📭 No accounts to remove.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("⬅️ Back", callback_data="user_remove")]
                ])
            )
            return
        
        # Delete all accounts
        result = await db.accounts.delete_many({"user_id": user_id})
        
        # Clear user's account list
        await db.users.update_one(
            {"user_id": user_id},
            {"$set": {"accounts": []}}
        )
        
        await callback_query.message.edit_text(
            f"✅ Removed all {result.deleted_count} accounts successfully!",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ Back to Menu", callback_data="back_to_menu")]
            ])
        )
        
        await log_action(user_id, "Removed all accounts", f"Count: {result.deleted_count}")
    
    async def refresh_accounts(self, callback_query: CallbackQuery):
        user_id = callback_query.from_user.id
        
        await callback_query.message.edit_text("🔄 Checking accounts status...")
        
        accounts = await db.accounts.find({"user_id": user_id}).to_list(length=None)
        active_count = 0
        inactive_count = 0
        
        from pyrogram import Client
        
        for account in accounts:
            try:
                # Try to create client from session string
                client = Client("temp_session", session_string=account["session_string"])
                await client.connect()
                me = await client.get_me()
                await client.disconnect()
                
                # Update account info
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
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🗑 Remove Inactive Accounts", callback_data="remove_inactive")],
            [InlineKeyboardButton("⬅️ Back", callback_data="back_to_menu")]
        ])
        
        await callback_query.message.edit_text(
            f"✅ **Account Check Completed!**\n\n"
            f"🟢 **Active:** {active_count}\n"
            f"🔴 **Inactive:** {inactive_count}\n"
            f"❄️ **Frozen:** {len([a for a in accounts if a.get('is_frozen', False)])}\n\n"
            f"Inactive accounts may be:\n"
            f"• Deleted/banned\n"
            f"• Session revoked\n"
            f"• Flood locked",
            reply_markup=keyboard
        )
        
        await log_action(user_id, "Refreshed accounts", f"Active: {active_count}, Inactive: {inactive_count}")
    
    async def remove_inactive_accounts(self, callback_query: CallbackQuery):
        user_id = callback_query.from_user.id
        
        # Find inactive accounts
        result = await db.accounts.delete_many({
            "user_id": user_id,
            "is_active": False
        })
        
        # Update user's account list
        inactive_accounts = await db.accounts.find({
            "user_id": user_id,
            "is_active": False
        }).to_list(length=None)
        
        for acc in inactive_accounts:
            await db.users.update_one(
                {"user_id": user_id},
                {"$pull": {"accounts": acc["phone"]}}
            )
        
        await callback_query.message.edit_text(
            f"✅ Removed {result.deleted_count} inactive accounts.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ Back", callback_data="back_to_menu")]
            ])
        )
        
        await log_action(user_id, "Removed inactive accounts", f"Count: {result.deleted_count}")
    
    async def remove_log_channel(self, callback_query: CallbackQuery):
        user_id = callback_query.from_user.id
        
        await db.users.update_one(
            {"user_id": user_id},
            {"$set": {"log_channel": None}}
        )
        
        await callback_query.message.edit_text(
            "✅ Log channel removed successfully!",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ Back", callback_data="back_to_menu")]
            ])
        )
        
        await log_action(user_id, "Removed log channel")
    
    async def show_accounts_page(self, callback_query: CallbackQuery, page: int):
        await self.show_user_accounts(callback_query, page)
    
    async def process_message(self, message: Message):
        user_id = message.from_user.id
        
        if user_id not in self.user_data:
            return
        
        data = self.user_data[user_id]
        action = data.get("action")
        
        if action == "set_log":
            try:
                if message.forward_from_chat:
                    channel_id = message.forward_from_chat.id
                else:
                    channel_id = int(message.text)
                
                await db.users.update_one(
                    {"user_id": user_id},
                    {"$set": {"log_channel": channel_id}},
                    upsert=True
                )
                
                await message.reply(f"✅ Log channel set to: {channel_id}")
                del self.user_data[user_id]
                
                await log_action(user_id, "Set log channel", f"Channel: {channel_id}")
            except:
                await message.reply("❌ Invalid channel. Please forward a message from a channel or send a valid channel ID.")
        
        elif action == "remove_multiple":
            try:
                numbers = parse_account_numbers(message.text)
                accounts = data.get("accounts", [])
                
                removed = 0
                for num in numbers:
                    if 0 < num <= len(accounts):
                        await db.accounts.delete_one({"_id": accounts[num-1]["_id"]})
                        removed += 1
                
                # Update user's account list
                remaining_accounts = await db.accounts.find({"user_id": user_id}).to_list(length=None)
                account_phones = [acc["phone"] for acc in remaining_accounts]
                await db.users.update_one(
                    {"user_id": user_id},
                    {"$set": {"accounts": account_phones}}
                )
                
                await message.reply(f"✅ Removed {removed} accounts.")
                del self.user_data[user_id]
                
                await log_action(user_id, "Removed multiple accounts", f"Count: {removed}")
            except Exception as e:
                await message.reply(f"❌ Error: {str(e)}")

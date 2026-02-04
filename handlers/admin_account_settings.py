from pyrogram import filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram import Client, enums
import asyncio
import os
from database import db
from config import config
from utils.logger import log_to_channel, log_action
from utils.helpers import create_account_selection_keyboard
from bson import ObjectId

class AdminAccountSettings:
    def __init__(self, bot):
        self.bot = bot
        self.settings_data = {}
    
    async def handle_account_settings(self, callback_query: CallbackQuery):
        """Entry point for account settings from admin menu"""
        if not config.is_admin(callback_query.from_user.id):
            await callback_query.answer("❌ Unauthorized", show_alert=True)
            return
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("Single Account", callback_data="acc_setting_single")],
            [InlineKeyboardButton("All Accounts", callback_data="acc_setting_all")],
            [InlineKeyboardButton("Multiple Accounts", callback_data="acc_setting_multiple")],
            [InlineKeyboardButton("⬅️ Back", callback_data="back_to_admin")]
        ])
        
        await callback_query.message.edit_text(
            "⚙️ **Account Settings**\n\n"
            "Select accounts to modify:",
            reply_markup=keyboard
        )
        
        await callback_query.answer()
    
    async def handle_callback(self, callback_query: CallbackQuery):
        data = callback_query.data
        user_id = callback_query.from_user.id
        
        if not config.is_admin(user_id):
            await callback_query.answer("❌ Unauthorized", show_alert=True)
            return
        
        if data.startswith("acc_setting_"):
            setting_type = data.split("_")[2]  # single, all, multiple
            await self.select_accounts_for_settings(callback_query, setting_type)
        
        elif data.startswith("select_acc_setting:"):
            idx = int(data.split(":")[1])
            await self.toggle_account_selection(callback_query, idx)
        
        elif data.startswith("acc_setting_page:"):
            page = int(data.split(":")[1])
            await self.show_accounts_page(callback_query, page)
        
        elif data == "acc_setting_proceed" or data == "confirm_setting_selection":
            await self.show_settings_options(callback_query)
        
        elif data.startswith("setting_option:"):
            option = data.split(":")[1]
            await self.handle_setting_option(callback_query, option)
        
        elif data == "apply_all_accounts":
            await self.apply_to_all_accounts(callback_query)
        
        elif data == "back_to_settings_menu":
            await self.show_settings_options(callback_query)
        
        await callback_query.answer()
    
    async def select_accounts_for_settings(self, callback_query: CallbackQuery, setting_type: str):
        user_id = callback_query.from_user.id
        
        accounts = await db.accounts.find({"is_active": True}).to_list(length=100)
        
        if not accounts:
            await callback_query.message.edit_text(
                "❌ No active accounts found.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("⬅️ Back", callback_data="back_to_admin")]
                ])
            )
            return
        
        if user_id not in self.settings_data:
            self.settings_data[user_id] = {}
        
        self.settings_data[user_id].update({
            "type": setting_type,
            "accounts": accounts,
            "selected": [],
            "page": 0
        })
        
        if setting_type == "all":
            # Select all accounts automatically
            self.settings_data[user_id]["selected"] = list(range(len(accounts)))
            await self.show_settings_options(callback_query)
        else:
            await self.show_accounts_page(callback_query, 0)
    
    async def show_accounts_page(self, callback_query: CallbackQuery, page: int = 0):
        user_id = callback_query.from_user.id
        
        if user_id not in self.settings_data:
            await callback_query.message.edit_text("❌ Session expired. Start again.")
            return
        
        op_data = self.settings_data[user_id]
        accounts = op_data.get("accounts", [])
        selected = op_data.get("selected", [])
        setting_type = op_data.get("type", "")
        
        op_data["page"] = page
        self.settings_data[user_id] = op_data
        
        if setting_type == "single" and len(selected) > 1:
            # For single account, keep only the last selection
            selected = selected[-1:]
            op_data["selected"] = selected
            self.settings_data[user_id] = op_data
        
        keyboard = self.create_settings_selection_keyboard(accounts, selected, page)
        
        text = "📱 **Select Accounts**\n\n"
        
        if setting_type == "single":
            text += "⚠️ Select ONE account only\n"
        elif setting_type == "multiple":
            text += "Select multiple accounts\n"
        
        text += f"Selected: {len(selected)} accounts\n\n"
        text += "Click on accounts to select/deselect.\n"
        text += "Click 'Proceed' when done."
        
        await callback_query.message.edit_text(text, reply_markup=keyboard)
    
    def create_settings_selection_keyboard(self, accounts: list, selected: list, page: int):
        """Create keyboard for account selection with checkboxes"""
        start_idx = page * 10
        end_idx = start_idx + 10
        page_accounts = accounts[start_idx:end_idx]
        
        keyboard = []
        for i, acc in enumerate(page_accounts, 1):
            idx = start_idx + i - 1
            is_selected = idx in selected
            emoji = "✅" if is_selected else "⬜"
            keyboard.append([
                InlineKeyboardButton(
                    f"{emoji} {acc.get('name', acc.get('phone', 'Unknown'))}",
                    callback_data=f"select_acc_setting:{idx}"
                )
            ])
        
        # Navigation buttons
        nav_buttons = []
        if page > 0:
            nav_buttons.append(InlineKeyboardButton("⬅️", callback_data=f"acc_setting_page:{page-1}"))
        
        if len(selected) > 0:
            nav_buttons.append(InlineKeyboardButton("🚀 Proceed", callback_data="acc_setting_proceed"))
        
        if end_idx < len(accounts):
            nav_buttons.append(InlineKeyboardButton("➡️", callback_data=f"acc_setting_page:{page+1}"))
        
        if nav_buttons:
            keyboard.append(nav_buttons)
        
        # Confirm selection button
        if len(selected) > 0:
            keyboard.append([
                InlineKeyboardButton(
                    f"✅ Confirm ({len(selected)} selected)", 
                    callback_data="confirm_setting_selection"
                )
            ])
        
        keyboard.append([
            InlineKeyboardButton("⬅️ Back", callback_data="back_to_admin")
        ])
        
        return InlineKeyboardMarkup(keyboard)
    
    async def toggle_account_selection(self, callback_query: CallbackQuery, idx: int):
        user_id = callback_query.from_user.id
        
        if user_id not in self.settings_data:
            await callback_query.answer("❌ Session expired", show_alert=True)
            return
        
        op_data = self.settings_data[user_id]
        selected = op_data.get("selected", [])
        setting_type = op_data.get("type", "")
        
        if setting_type == "single":
            # For single account, replace selection
            selected = [idx]
        else:
            # For multiple accounts, toggle selection
            if idx in selected:
                selected.remove(idx)
            else:
                selected.append(idx)
        
        op_data["selected"] = selected
        self.settings_data[user_id] = op_data
        
        # Stay on same page
        page = op_data.get("page", 0)
        await self.show_accounts_page(callback_query, page)
    
    async def show_settings_options(self, callback_query: CallbackQuery):
        user_id = callback_query.from_user.id
        
        if user_id not in self.settings_data:
            await callback_query.message.edit_text("❌ Session expired. Start again.")
            return
        
        op_data = self.settings_data[user_id]
        selected_count = len(op_data.get("selected", []))
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📛 Change Name", callback_data="setting_option:name")],
            [InlineKeyboardButton("👤 Change Username", callback_data="setting_option:username")],
            [InlineKeyboardButton("📝 Change Bio", callback_data="setting_option:bio")],
            [InlineKeyboardButton("🖼️ Change Profile Photo", callback_data="setting_option:photo")],
            [InlineKeyboardButton("🔐 Set/Change 2FA Password", callback_data="setting_option:2fa")],
            [InlineKeyboardButton("🔒 Privacy Settings", callback_data="setting_option:privacy")],
            [InlineKeyboardButton("⚙️ Account Info", callback_data="setting_option:info")],
            [InlineKeyboardButton("⬅️ Back", callback_data="back_to_admin")]
        ])
        
        text = f"⚙️ **Account Settings Options**\n\n"
        text += f"📱 **Selected Accounts:** {selected_count}\n\n"
        text += "Select setting to modify:"
        
        await callback_query.message.edit_text(text, reply_markup=keyboard)
    
    async def handle_setting_option(self, callback_query: CallbackQuery, option: str):
        user_id = callback_query.from_user.id
        
        if user_id not in self.settings_data:
            await callback_query.message.edit_text("❌ Session expired. Start again.")
            return
        
        op_data = self.settings_data[user_id]
        op_data["current_option"] = option
        
        if option == "name":
            await self.handle_name_change(callback_query)
        elif option == "username":
            await self.handle_username_change(callback_query)
        elif option == "bio":
            await self.handle_bio_change(callback_query)
        elif option == "photo":
            await self.handle_photo_change(callback_query)
        elif option == "2fa":
            await self.handle_2fa_change(callback_query)
        elif option == "privacy":
            await self.handle_privacy_settings(callback_query)
        elif option == "info":
            await self.show_account_info(callback_query)
        
        self.settings_data[user_id] = op_data
    
    async def handle_name_change(self, callback_query: CallbackQuery):
        user_id = callback_query.from_user.id
        op_data = self.settings_data[user_id]
        
        selected_count = len(op_data.get("selected", []))
        
        if selected_count == 1:
            text = "📛 **Change Account Name**\n\n"
            text += "Send the new name for the account:\n\n"
            text += "Format: FirstName LastName\n"
            text += "Example: `John Doe`\n\n"
            text += "Type /cancel to cancel."
        else:
            text = "📛 **Change Multiple Account Names**\n\n"
            text += f"Selected accounts: {selected_count}\n\n"
            text += "Choose naming method:\n"
            text += "1. Send names separated by commas\n"
            text += "   Example: `John, Jane, Bob`\n\n"
            text += "2. Send base name with numbers\n"
            text += "   Example: `User` will become:\n"
            text += "   • User 1\n   • User 2\n   • User 3\n\n"
            text += "Type /cancel to cancel."
        
        await callback_query.message.edit_text(text)
        op_data["step"] = "get_name"
        self.settings_data[user_id] = op_data
    
    async def handle_username_change(self, callback_query: CallbackQuery):
        user_id = callback_query.from_user.id
        op_data = self.settings_data[user_id]
        
        text = "👤 **Change Username**\n\n"
        text += "Send new username (without @):\n\n"
        
        selected_count = len(op_data.get("selected", []))
        if selected_count > 1:
            text += f"Selected accounts: {selected_count}\n\n"
            text += "Usernames will be set as:\n"
            text += "1. If you send one username: username_1, username_2, etc.\n"
            text += "2. If you send multiple: user1, user2, user3\n\n"
        
        text += "Leave empty to remove username.\n"
        text += "Type /cancel to cancel."
        
        await callback_query.message.edit_text(text)
        op_data["step"] = "get_username"
        self.settings_data[user_id] = op_data
    
    async def handle_bio_change(self, callback_query: CallbackQuery):
        user_id = callback_query.from_user.id
        op_data = self.settings_data[user_id]
        
        text = "📝 **Change Bio**\n\n"
        text += "Send new bio text:\n\n"
        text += "Maximum 70 characters.\n"
        text += "Leave empty to remove bio.\n"
        text += "Type /cancel to cancel."
        
        await callback_query.message.edit_text(text)
        op_data["step"] = "get_bio"
        self.settings_data[user_id] = op_data
    
    async def handle_photo_change(self, callback_query: CallbackQuery):
        user_id = callback_query.from_user.id
        op_data = self.settings_data[user_id]
        
        text = "🖼️ **Change Profile Photo**\n\n"
        text += "Send a photo to set as profile picture:\n\n"
        text += "Note: Same photo will be set for all selected accounts.\n"
        text += "Type /cancel to cancel."
        
        await callback_query.message.edit_text(text)
        op_data["step"] = "get_photo"
        self.settings_data[user_id] = op_data
    
    async def handle_2fa_change(self, callback_query: CallbackQuery):
        user_id = callback_query.from_user.id
        op_data = self.settings_data[user_id]
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔐 Set 2FA Password", callback_data="2fa_set")],
            [InlineKeyboardButton("🔓 Remove 2FA Password", callback_data="2fa_remove")],
            [InlineKeyboardButton("⬅️ Back", callback_data="back_to_settings_menu")]
        ])
        
        text = "🔐 **Two-Step Verification**\n\n"
        text += "Select action:\n\n"
        text += "• Set Password: Enable 2FA with password\n"
        text += "• Remove Password: Disable 2FA\n\n"
        text += "Note: You need current password to remove 2FA."
        
        await callback_query.message.edit_text(text, reply_markup=keyboard)
    
    async def handle_privacy_settings(self, callback_query: CallbackQuery):
        user_id = callback_query.from_user.id
        op_data = self.settings_data[user_id]
        
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("📞 Phone", callback_data="privacy:phone"),
                InlineKeyboardButton("👁️ Last Seen", callback_data="privacy:last_seen")
            ],
            [
                InlineKeyboardButton("🖼️ Profile Photo", callback_data="privacy:profile_photo"),
                InlineKeyboardButton("📩 Forwards", callback_data="privacy:forwards")
            ],
            [
                InlineKeyboardButton("📞 Calls", callback_data="privacy:calls"),
                InlineKeyboardButton("👥 Invites", callback_data="privacy:invites")
            ],
            [
                InlineKeyboardButton("🌐 Groups", callback_data="privacy:groups"),
                InlineKeyboardButton("📢 Channels", callback_data="privacy:channels")
            ],
            [InlineKeyboardButton("⬅️ Back", callback_data="back_to_settings_menu")]
        ])
        
        text = "🔒 **Privacy Settings**\n\n"
        text += "Select privacy setting to modify:\n\n"
        text += "• **Everyone** - All users can see\n"
        text += "• **Contacts** - Only your contacts\n"
        text += "• **Nobody** - No one can see\n\n"
        text += "Select a setting to configure:"
        
        await callback_query.message.edit_text(text, reply_markup=keyboard)
    
    async def show_account_info(self, callback_query: CallbackQuery):
        user_id = callback_query.from_user.id
        
        if user_id not in self.settings_data:
            await callback_query.message.edit_text("❌ Session expired. Start again.")
            return
        
        op_data = self.settings_data[user_id]
        selected_indices = op_data.get("selected", [])
        accounts = op_data.get("accounts", [])
        
        selected_accounts = [accounts[i] for i in selected_indices if i < len(accounts)]
        
        text = "📊 **Account Information**\n\n"
        
        for i, account in enumerate(selected_accounts[:5], 1):  # Show first 5
            text += f"**{i}. {account.get('name', 'Unknown')}**\n"
            text += f"📱 Phone: {account.get('phone')}\n"
            text += f"👤 Username: @{account.get('username', 'None')}\n"
            text += f"🆔 User ID: `{account.get('user_id', 'Unknown')}`\n"
            text += f"📅 Created: {account.get('created_at').strftime('%Y-%m-%d')}\n"
            text += f"📶 Status: {'🟢 Active' if account.get('is_active') else '🔴 Inactive'}\n"
            if account.get('is_frozen'):
                text += "❄️ Frozen: Yes\n"
            text += "\n"
        
        if len(selected_accounts) > 5:
            text += f"... and {len(selected_accounts) - 5} more accounts\n\n"
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Refresh Info", callback_data="setting_option:info")],
            [InlineKeyboardButton("⬅️ Back", callback_data="back_to_settings_menu")]
        ])
        
        await callback_query.message.edit_text(text, reply_markup=keyboard)
    
    async def process_message(self, message: Message):
        user_id = message.from_user.id
        
        if user_id not in self.settings_data:
            return
        
        op_data = self.settings_data[user_id]
        step = op_data.get("step")
        option = op_data.get("current_option")
        
        if step == "get_name":
            await self.process_name_change(message, op_data)
        
        elif step == "get_username":
            await self.process_username_change(message, op_data)
        
        elif step == "get_bio":
            await self.process_bio_change(message, op_data)
        
        elif step == "get_photo":
            await self.process_photo_change(message, op_data)
        
        elif step == "get_2fa_password":
            await self.process_2fa_password(message, op_data)
        
        elif step == "get_privacy_value":
            await self.process_privacy_setting(message, op_data)
        
        self.settings_data[user_id] = op_data
    
    async def process_name_change(self, message: Message, op_data: dict):
        user_id = message.from_user.id
        new_name = message.text.strip()
        
        if not new_name:
            await message.reply("❌ Name cannot be empty. Please try again:")
            return
        
        selected_indices = op_data.get("selected", [])
        accounts = op_data.get("accounts", [])
        selected_accounts = [accounts[i] for i in selected_indices if i < len(accounts)]
        
        if len(selected_accounts) == 1:
            # Single account - use provided name directly
            names = [new_name]
        else:
            # Multiple accounts
            if "," in new_name:
                # Comma-separated names
                names = [name.strip() for name in new_name.split(",") if name.strip()]
                if len(names) != len(selected_accounts):
                    await message.reply(
                        f"❌ Number of names ({len(names)}) doesn't match "
                        f"number of accounts ({len(selected_accounts)}). "
                        "Please provide matching names or a single base name."
                    )
                    return
            else:
                # Base name with numbers
                base_name = new_name
                names = [f"{base_name} {i+1}" for i in range(len(selected_accounts))]
        
        # Confirm before changing
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Apply Changes", callback_data="apply_name_change")],
            [InlineKeyboardButton("❌ Cancel", callback_data="back_to_settings_menu")]
        ])
        
        text = f"📛 **Confirm Name Change**\n\n"
        text += f"**New Names:**\n"
        for i, name in enumerate(names[:10], 1):
            text += f"{i}. {name}\n"
        
        if len(names) > 10:
            text += f"... and {len(names) - 10} more\n\n"
        
        text += f"\nApply to {len(selected_accounts)} accounts?"
        
        await message.reply(text, reply_markup=keyboard)
        
        # Store data for confirmation
        op_data["names"] = names
        op_data["step"] = "confirm_name"
        self.settings_data[user_id] = op_data
    
    async def process_username_change(self, message: Message, op_data: dict):
        user_id = message.from_user.id
        username_input = message.text.strip()
        
        selected_indices = op_data.get("selected", [])
        accounts = op_data.get("accounts", [])
        selected_accounts = [accounts[i] for i in selected_indices if i < len(accounts)]
        
        if len(selected_accounts) == 1:
            # Single account
            if username_input:
                # Remove @ if present
                username = username_input.replace("@", "")
                # Validate username
                if not self.is_valid_username(username):
                    await message.reply("❌ Invalid username format. Use letters, numbers, and underscores only.")
                    return
                usernames = [username]
            else:
                usernames = [""]  # Empty to remove username
        else:
            # Multiple accounts
            if username_input:
                if "," in username_input:
                    # Comma-separated usernames
                    usernames = [uname.strip().replace("@", "") for uname in username_input.split(",") if uname.strip()]
                    
                    # Validate all usernames
                    for uname in usernames:
                        if uname and not self.is_valid_username(uname):
                            await message.reply(f"❌ Invalid username: {uname}. Use letters, numbers, and underscores only.")
                            return
                    
                    if len(usernames) != len(selected_accounts):
                        await message.reply(
                            f"❌ Number of usernames ({len(usernames)}) doesn't match "
                            f"number of accounts ({len(selected_accounts)})."
                        )
                        return
                else:
                    # Base username with numbers
                    base_username = username_input.replace("@", "")
                    if not self.is_valid_username(base_username):
                        await message.reply("❌ Invalid username format. Use letters, numbers, and underscores only.")
                        return
                    
                    usernames = []
                    for i in range(len(selected_accounts)):
                        if i == 0:
                            usernames.append(base_username)
                        else:
                            usernames.append(f"{base_username}_{i+1}")
            else:
                # Empty to remove all usernames
                usernames = [""] * len(selected_accounts)
        
        # Confirm before changing
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Apply Changes", callback_data="apply_username_change")],
            [InlineKeyboardButton("❌ Cancel", callback_data="back_to_settings_menu")]
        ])
        
        text = f"👤 **Confirm Username Change**\n\n"
        
        if any(usernames):
            text += f"**New Usernames:**\n"
            for i, uname in enumerate(usernames[:10], 1):
                text += f"{i}. @{uname if uname else 'None'}\n"
        else:
            text += "**Action:** Remove all usernames\n"
        
        if len(usernames) > 10:
            text += f"... and {len(usernames) - 10} more\n\n"
        
        text += f"\nApply to {len(selected_accounts)} accounts?"
        
        await message.reply(text, reply_markup=keyboard)
        
        # Store data for confirmation
        op_data["usernames"] = usernames
        op_data["step"] = "confirm_username"
        self.settings_data[user_id] = op_data
    
    def is_valid_username(self, username: str) -> bool:
        """Check if username is valid"""
        if not username:
            return True  # Empty username is allowed (to remove)
        
        if len(username) < 5 or len(username) > 32:
            return False
        
        # Check if contains only allowed characters
        import re
        pattern = r'^[a-zA-Z0-9_]+$'
        return bool(re.match(pattern, username))
    
    async def process_bio_change(self, message: Message, op_data: dict):
        user_id = message.from_user.id
        bio = message.text.strip()
        
        if len(bio) > 70:
            await message.reply("❌ Bio too long (max 70 characters). Please shorten it:")
            return
        
        selected_indices = op_data.get("selected", [])
        accounts = op_data.get("accounts", [])
        selected_accounts = [accounts[i] for i in selected_indices if i < len(accounts)]
        
        # Confirm before changing
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Apply Changes", callback_data="apply_bio_change")],
            [InlineKeyboardButton("❌ Cancel", callback_data="back_to_settings_menu")]
        ])
        
        text = f"📝 **Confirm Bio Change**\n\n"
        
        if bio:
            text += f"**New Bio:**\n{bio}\n\n"
        else:
            text += "**Action:** Remove bio\n\n"
        
        text += f"Apply to {len(selected_accounts)} accounts?"
        
        await message.reply(text, reply_markup=keyboard)
        
        # Store data for confirmation
        op_data["bio"] = bio
        op_data["step"] = "confirm_bio"
        self.settings_data[user_id] = op_data
    
    async def process_photo_change(self, message: Message, op_data: dict):
        user_id = message.from_user.id
        
        if not message.photo:
            await message.reply("❌ Please send a photo.")
            return
        
        selected_indices = op_data.get("selected", [])
        accounts = op_data.get("accounts", [])
        selected_accounts = [accounts[i] for i in selected_indices if i < len(accounts)]
        
        # Confirm before changing
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Apply Changes", callback_data="apply_photo_change")],
            [InlineKeyboardButton("❌ Cancel", callback_data="back_to_settings_menu")]
        ])
        
        text = f"🖼️ **Confirm Profile Photo Change**\n\n"
        text += f"Set this photo as profile picture for {len(selected_accounts)} accounts?"
        
        await message.reply_photo(
            message.photo.file_id,
            caption=text,
            reply_markup=keyboard
        )
        
        # Store photo for confirmation
        op_data["photo"] = message.photo
        op_data["step"] = "confirm_photo"
        self.settings_data[user_id] = op_data
    
    async def process_2fa_password(self, message: Message, op_data: dict):
        """Process 2FA password input"""
        user_id = message.from_user.id
        password = message.text
        
        op_data["2fa_password"] = password
        op_data["step"] = "confirm_2fa"
        
        selected_indices = op_data.get("selected", [])
        accounts = op_data.get("accounts", [])
        selected_accounts = [accounts[i] for i in selected_indices if i < len(accounts)]
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Set 2FA Password", callback_data="apply_2fa_change")],
            [InlineKeyboardButton("❌ Cancel", callback_data="back_to_settings_menu")]
        ])
        
        text = f"🔐 **Confirm 2FA Password**\n\n"
        text += f"Set password for {len(selected_accounts)} accounts?\n\n"
        text += f"Password: {'*' * len(password)}\n\n"
        text += "Note: This will enable two-step verification."
        
        await message.reply(text, reply_markup=keyboard)
        
        self.settings_data[user_id] = op_data
    
    async def process_privacy_setting(self, message: Message, op_data: dict):
        """Process privacy setting input"""
        user_id = message.from_user.id
        setting = message.text.lower().strip()
        
        privacy_type = op_data.get("privacy_type")
        selected_indices = op_data.get("selected", [])
        accounts = op_data.get("accounts", [])
        
        # Validate setting
        valid_settings = ["everyone", "contacts", "nobody"]
        if setting not in valid_settings:
            await message.reply("❌ Invalid setting. Use: everyone, contacts, or nobody")
            return
        
        # Map setting to pyrogram enum
        setting_map = {
            "everyone": enums.PrivacyRuleType.ALLOW_ALL,
            "contacts": enums.PrivacyRuleType.ALLOW_CONTACTS,
            "nobody": enums.PrivacyRuleType.ALLOW_USERS  # This needs user list
        }
        
        op_data["privacy_setting"] = setting
        op_data["step"] = "confirm_privacy"
        
        privacy_names = {
            "phone": "phone number",
            "last_seen": "last seen",
            "profile_photo": "profile photo",
            "forwards": "forwarded messages",
            "calls": "calls",
            "invites": "group invites",
            "groups": "groups",
            "channels": "channels"
        }
        
        privacy_name = privacy_names.get(privacy_type, privacy_type)
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"✅ Apply {setting.capitalize()}", 
                                 callback_data=f"confirm_privacy:{privacy_type}:{setting}")],
            [InlineKeyboardButton("❌ Cancel", callback_data="back_to_settings_menu")]
        ])
        
        text = f"🔒 **Confirm Privacy Change**\n\n"
        text += f"**Setting:** {privacy_name}\n"
        text += f"**Visibility:** {setting.capitalize()}\n\n"
        text += f"Apply to {len(selected_indices)} accounts?"
        
        await message.reply(text, reply_markup=keyboard)
        
        self.settings_data[user_id] = op_data
    
    async def handle_setting_confirmation(self, callback_query: CallbackQuery):
        data = callback_query.data
        user_id = callback_query.from_user.id
        
        if user_id not in self.settings_data:
            await callback_query.answer("❌ Session expired", show_alert=True)
            return
        
        op_data = self.settings_data[user_id]
        
        if data == "apply_name_change":
            await self.apply_name_change(callback_query, op_data)
        
        elif data == "apply_username_change":
            await self.apply_username_change(callback_query, op_data)
        
        elif data == "apply_bio_change":
            await self.apply_bio_change(callback_query, op_data)
        
        elif data == "apply_photo_change":
            await self.apply_photo_change(callback_query, op_data)
        
        elif data.startswith("privacy:"):
            privacy_type = data.split(":")[1]
            await self.configure_privacy(callback_query, op_data, privacy_type)
        
        elif data.startswith("2fa_"):
            action = data.split("_")[1]
            await self.handle_2fa_action(callback_query, op_data, action)
        
        elif data.startswith("set_privacy:"):
            parts = data.split(":")
            privacy_type = parts[1]
            setting = parts[2]
            await self.apply_privacy_setting(callback_query, op_data, privacy_type, setting)
        
        elif data.startswith("confirm_privacy:"):
            parts = data.split(":")
            privacy_type = parts[1]
            setting = parts[2]
            await self.execute_privacy_change(callback_query, op_data, privacy_type, setting)
        
        elif data == "apply_2fa_change":
            await self.apply_2fa_change(callback_query, op_data)
        
        await callback_query.answer()
    
    async def apply_name_change(self, callback_query: CallbackQuery, op_data: dict):
        user_id = callback_query.from_user.id
        
        selected_indices = op_data.get("selected", [])
        accounts = op_data.get("accounts", [])
        names = op_data.get("names", [])
        
        await callback_query.message.edit_text("📛 Changing names...")
        
        success_count = 0
        fail_count = 0
        results = []
        
        from pyrogram import Client
        
        for i, idx in enumerate(selected_indices):
            if idx >= len(accounts):
                continue
            
            account = accounts[idx]
            new_name = names[i] if i < len(names) else f"User {i+1}"
            
            try:
                client = Client("name_session", session_string=account["session_string"])
                await client.connect()
                
                # Split name into first and last name
                name_parts = new_name.split(" ", 1)
                first_name = name_parts[0]
                last_name = name_parts[1] if len(name_parts) > 1 else ""
                
                await client.update_profile(
                    first_name=first_name,
                    last_name=last_name
                )
                
                # Update database
                await db.accounts.update_one(
                    {"_id": account["_id"]},
                    {"$set": {"name": new_name}}
                )
                
                results.append(f"✅ {account['phone']}: Changed to '{new_name}'")
                success_count += 1
                
                await client.disconnect()
                await asyncio.sleep(2)  # Delay between accounts
            
            except Exception as e:
                error_msg = str(e)
                if "FLOOD_WAIT" in error_msg:
                    results.append(f"⏳ {account['phone']}: Flood wait")
                else:
                    results.append(f"❌ {account['phone']}: {error_msg[:50]}")
                fail_count += 1
        
        # Show results
        result_text = f"📛 **Name Change Complete!**\n\n"
        result_text += f"✅ Success: {success_count}\n"
        result_text += f"❌ Failed: {fail_count}\n\n"
        
        if results:
            result_text += "**Results:**\n"
            for res in results[:10]:
                result_text += f"{res}\n"
            
            if len(results) > 10:
                result_text += f"\n... and {len(results) - 10} more"
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Change More", callback_data="acc_setting_single")],
            [InlineKeyboardButton("⬅️ Back to Admin", callback_data="back_to_admin")]
        ])
        
        await callback_query.message.edit_text(result_text, reply_markup=keyboard)
        
        # Cleanup
        if user_id in self.settings_data:
            del self.settings_data[user_id]
        
        # Log action
        await log_action(user_id, "Changed account names", f"Success: {success_count}, Failed: {fail_count}")
    
    async def apply_username_change(self, callback_query: CallbackQuery, op_data: dict):
        user_id = callback_query.from_user.id
        
        selected_indices = op_data.get("selected", [])
        accounts = op_data.get("accounts", [])
        usernames = op_data.get("usernames", [])
        
        await callback_query.message.edit_text("👤 Changing usernames...")
        
        success_count = 0
        fail_count = 0
        results = []
        
        from pyrogram import Client
        
        for i, idx in enumerate(selected_indices):
            if idx >= len(accounts):
                continue
            
            account = accounts[idx]
            new_username = usernames[i] if i < len(usernames) else ""
            
            try:
                client = Client("username_session", session_string=account["session_string"])
                await client.connect()
                
                if new_username:
                    await client.set_username(new_username)
                    result_msg = f"Changed to @{new_username}"
                else:
                    await client.set_username("")  # Remove username
                    result_msg = "Username removed"
                
                # Update database
                await db.accounts.update_one(
                    {"_id": account["_id"]},
                    {"$set": {"username": new_username}}
                )
                
                results.append(f"✅ {account['phone']}: {result_msg}")
                success_count += 1
                
                await client.disconnect()
                await asyncio.sleep(3)  # Longer delay for username changes
            
            except Exception as e:
                error_msg = str(e)
                if "USERNAME_OCCUPIED" in error_msg:
                    results.append(f"❌ {account['phone']}: Username @{new_username} is taken")
                elif "USERNAME_INVALID" in error_msg:
                    results.append(f"❌ {account['phone']}: Invalid username")
                elif "FLOOD_WAIT" in error_msg:
                    results.append(f"⏳ {account['phone']}: Flood wait")
                else:
                    results.append(f"❌ {account['phone']}: {error_msg[:50]}")
                fail_count += 1
        
        # Show results
        result_text = f"👤 **Username Change Complete!**\n\n"
        result_text += f"✅ Success: {success_count}\n"
        result_text += f"❌ Failed: {fail_count}\n\n"
        
        if results:
            result_text += "**Results:**\n"
            for res in results[:10]:
                result_text += f"{res}\n"
            
            if len(results) > 10:
                result_text += f"\n... and {len(results) - 10} more"
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Change More", callback_data="acc_setting_single")],
            [InlineKeyboardButton("⬅️ Back to Admin", callback_data="back_to_admin")]
        ])
        
        await callback_query.message.edit_text(result_text, reply_markup=keyboard)
        
        # Cleanup
        if user_id in self.settings_data:
            del self.settings_data[user_id]
        
        # Log action
        await log_action(user_id, "Changed account usernames", f"Success: {success_count}, Failed: {fail_count}")
    
    async def apply_bio_change(self, callback_query: CallbackQuery, op_data: dict):
        user_id = callback_query.from_user.id
        
        selected_indices = op_data.get("selected", [])
        accounts = op_data.get("accounts", [])
        bio = op_data.get("bio", "")
        
        await callback_query.message.edit_text("📝 Changing bios...")
        
        success_count = 0
        fail_count = 0
        results = []
        
        from pyrogram import Client
        
        for idx in selected_indices:
            if idx >= len(accounts):
                continue
            
            account = accounts[idx]
            
            try:
                client = Client("bio_session", session_string=account["session_string"])
                await client.connect()
                
                await client.update_profile(bio=bio)
                
                results.append(f"✅ {account['phone']}: Bio updated")
                success_count += 1
                
                await client.disconnect()
                await asyncio.sleep(2)
            
            except Exception as e:
                error_msg = str(e)
                if "FLOOD_WAIT" in error_msg:
                    results.append(f"⏳ {account['phone']}: Flood wait")
                else:
                    results.append(f"❌ {account['phone']}: {error_msg[:50]}")
                fail_count += 1
        
        # Show results
        result_text = f"📝 **Bio Change Complete!**\n\n"
        result_text += f"✅ Success: {success_count}\n"
        result_text += f"❌ Failed: {fail_count}\n\n"
        
        if bio:
            result_text += f"**New Bio:** {bio}\n\n"
        
        if results:
            result_text += "**Results:**\n"
            for res in results[:10]:
                result_text += f"{res}\n"
            
            if len(results) > 10:
                result_text += f"\n... and {len(results) - 10} more"
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Change More", callback_data="acc_setting_single")],
            [InlineKeyboardButton("⬅️ Back to Admin", callback_data="back_to_admin")]
        ])
        
        await callback_query.message.edit_text(result_text, reply_markup=keyboard)
        
        # Cleanup
        if user_id in self.settings_data:
            del self.settings_data[user_id]
        
        # Log action
        await log_action(user_id, "Changed account bios", f"Success: {success_count}, Failed: {fail_count}")
    
    async def apply_photo_change(self, callback_query: CallbackQuery, op_data: dict):
        user_id = callback_query.from_user.id
        
        selected_indices = op_data.get("selected", [])
        accounts = op_data.get("accounts", [])
        photo = op_data.get("photo")
        
        if not photo:
            await callback_query.message.edit_text("❌ No photo found. Please try again.")
            return
        
        await callback_query.message.edit_text("🖼️ Changing profile photos...")
        
        success_count = 0
        fail_count = 0
        results = []
        
        from pyrogram import Client
        
        for idx in selected_indices:
            if idx >= len(accounts):
                continue
            
            account = accounts[idx]
            
            try:
                client = Client("photo_session", session_string=account["session_string"])
                await client.connect()
                
                # Download photo if needed
                photo_path = f"temp_photo_{user_id}.jpg"
                await client.download_media(photo.file_id, photo_path)
                
                # Set as profile photo
                await client.set_profile_photo(photo=photo_path)
                
                # Clean up temp file
                try:
                    os.remove(photo_path)
                except:
                    pass
                
                results.append(f"✅ {account['phone']}: Photo updated")
                success_count += 1
                
                await client.disconnect()
                await asyncio.sleep(3)  # Longer delay for photo changes
            
            except Exception as e:
                error_msg = str(e)
                if "FLOOD_WAIT" in error_msg:
                    results.append(f"⏳ {account['phone']}: Flood wait")
                else:
                    results.append(f"❌ {account['phone']}: {error_msg[:50]}")
                fail_count += 1
        
        # Show results
        result_text = f"🖼️ **Profile Photo Change Complete!**\n\n"
        result_text += f"✅ Success: {success_count}\n"
        result_text += f"❌ Failed: {fail_count}\n\n"
        
        if results:
            result_text += "**Results:**\n"
            for res in results[:10]:
                result_text += f"{res}\n"
            
            if len(results) > 10:
                result_text += f"\n... and {len(results) - 10} more"
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Change More", callback_data="acc_setting_single")],
            [InlineKeyboardButton("⬅️ Back to Admin", callback_data="back_to_admin")]
        ])
        
        await callback_query.message.edit_text(result_text, reply_markup=keyboard)
        
        # Cleanup
        if user_id in self.settings_data:
            del self.settings_data[user_id]
        
        # Log action
        await log_action(user_id, "Changed profile photos", f"Success: {success_count}, Failed: {fail_count}")
    
    async def configure_privacy(self, callback_query: CallbackQuery, op_data: dict, privacy_type: str):
        user_id = callback_query.from_user.id
        
        privacy_names = {
            "phone": "📞 Phone Number",
            "last_seen": "👁️ Last Seen & Online",
            "profile_photo": "🖼️ Profile Photo",
            "forwards": "📩 Forwarded Messages",
            "calls": "📞 Calls",
            "invites": "👥 Group Invites",
            "groups": "🌐 Groups",
            "channels": "📢 Channels"
        }
        
        privacy_name = privacy_names.get(privacy_type, privacy_type)
        
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("👥 Everyone", callback_data=f"set_privacy:{privacy_type}:everyone"),
                InlineKeyboardButton("📱 Contacts", callback_data=f"set_privacy:{privacy_type}:contacts")
            ],
            [
                InlineKeyboardButton("🚫 Nobody", callback_data=f"set_privacy:{privacy_type}:nobody"),
                InlineKeyboardButton("⬅️ Back", callback_data="setting_option:privacy")
            ]
        ])
        
        text = f"🔒 **{privacy_name} Privacy**\n\n"
        text += "Select who can see this:\n\n"
        text += "• **Everyone** - All Telegram users\n"
        text += "• **Contacts** - Only your contacts\n"
        text += "• **Nobody** - No one can see\n\n"
        text += "Select setting:"
        
        await callback_query.message.edit_text(text, reply_markup=keyboard)
        
        # Store privacy type
        op_data["privacy_type"] = privacy_type
        self.settings_data[user_id] = op_data
    
    async def apply_privacy_setting(self, callback_query: CallbackQuery, op_data: dict, privacy_type: str, setting: str):
        user_id = callback_query.from_user.id
        
        selected_indices = op_data.get("selected", [])
        accounts = op_data.get("accounts", [])
        
        privacy_names = {
            "phone": "phone number",
            "last_seen": "last seen",
            "profile_photo": "profile photo",
            "forwards": "forwarded messages",
            "calls": "calls",
            "invites": "group invites",
            "groups": "groups",
            "channels": "channels"
        }
        
        setting_names = {
            "everyone": "Everyone",
            "contacts": "Contacts",
            "nobody": "Nobody"
        }
        
        privacy_name = privacy_names.get(privacy_type, privacy_type)
        setting_name = setting_names.get(setting, setting)
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Apply", callback_data=f"confirm_privacy:{privacy_type}:{setting}")],
            [InlineKeyboardButton("❌ Cancel", callback_data="setting_option:privacy")]
        ])
        
        text = f"🔒 **Confirm Privacy Change**\n\n"
        text += f"**Setting:** {privacy_name}\n"
        text += f"**Visibility:** {setting_name}\n\n"
        text += f"Apply to {len(selected_indices)} accounts?"
        
        await callback_query.message.edit_text(text, reply_markup=keyboard)
    
    async def execute_privacy_change(self, callback_query: CallbackQuery, op_data: dict, privacy_type: str, setting: str):
        user_id = callback_query.from_user.id
        
        selected_indices = op_data.get("selected", [])
        accounts = op_data.get("accounts", [])
        
        await callback_query.message.edit_text("🔒 Changing privacy settings...")
        
        success_count = 0
        fail_count = 0
        results = []
        
        from pyrogram import Client
        
        for idx in selected_indices:
            if idx >= len(accounts):
                continue
            
            account = accounts[idx]
            
            try:
                client = Client("privacy_session", session_string=account["session_string"])
                await client.connect()
                
                # Map setting to pyrogram privacy rule
                from pyrogram import enums
                
                if setting == "everyone":
                    rule = enums.PrivacyRuleType.ALLOW_ALL
                elif setting == "contacts":
                    rule = enums.PrivacyRuleType.ALLOW_CONTACTS
                elif setting == "nobody":
                    rule = enums.PrivacyRuleType.ALLOW_USERS  # Empty user list = nobody
                else:
                    rule = enums.PrivacyRuleType.ALLOW_ALL
                
                # Map privacy type to method
                privacy_methods = {
                    "phone": client.set_privacy,
                    "last_seen": client.set_privacy,
                    "profile_photo": client.set_privacy,
                    "forwards": client.set_privacy,
                    "calls": client.set_privacy,
                    "invites": client.set_privacy,
                    "groups": client.set_privacy,
                    "channels": client.set_privacy
                }
                
                # Map to pyrogram privacy key
                privacy_keys = {
                    "phone": enums.PrivacyKey.PHONE_NUMBER,
                    "last_seen": enums.PrivacyKey.STATUS_TIMESTAMP,
                    "profile_photo": enums.PrivacyKey.PROFILE_PHOTO,
                    "forwards": enums.PrivacyKey.FORWARDS,
                    "calls": enums.PrivacyKey.PHONE_CALL,
                    "invites": enums.PrivacyKey.CHAT_INVITE,
                    "groups": enums.PrivacyKey.ADDED_BY_PHONE,
                    "channels": enums.PrivacyKey.ADDED_BY_PHONE
                }
                
                privacy_key = privacy_keys.get(privacy_type)
                if privacy_key:
                    await client.set_privacy(privacy_key, [rule])
                    results.append(f"✅ {account['phone']}: Privacy updated")
                    success_count += 1
                else:
                    results.append(f"❌ {account['phone']}: Unknown privacy type")
                    fail_count += 1
                
                await client.disconnect()
                await asyncio.sleep(2)
            
            except Exception as e:
                error_msg = str(e)
                if "FLOOD_WAIT" in error_msg:
                    results.append(f"⏳ {account['phone']}: Flood wait")
                else:
                    results.append(f"❌ {account['phone']}: {error_msg[:50]}")
                fail_count += 1
        
        # Show results
        result_text = f"🔒 **Privacy Change Complete!**\n\n"
        result_text += f"✅ Success: {success_count}\n"
        result_text += f"❌ Failed: {fail_count}\n\n"
        
        privacy_names = {
            "phone": "Phone Number",
            "last_seen": "Last Seen",
            "profile_photo": "Profile Photo",
            "forwards": "Forwarded Messages",
            "calls": "Calls",
            "invites": "Group Invites",
            "groups": "Groups",
            "channels": "Channels"
        }
        
        result_text += f"**Setting:** {privacy_names.get(privacy_type, privacy_type)}\n"
        result_text += f"**Visibility:** {setting.capitalize()}\n\n"
        
        if results:
            result_text += "**Results:**\n"
            for res in results[:10]:
                result_text += f"{res}\n"
            
            if len(results) > 10:
                result_text += f"\n... and {len(results) - 10} more"
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Change More", callback_data="acc_setting_single")],
            [InlineKeyboardButton("⬅️ Back to Admin", callback_data="back_to_admin")]
        ])
        
        await callback_query.message.edit_text(result_text, reply_markup=keyboard)
        
        # Cleanup
        if user_id in self.settings_data:
            del self.settings_data[user_id]
        
        # Log action
        await log_action(user_id, "Changed privacy settings", 
                        f"Type: {privacy_type}, Setting: {setting}, Success: {success_count}, Failed: {fail_count}")
    
    async def handle_2fa_action(self, callback_query: CallbackQuery, op_data: dict, action: str):
        user_id = callback_query.from_user.id
        
        if action == "set":
            await callback_query.message.edit_text(
                "🔐 **Set 2FA Password**\n\n"
                "Send the new 2FA password:\n\n"
                "Requirements:\n"
                "• Minimum 4 characters\n"
                "• Maximum 128 characters\n"
                "• Can include letters, numbers, and symbols\n\n"
                "Type /cancel to cancel."
            )
            op_data["2fa_action"] = "set"
            op_data["step"] = "get_2fa_password"
        elif action == "remove":
            await callback_query.message.edit_text(
                "🔓 **Remove 2FA Password**\n\n"
                "Send the current 2FA password to remove it:\n\n"
                "Type /cancel to cancel."
            )
            op_data["2fa_action"] = "remove"
            op_data["step"] = "get_2fa_password"
        
        self.settings_data[user_id] = op_data
    
    async def apply_2fa_change(self, callback_query: CallbackQuery, op_data: dict):
        user_id = callback_query.from_user.id
        
        selected_indices = op_data.get("selected", [])
        accounts = op_data.get("accounts", [])
        password = op_data.get("2fa_password", "")
        action = op_data.get("2fa_action", "set")
        
        await callback_query.message.edit_text("🔐 Processing 2FA changes...")
        
        success_count = 0
        fail_count = 0
        results = []
        
        from pyrogram import Client
        
        for idx in selected_indices:
            if idx >= len(accounts):
                continue
            
            account = accounts[idx]
            
            try:
                client = Client("2fa_session", session_string=account["session_string"])
                await client.connect()
                
                if action == "set":
                    # Enable 2FA
                    await client.enable_cloud_password(password)
                    results.append(f"✅ {account['phone']}: 2FA enabled")
                    success_count += 1
                elif action == "remove":
                    # Disable 2FA
                    await client.disable_cloud_password()
                    results.append(f"✅ {account['phone']}: 2FA disabled")
                    success_count += 1
                
                await client.disconnect()
                await asyncio.sleep(3)  # Longer delay for security operations
            
            except Exception as e:
                error_msg = str(e)
                if "FLOOD_WAIT" in error_msg:
                    results.append(f"⏳ {account['phone']}: Flood wait")
                elif "PASSWORD_HASH_INVALID" in error_msg:
                    results.append(f"❌ {account['phone']}: Wrong password")
                elif "EMAIL_UNCONFIRMED" in error_msg:
                    results.append(f"❌ {account['phone']}: Email not confirmed")
                else:
                    results.append(f"❌ {account['phone']}: {error_msg[:50]}")
                fail_count += 1
        
        # Show results
        result_text = f"🔐 **2FA Change Complete!**\n\n"
        
        if action == "set":
            result_text += "**Action:** Enable 2FA\n"
        else:
            result_text += "**Action:** Disable 2FA\n"
        
        result_text += f"✅ Success: {success_count}\n"
        result_text += f"❌ Failed: {fail_count}\n\n"
        
        if results:
            result_text += "**Results:**\n"
            for res in results[:10]:
                result_text += f"{res}\n"
            
            if len(results) > 10:
                result_text += f"\n... and {len(results) - 10} more"
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Change More", callback_data="acc_setting_single")],
            [InlineKeyboardButton("⬅️ Back to Admin", callback_data="back_to_admin")]
        ])
        
        await callback_query.message.edit_text(result_text, reply_markup=keyboard)
        
        # Cleanup
        if user_id in self.settings_data:
            del self.settings_data[user_id]
        
        # Log action
        action_text = "Enabled" if action == "set" else "Disabled"
        await log_action(user_id, f"{action_text} 2FA", f"Success: {success_count}, Failed: {fail_count}")
    
    async def apply_to_all_accounts(self, callback_query: CallbackQuery):
        user_id = callback_query.from_user.id
        
        if user_id not in self.settings_data:
            await callback_query.answer("❌ Session expired", show_alert=True)
            return
        
        op_data = self.settings_data[user_id]
        accounts = op_data.get("accounts", [])
        
        # Select all accounts
        op_data["selected"] = list(range(len(accounts)))
        self.settings_data[user_id] = op_data
        
        await self.show_settings_options(callback_query)

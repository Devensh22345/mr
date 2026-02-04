from pyrogram import filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram import Client
import asyncio
from database import db
from config import config
from utils.logger import log_to_channel, log_action

class OTPHandler:
    def __init__(self, bot):
        self.bot = bot
    
    async def handle_otp_command(self, message: Message):
        if not config.is_admin(message.from_user.id):
            await message.reply("❌ Admin only command.")
            return
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📱 Select Account", callback_data="otp_select")],
            [InlineKeyboardButton("📋 All Accounts OTP", callback_data="otp_all")],
            [InlineKeyboardButton("🔄 Check OTPs", callback_data="otp_check")]
        ])
        
        await message.reply(
            "📱 **OTP Management**\n\n"
            "Select an option:",
            reply_markup=keyboard
        )
        
        await log_action(message.from_user.id, "Opened OTP management", "Admin")
    
    async def handle_callback(self, callback_query: CallbackQuery):
        data = callback_query.data
        
        if not config.is_admin(callback_query.from_user.id):
            await callback_query.answer("❌ Unauthorized", show_alert=True)
            return
        
        if data == "otp_select":
            await self.show_accounts_for_otp(callback_query)
        
        elif data == "otp_all":
            await self.get_all_otps(callback_query)
        
        elif data == "otp_check":
            await self.check_otps(callback_query)
        
        elif data.startswith("otp_account:"):
            account_id = data.split(":")[1]
            await self.get_account_otp(callback_query, account_id)
        
        elif data.startswith("otp_page:"):
            page = int(data.split(":")[1])
            await self.show_accounts_for_otp(callback_query, page)
        
        await callback_query.answer()
    
    async def show_accounts_for_otp(self, callback_query: CallbackQuery, page: int = 0):
        accounts = await db.accounts.find({"is_active": True}).skip(page * 10).limit(10).to_list(length=10)
        total_accounts = await db.accounts.count_documents({"is_active": True})
        
        if not accounts:
            await callback_query.message.edit_text("No active accounts found.")
            return
        
        text = f"Select account to check OTP (Page {page + 1}):\n\n"
        
        keyboard = []
        for i, acc in enumerate(accounts, 1):
            keyboard.append([
                InlineKeyboardButton(
                    f"{i}. {acc['phone']}",
                    callback_data=f"otp_account:{acc['_id']}"
                )
            ])
        
        # Navigation buttons
        nav_buttons = []
        if page > 0:
            nav_buttons.append(InlineKeyboardButton("⬅️", callback_data=f"otp_page:{page-1}"))
        
        nav_buttons.append(InlineKeyboardButton(f"{page+1}/{(total_accounts+9)//10}", callback_data="none"))
        
        if (page + 1) * 10 < total_accounts:
            nav_buttons.append(InlineKeyboardButton("➡️", callback_data=f"otp_page:{page+1}"))
        
        if nav_buttons:
            keyboard.append(nav_buttons)
        
        keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data="back_to_admin")])
        
        await callback_query.message.edit_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    async def get_account_otp(self, callback_query: CallbackQuery, account_id: str):
        from bson import ObjectId
        
        await callback_query.message.edit_text("🔍 Checking for OTP messages...")
        
        try:
            account = await db.accounts.find_one({"_id": ObjectId(account_id)})
            if not account:
                await callback_query.message.edit_text("❌ Account not found.")
                return
            
            client = Client("temp_otp", session_string=account["session_string"])
            await client.connect()
            
            # Get recent messages from Telegram (service notifications)
            otp_found = False
            otp_text = ""
            
            async for message in client.get_chat_history("Telegram", limit=20):
                if message.service:
                    # Check if it's a login code message
                    if any(keyword in str(message) for keyword in ["code", "login", "Code", "Login"]):
                        otp_text = str(message)
                        otp_found = True
                        break
            
            await client.disconnect()
            
            if otp_found:
                # Extract OTP code
                import re
                otp_codes = re.findall(r'\b\d{4,6}\b', otp_text)
                
                response = f"📱 **Account:** {account['phone']}\n"
                response += f"📛 **Name:** {account.get('name', 'Unknown')}\n\n"
                response += "📨 **Recent OTP Message:**\n"
                response += f"```\n{otp_text[:500]}\n```\n\n"
                
                if otp_codes:
                    response += f"🔢 **Possible OTP Codes:**\n"
                    for code in otp_codes:
                        response += f"• `{code}`\n"
                
                # Log to OTP channel
                if config.OTP_LOG_CHANNEL:
                    log_msg = f"OTP found for {account['phone']}: {' '.join(otp_codes) if otp_codes else 'No code extracted'}"
                    await log_to_channel(config.OTP_LOG_CHANNEL, log_msg)
                
            else:
                response = f"📱 **Account:** {account['phone']}\n"
                response += "❌ No recent OTP messages found.\n"
                response += "Check Telegram notifications on the device."
            
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 Check Another", callback_data="otp_select")],
                [InlineKeyboardButton("⬅️ Back", callback_data="back_to_admin")]
            ])
            
            await callback_query.message.edit_text(response, reply_markup=keyboard)
            
        except Exception as e:
            await callback_query.message.edit_text(f"❌ Error: {str(e)}")
    
    async def get_all_otps(self, callback_query: CallbackQuery):
        await callback_query.message.edit_text("📱 Fetching OTPs from all accounts... This may take a while.")
        
        accounts = await db.accounts.find({"is_active": True}).to_list(length=None)
        
        if not accounts:
            await callback_query.message.edit_text("No active accounts found.")
            return
        
        all_otps = []
        from pyrogram import Client
        
        for account in accounts[:20]:  # Limit to 20 accounts for performance
            try:
                client = Client("temp_otp", session_string=account["session_string"])
                await client.connect()
                
                otp_found = False
                async for message in client.get_chat_history("Telegram", limit=5):
                    if message.service and "code" in str(message).lower():
                        # Extract OTP
                        import re
                        text = str(message)
                        codes = re.findall(r'\b\d{4,6}\b', text)
                        if codes:
                            otp_found = True
                            all_otps.append(f"📱 {account['phone']}: `{codes[0]}`")
                            break
                
                await client.disconnect()
                
                if not otp_found:
                    all_otps.append(f"📱 {account['phone']}: No OTP found")
            
            except Exception as e:
                all_otps.append(f"📱 {account['phone']}: Error - {str(e)[:50]}")
        
        if not all_otps:
            response = "❌ No OTPs found in any account."
        else:
            response = "📱 **OTP Status for All Accounts**\n\n"
            for otp_info in all_otps:
                response += f"{otp_info}\n"
            
            if len(accounts) > 20:
                response += f"\n... and {len(accounts) - 20} more accounts not checked."
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Refresh", callback_data="otp_all")],
            [InlineKeyboardButton("⬅️ Back", callback_data="back_to_admin")]
        ])
        
        await callback_query.message.edit_text(response, reply_markup=keyboard)
        
        # Log to OTP channel
        if config.OTP_LOG_CHANNEL:
            summary = f"OTP check completed. Found {len([o for o in all_otps if 'No OTP' not in o])} accounts with OTPs."
            await log_to_channel(config.OTP_LOG_CHANNEL, summary)
    
    async def check_otps(self, callback_query: CallbackQuery):
        await callback_query.message.edit_text("🔄 Checking for new OTPs in all accounts...")
        
        accounts = await db.accounts.find({"is_active": True}).to_list(length=10)  # Limit to 10
        
        new_otps = []
        from pyrogram import Client
        
        for account in accounts:
            try:
                client = Client("temp_otp", session_string=account["session_string"])
                await client.connect()
                
                # Get only very recent messages (last 5)
                async for message in client.get_chat_history("Telegram", limit=5):
                    if message.service and "code" in str(message).lower():
                        # Check if message is recent (within last 10 minutes)
                        import time
                        if time.time() - message.date.timestamp() < 600:  # 10 minutes
                            import re
                            codes = re.findall(r'\b\d{4,6}\b', str(message))
                            if codes:
                                new_otps.append(f"📱 {account['phone']}: `{codes[0]}` (Just now)")
                                break
                
                await client.disconnect()
            
            except:
                pass
        
        if new_otps:
            response = "🆕 **New OTPs Received (Last 10 minutes)**\n\n"
            for otp in new_otps:
                response += f"{otp}\n"
        else:
            response = "📭 No new OTPs received in the last 10 minutes."
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Check Again", callback_data="otp_check")],
            [InlineKeyboardButton("⬅️ Back", callback_data="back_to_admin")]
        ])
        
        await callback_query.message.edit_text(response, reply_markup=keyboard)
        
        # Log to OTP channel
        if config.OTP_LOG_CHANNEL and new_otps:
            log_msg = f"New OTPs found: {len(new_otps)} accounts"
            await log_to_channel(config.OTP_LOG_CHANNEL, log_msg)

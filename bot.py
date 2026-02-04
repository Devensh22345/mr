import asyncio
from pyrogram import Client, filters, idle
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from config import config
from database import db
from utils.logger import log_to_main

# Import handlers
from handlers.login_handler import LoginHandler
from handlers.user_menu import UserMenuHandler
from handlers.admin_menu import AdminMenuHandler
from handlers.admin_account_settings import AdminAccountSettings
from handlers.otp_handler import OTPHandler
from handlers.send_handler import SendHandler
from handlers.join_handler import JoinHandler
from handlers.leave_handler import LeaveHandler
from handlers.report_handler import ReportHandler
from handlers.stop_handler import StopHandler

# Initialize bot
bot = Client(
    "bot_session",
    api_id=config.API_ID,
    api_hash=config.API_HASH,
    bot_token=config.BOT_TOKEN
)

# Initialize handlers
login_handler = LoginHandler(bot)
user_menu = UserMenuHandler(bot)
admin_menu = AdminMenuHandler(bot)
admin_account_settings = AdminAccountSettings(bot)
otp_handler = OTPHandler(bot)
send_handler = SendHandler(bot)
join_handler = JoinHandler(bot)
leave_handler = LeaveHandler(bot)
report_handler = ReportHandler(bot)
stop_handler = StopHandler(bot)

@bot.on_message(filters.command("start"))
async def start_command(client, message: Message):
    user_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name
    
    # Store user info
    await db.users.update_one(
        {"user_id": user_id},
        {
            "$set": {
                "username": username,
                "first_name": first_name,
                "last_seen": asyncio.get_event_loop().time()
            }
        },
        upsert=True
    )
    
    welcome_msg = (
        "🤖 **Telegram Account Manager Bot**\n\n"
        "✨ **Features:**\n"
        "• Manage multiple Telegram accounts\n"
        "• Send messages from all accounts\n"
        "• Join/Leave groups and channels\n"
        "• Report users/groups/posts\n"
        "• OTP management system\n"
        "• Account settings modification\n\n"
        
        "📋 **Available Commands:**\n"
        "`/login` - Add Telegram account\n"
        "`/set` - User settings\n"
        "`/admin` - Admin panel (Admin only)\n"
        "`/otp` - View OTPs (Admin only)\n"
        "`/send` - Send messages (Admin only)\n"
        "`/join` - Join groups/channels (Admin only)\n"
        "`/leave` - Leave groups/channels (Admin only)\n"
        "`/report` - Report users/groups (Admin only)\n"
        "`/stop` - Stop current operation\n"
        "`/cancel` - Cancel current process\n\n"
        
        "🔒 **Privacy:** Your session strings are stored securely.\n"
        "📊 **Support:** Up to 10 accounts per user."
    )
    
    await message.reply(welcome_msg)
    
    await log_to_main(f"User {user_id} ({username}) started the bot")

@bot.on_message(filters.command("login"))
async def login_command(client, message: Message):
    await login_handler.handle_login(message)

@bot.on_message(filters.command("set"))
async def set_command(client, message: Message):
    await user_menu.handle_set_command(message)

@bot.on_message(filters.command("admin"))
async def admin_command(client, message: Message):
    await admin_menu.handle_admin_command(message)

@bot.on_message(filters.command("otp"))
async def otp_command(client, message: Message):
    await otp_handler.handle_otp_command(message)

@bot.on_message(filters.command("send"))
async def send_command(client, message: Message):
    await send_handler.handle_send_command(message)

@bot.on_message(filters.command("join"))
async def join_command(client, message: Message):
    await join_handler.handle_join_command(message)

@bot.on_message(filters.command("leave"))
async def leave_command(client, message: Message):
    await leave_handler.handle_leave_command(message)

@bot.on_message(filters.command("report"))
async def report_command(client, message: Message):
    await report_handler.handle_report_command(message)

@bot.on_message(filters.command("stop"))
async def stop_command(client, message: Message):
    await stop_handler.handle_stop_command(message)

@bot.on_message(filters.command("cancel"))
async def cancel_command(client, message: Message):
    await stop_handler.handle_cancel_command(message)

@bot.on_callback_query()
async def callback_handler(client, callback_query: CallbackQuery):
    data = callback_query.data
    
    # Handle back buttons
    if data == "back_to_menu":
        await user_menu.handle_set_command(callback_query.message)
    
    elif data == "back_to_admin":
        await admin_menu.handle_admin_command(callback_query.message)
    
    elif data == "start_login":
        await login_handler.handle_login(callback_query.message)
    
    # Route callbacks to appropriate handlers
    
    # User menu callbacks
    elif data.startswith("user_"):
        await user_menu.handle_callback(callback_query)
    
    # Admin menu callbacks
    elif data.startswith("admin_"):
        await admin_menu.handle_callback(callback_query)
    
    # Account settings callbacks
    elif data.startswith("acc_setting_"):
        await admin_account_settings.handle_account_settings(callback_query)
    
    elif data.startswith("select_acc_setting:") or \
         data.startswith("acc_setting_page:") or \
         data == "acc_setting_proceed" or \
         data == "confirm_setting_selection" or \
         data.startswith("setting_option:") or \
         data == "apply_all_accounts" or \
         data == "back_to_settings_menu":
        await admin_account_settings.handle_callback(callback_query)
    
    # Setting confirmations
    elif data.startswith("apply_") and "change" in data or \
         data.startswith("confirm_privacy:") or \
         data.startswith("set_privacy:") or \
         data.startswith("privacy:") or \
         data.startswith("2fa_"):
        await admin_account_settings.handle_setting_confirmation(callback_query)
    
    # OTP handler callbacks
    elif data.startswith("otp_"):
        await otp_handler.handle_callback(callback_query)
    
    # Send handler callbacks
    elif data.startswith("send_"):
        await send_handler.handle_callback(callback_query)
        if data.startswith("start_sending:") or data == "cancel_sending":
            await send_handler.handle_send_confirmation(callback_query)
    
    # Report handler callbacks
    elif data.startswith("report_"):
        await report_handler.handle_report_callback(callback_query)
    
    # Join handler callbacks
    elif data.startswith("start_join:") or data == "cancel_join":
        await join_handler.handle_callback(callback_query)
    
    # Leave handler callbacks
    elif data.startswith("start_leave:") or data == "cancel_leave":
        await leave_handler.handle_callback(callback_query)
    
    # Navigation callbacks
    elif data == "join_again":
        await join_handler.handle_join_command(callback_query.message)
    
    elif data == "leave_again":
        await leave_handler.handle_leave_command(callback_query.message)
    
    elif data == "report_again":
        await report_handler.handle_report_command(callback_query.message)
    
    await callback_query.answer()

@bot.on_message(filters.text & ~filters.command())
async def message_handler(client, message: Message):
    # Pass message to appropriate handler based on user state
    await login_handler.process_message(message)
    await user_menu.process_message(message)
    await admin_menu.process_message(message)
    await admin_account_settings.process_message(message)
    await send_handler.process_message(message)
    await join_handler.process_message(message)
    await leave_handler.process_message(message)
    await report_handler.process_message(message)

@bot.on_message(filters.forwarded)
async def forwarded_handler(client, message: Message):
    # Handle forwarded messages for log channel setting
    user_id = message.from_user.id
    
    if user_id in user_menu.user_data:
        data = user_menu.user_data[user_id]
        if data.get("action") == "set_log":
            if message.forward_from_chat:
                channel_id = message.forward_from_chat.id
                
                await db.users.update_one(
                    {"user_id": user_id},
                    {"$set": {"log_channel": channel_id}},
                    upsert=True
                )
                
                await message.reply(f"✅ Log channel set to: `{channel_id}`")
                del user_menu.user_data[user_id]
            else:
                await message.reply("❌ Please forward a message from a channel, not a user.")
        return

async def main():
    # Connect to database
    await db.connect()
    
    # Create sessions directory
    import os
    os.makedirs(config.SESSION_DIR, exist_ok=True)
    
    # Start the bot
    await bot.start()
    
    # Get bot info
    me = await bot.get_me()
    print(f"🤖 Bot started: @{me.username}")
    print(f"🆔 Bot ID: {me.id}")
    
    # Log startup
    await log_to_main(f"Bot @{me.username} started successfully!")
    
    # Run idle
    print("✅ Bot is running. Press Ctrl+C to stop.")
    await idle()
    
    # Stop the bot
    await bot.stop()
    await db.disconnect()
    print("👋 Bot stopped.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Bot stopped by user.")
    except Exception as e:
        print(f"❌ Error: {e}")

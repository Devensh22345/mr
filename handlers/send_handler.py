from pyrogram import filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram import Client
import asyncio
from database import db
from config import config
from utils.logger import log_to_channel, log_action
from utils.helpers import create_account_selection_keyboard

class SendHandler:
    def __init__(self, bot):
        self.bot = bot
        self.sending_tasks = {}
        self.active_operations = {}
    
    async def handle_send_command(self, message: Message):
        if not config.is_admin(message.from_user.id):
            await message.reply("❌ Admin only command.")
            return
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🤖 Send to Bot", callback_data="send_bot")],
            [InlineKeyboardButton("👤 Send to User", callback_data="send_user")],
            [InlineKeyboardButton("👥 Send to Group", callback_data="send_group")],
            [InlineKeyboardButton("📊 Send Stats", callback_data="send_stats")]
        ])
        
        await message.reply(
            "📨 **Send Messages**\n\n"
            "Select destination type:",
            reply_markup=keyboard
        )
        
        await log_action(message.from_user.id, "Opened send menu", "Admin")
    
    async def handle_callback(self, callback_query: CallbackQuery):
        data = callback_query.data
        user_id = callback_query.from_user.id
        
        if not config.is_admin(user_id):
            await callback_query.answer("❌ Unauthorized", show_alert=True)
            return
        
        if data == "send_bot":
            await self.send_to_bot_menu(callback_query)
        
        elif data == "send_user":
            await self.send_to_user_menu(callback_query)
        
        elif data == "send_group":
            await self.send_to_group_menu(callback_query)
        
        elif data == "send_stats":
            await self.show_send_stats(callback_query)
        
        elif data.startswith("send_type:"):
            send_type = data.split(":")[1]
            self.active_operations[user_id] = {"type": send_type}
            await self.select_accounts(callback_query, send_type)
        
        elif data.startswith("select_acc:"):
            idx = int(data.split(":")[1])
            await self.toggle_account_selection(callback_query, idx)
        
        elif data.startswith("acc_page:"):
            page = int(data.split(":")[1])
            await self.show_accounts_page(callback_query, page)
        
        elif data == "acc_proceed" or data == "confirm_selection":
            await self.get_target_info(callback_query)
        
        await callback_query.answer()
    
    async def send_to_bot_menu(self, callback_query: CallbackQuery):
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📤 Send Single Message", callback_data="send_type:bot_single")],
            [InlineKeyboardButton("📤 Send Multiple Messages", callback_data="send_type:bot_multiple")],
            [InlineKeyboardButton("⬅️ Back", callback_data="back_to_admin")]
        ])
        
        await callback_query.message.edit_text(
            "🤖 **Send to Bot**\n\n"
            "Select message type:",
            reply_markup=keyboard
        )
    
    async def send_to_user_menu(self, callback_query: CallbackQuery):
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📤 Send Single Message", callback_data="send_type:user_single")],
            [InlineKeyboardButton("📤 Send Multiple Messages", callback_data="send_type:user_multiple")],
            [InlineKeyboardButton("⬅️ Back", callback_data="back_to_admin")]
        ])
        
        await callback_query.message.edit_text(
            "👤 **Send to User**\n\n"
            "Select message type:",
            reply_markup=keyboard
        )
    
    async def send_to_group_menu(self, callback_query: CallbackQuery):
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📤 Send Single Message", callback_data="send_type:group_single")],
            [InlineKeyboardButton("📤 Send Multiple Messages", callback_data="send_type:group_multiple")],
            [InlineKeyboardButton("⬅️ Back", callback_data="back_to_admin")]
        ])
        
        await callback_query.message.edit_text(
            "👥 **Send to Group**\n\n"
            "Select message type:",
            reply_markup=keyboard
        )
    
    async def select_accounts(self, callback_query: CallbackQuery, send_type: str):
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
        
        if user_id not in self.active_operations:
            self.active_operations[user_id] = {}
        
        self.active_operations[user_id].update({
            "type": send_type,
            "accounts": accounts,
            "selected": []
        })
        
        await self.show_accounts_page(callback_query, 0)
    
    async def show_accounts_page(self, callback_query: CallbackQuery, page: int):
        user_id = callback_query.from_user.id
        
        if user_id not in self.active_operations:
            await callback_query.message.edit_text("❌ Session expired. Start again.")
            return
        
        op_data = self.active_operations[user_id]
        accounts = op_data.get("accounts", [])
        selected = op_data.get("selected", [])
        
        keyboard = create_account_selection_keyboard(accounts, selected, page)
        
        text = "📱 **Select Accounts**\n\n"
        text += f"Selected: {len(selected)} accounts\n\n"
        text += "Click on accounts to select/deselect.\n"
        text += "Click 'Proceed' when done."
        
        await callback_query.message.edit_text(text, reply_markup=keyboard)
    
    async def toggle_account_selection(self, callback_query: CallbackQuery, idx: int):
        user_id = callback_query.from_user.id
        
        if user_id not in self.active_operations:
            await callback_query.answer("❌ Session expired", show_alert=True)
            return
        
        op_data = self.active_operations[user_id]
        selected = op_data.get("selected", [])
        
        if idx in selected:
            selected.remove(idx)
        else:
            selected.append(idx)
        
        op_data["selected"] = selected
        self.active_operations[user_id] = op_data
        
        # Get current page
        page = 0
        if len(op_data.get("accounts", [])) > 0:
            page = idx // 10
        
        await self.show_accounts_page(callback_query, page)
    
    async def get_target_info(self, callback_query: CallbackQuery):
        user_id = callback_query.from_user.id
        
        if user_id not in self.active_operations:
            await callback_query.message.edit_text("❌ Session expired. Start again.")
            return
        
        op_data = self.active_operations[user_id]
        send_type = op_data.get("type", "")
        
        if "bot" in send_type:
            prompt = "🤖 **Send to Bot**\n\nSend the bot username or link:\nExample: `@example_bot` or `t.me/example_bot`"
        elif "user" in send_type:
            prompt = "👤 **Send to User**\n\nSend the user username, ID, or link:\nExample: `@username` or `123456789`"
        elif "group" in send_type:
            prompt = "👥 **Send to Group**\n\nSend the group username, ID, or link:\nExample: `@groupname` or `-1001234567890`"
        else:
            prompt = "Send target username/ID/link:"
        
        prompt += "\n\nType /cancel to cancel."
        
        await callback_query.message.edit_text(prompt)
        
        # Set next step
        op_data["step"] = "get_target"
        self.active_operations[user_id] = op_data
    
    async def process_message(self, message: Message):
        user_id = message.from_user.id
        
        if user_id not in self.active_operations:
            return
        
        op_data = self.active_operations[user_id]
        step = op_data.get("step")
        
        if step == "get_target":
            target = message.text.strip()
            
            # Validate target
            if not target:
                await message.reply("❌ Invalid target. Please try again.")
                return
            
            op_data["target"] = target
            op_data["step"] = "get_message"
            
            if op_data["type"] in ["bot_single", "user_single", "group_single"]:
                prompt = "💬 **Send Message**\n\nSend the message text you want to send:\n\n"
                prompt += "You can send:\n"
                prompt += "• Text message\n"
                prompt += "• Photo with caption\n"
                prompt += "• Document\n"
                prompt += "• Video\n\n"
                prompt += "Type /cancel to cancel."
            else:
                prompt = "💬 **Send Multiple Messages**\n\nSend messages one by one.\n"
                prompt += "Send /done when finished adding messages.\n"
                prompt += "Send /cancel to cancel."
                op_data["messages"] = []
            
            await message.reply(prompt)
            self.active_operations[user_id] = op_data
        
        elif step == "get_message":
            if "messages" in op_data:
                # Multiple messages mode
                if message.text == "/done":
                    if not op_data["messages"]:
                        await message.reply("❌ No messages added. Please add at least one message.")
                        return
                    
                    await self.start_sending(message, op_data)
                    return
                
                op_data["messages"].append(message)
                count = len(op_data["messages"])
                await message.reply(f"✅ Message {count} added. Send another or /done to finish.")
                self.active_operations[user_id] = op_data
            else:
                # Single message mode
                op_data["message"] = message
                await self.start_sending(message, op_data)
    
    async def start_sending(self, message: Message, op_data: dict):
        user_id = message.from_user.id
        
        selected_indices = op_data.get("selected", [])
        accounts = op_data.get("accounts", [])
        
        if not selected_indices:
            await message.reply("❌ No accounts selected.")
            del self.active_operations[user_id]
            return
        
        selected_accounts = [accounts[i] for i in selected_indices if i < len(accounts)]
        
        # Prepare messages
        if "messages" in op_data:
            messages = op_data["messages"]
            is_multiple = True
        else:
            messages = [op_data.get("message")]
            is_multiple = False
        
        target = op_data.get("target", "")
        send_type = op_data.get("type", "")
        
        # Confirm before sending
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Start Sending", callback_data=f"start_sending:{user_id}")],
            [InlineKeyboardButton("❌ Cancel", callback_data="cancel_sending")]
        ])
        
        summary = f"📤 **Send Confirmation**\n\n"
        summary += f"🔧 **Type:** {'Multiple' if is_multiple else 'Single'} Message\n"
        summary += f"🎯 **Target:** `{target}`\n"
        summary += f"📱 **Accounts:** {len(selected_accounts)} selected\n"
        summary += f"💬 **Messages:** {len(messages)}\n\n"
        
        if not is_multiple and messages[0].text:
            summary += f"**Message Preview:**\n{messages[0].text[:200]}"
            if len(messages[0].text) > 200:
                summary += "..."
        
        summary += "\n\n⚠️ **Are you sure you want to proceed?**"
        
        await message.reply(summary, reply_markup=keyboard)
        
        # Store operation data for confirmation
        if user_id not in self.sending_tasks:
            self.sending_tasks[user_id] = {}
        
        self.sending_tasks[user_id] = {
            "accounts": selected_accounts,
            "target": target,
            "messages": messages,
            "type": send_type,
            "user_msg": message
        }
    
    async def handle_send_confirmation(self, callback_query: CallbackQuery):
        data = callback_query.data
        
        if data.startswith("start_sending:"):
            target_user_id = int(data.split(":")[1])
            
            if target_user_id not in self.sending_tasks:
                await callback_query.answer("❌ Task expired", show_alert=True)
                return
            
            task_data = self.sending_tasks[target_user_id]
            await self.execute_sending(callback_query, task_data)
        
        elif data == "cancel_sending":
            user_id = callback_query.from_user.id
            if user_id in self.sending_tasks:
                del self.sending_tasks[user_id]
            
            await callback_query.message.edit_text("❌ Sending cancelled.")
        
        await callback_query.answer()
    
    async def execute_sending(self, callback_query: CallbackQuery, task_data: dict):
        user_id = callback_query.from_user.id
        
        accounts = task_data["accounts"]
        target = task_data["target"]
        messages = task_data["messages"]
        send_type = task_data["type"]
        
        await callback_query.message.edit_text("🚀 Starting to send messages...")
        
        success_count = 0
        fail_count = 0
        results = []
        
        # Log start
        if config.SEND_LOG_CHANNEL:
            log_msg = f"📤 **Sending Started**\n\n"
            log_msg += f"👤 **By:** {callback_query.from_user.mention}\n"
            log_msg += f"🎯 **Target:** `{target}`\n"
            log_msg += f"📱 **Accounts:** {len(accounts)}\n"
            log_msg += f"💬 **Messages:** {len(messages)}\n"
            await log_to_channel(config.SEND_LOG_CHANNEL, log_msg)
        
        from pyrogram import Client
        
        for i, account in enumerate(accounts):
            if config.cancel_operation:
                await callback_query.message.edit_text("⏹️ Operation cancelled by user.")
                return
            
            try:
                client = Client("send_session", session_string=account["session_string"])
                await client.connect()
                
                # Resolve target
                try:
                    if send_type.startswith("bot"):
                        entity = await client.get_users(target)
                    elif send_type.startswith("user"):
                        entity = await client.get_users(target)
                    elif send_type.startswith("group"):
                        entity = await client.get_chat(target)
                except Exception as e:
                    results.append(f"❌ {account['phone']}: Failed to resolve target - {str(e)[:50]}")
                    fail_count += 1
                    await client.disconnect()
                    continue
                
                # Send messages
                for msg in messages:
                    try:
                        if msg.text:
                            await client.send_message(entity.id, msg.text)
                        elif msg.photo:
                            await client.send_photo(entity.id, msg.photo.file_id, caption=msg.caption)
                        elif msg.document:
                            await client.send_document(entity.id, msg.document.file_id, caption=msg.caption)
                        elif msg.video:
                            await client.send_video(entity.id, msg.video.file_id, caption=msg.caption)
                        
                        # Small delay between messages
                        await asyncio.sleep(1)
                    
                    except Exception as e:
                        results.append(f"❌ {account['phone']}: Failed to send - {str(e)[:50]}")
                        fail_count += 1
                        break
                else:
                    results.append(f"✅ {account['phone']}: Success")
                    success_count += 1
                
                await client.disconnect()
                await asyncio.sleep(2)  # Delay between accounts
            
            except Exception as e:
                results.append(f"❌ {account['phone']}: Connection error - {str(e)[:50]}")
                fail_count += 1
            
            # Update progress every 10 accounts
            if (i + 1) % 10 == 0:
                progress = f"📤 **Progress:** {i + 1}/{len(accounts)}\n"
                progress += f"✅ Success: {success_count}\n"
                progress += f"❌ Failed: {fail_count}"
                await callback_query.message.edit_text(progress)
        
        # Final result
        result_text = f"📤 **Sending Complete!**\n\n"
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
            [InlineKeyboardButton("🔄 Send Again", callback_data="send_bot")],
            [InlineKeyboardButton("⬅️ Back", callback_data="back_to_admin")]
        ])
        
        await callback_query.message.edit_text(result_text, reply_markup=keyboard)
        
        # Log completion
        if config.SEND_LOG_CHANNEL:
            log_msg = f"📤 **Sending Completed**\n\n"
            log_msg += f"✅ **Success:** {success_count}\n"
            log_msg += f"❌ **Failed:** {fail_count}\n"
            log_msg += f"🎯 **Target:** `{target}`\n"
            await log_to_channel(config.SEND_LOG_CHANNEL, log_msg)
        
        # Cleanup
        if user_id in self.sending_tasks:
            del self.sending_tasks[user_id]
        if user_id in self.active_operations:
            del self.active_operations[user_id]
    
    async def show_send_stats(self, callback_query: CallbackQuery):
        total_accounts = await db.accounts.count_documents({})
        active_accounts = await db.accounts.count_documents({"is_active": True})
        
        text = f"📊 **Send Statistics**\n\n"
        text += f"📈 **Accounts:**\n"
        text += f"• Total: {total_accounts}\n"
        text += f"• Active: {active_accounts}\n"
        text += f"• Inactive: {total_accounts - active_accounts}\n\n"
        
        if hasattr(self, 'last_send_stats'):
            text += f"📤 **Last Send Operation:**\n"
            text += f"• Accounts used: {self.last_send_stats.get('accounts', 0)}\n"
            text += f"• Success rate: {self.last_send_stats.get('success_rate', 0)}%\n"
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Refresh", callback_data="send_stats")],
            [InlineKeyboardButton("⬅️ Back", callback_data="back_to_admin")]
        ])
        
        await callback_query.message.edit_text(text, reply_markup=keyboard)

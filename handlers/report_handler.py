from pyrogram import filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram import Client, enums
import asyncio
from database import db
from config import config
from utils.logger import log_to_channel, log_action
import random
import time

class ReportHandler:
    def __init__(self, bot):
        self.bot = bot
        self.report_tasks = {}
        self.reporting_active = False
    
    async def handle_report_command(self, message: Message):
        if not config.is_admin(message.from_user.id):
            await message.reply("❌ Admin only command.")
            return
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🤖 Report Bot", callback_data="report_bot")],
            [InlineKeyboardButton("👥 Report Group", callback_data="report_group")],
            [InlineKeyboardButton("📢 Report Channel", callback_data="report_channel")],
            [InlineKeyboardButton("👤 Report User", callback_data="report_user")],
            [InlineKeyboardButton("📝 Report Post", callback_data="report_post")],
            [InlineKeyboardButton("📊 Report Stats", callback_data="report_stats")]
        ])
        
        await message.reply(
            "🚨 **Report System**\n\n"
            "Select what to report:",
            reply_markup=keyboard
        )
        
        await log_action(message.from_user.id, "Opened report menu", "Admin")
    
    async def handle_callback(self, callback_query: CallbackQuery):
        data = callback_query.data
        user_id = callback_query.from_user.id
        
        if not config.is_admin(user_id):
            await callback_query.answer("❌ Unauthorized", show_alert=True)
            return
        
        if data.startswith("report_"):
            report_type = data.split("_")[1]
            
            if user_id not in self.report_tasks:
                self.report_tasks[user_id] = {}
            
            self.report_tasks[user_id]["type"] = report_type
            self.report_tasks[user_id]["step"] = "get_target"
            
            type_names = {
                "bot": "🤖 Bot",
                "group": "👥 Group",
                "channel": "📢 Channel",
                "user": "👤 User",
                "post": "📝 Post"
            }
            
            type_name = type_names.get(report_type, report_type)
            
            prompt = f"🚨 **Report {type_name}**\n\n"
            prompt += "Send the link, username, or ID:\n\n"
            
            if report_type == "post":
                prompt += "Example: `https://t.me/channel/123` or `t.me/c/1234567890/123`\n"
            elif report_type == "bot":
                prompt += "Example: `@botname` or `t.me/botname`\n"
            else:
                prompt += "Example: `@username` or `t.me/username` or ID\n"
            
            prompt += "\nType /cancel to cancel."
            
            await callback_query.message.edit_text(prompt)
        
        elif data == "report_stats":
            await self.show_report_stats(callback_query)
        
        await callback_query.answer()
    
    async def process_message(self, message: Message):
        # Skip commands
        if message.text and message.text.startswith("/"):
            return
        
        user_id = message.from_user.id
        
        if user_id not in self.report_tasks:
            return
        
        task_data = self.report_tasks[user_id]
        step = task_data.get("step")
        report_type = task_data.get("type")
        
        if step == "get_target":
            target = message.text.strip()
            
            if not target:
                await message.reply("❌ Invalid target. Please try again.")
                return
            
            task_data["target"] = target
            task_data["step"] = "get_reason"
            
            # Define reasons based on report type
            if report_type == "bot":
                reasons = [
                    "🤖 Fake bot",
                    "💳 Payment scam",
                    "📩 Spam messages",
                    "🔞 Pornography",
                    "💀 Violence",
                    "⚖️ Illegal activities"
                ]
            elif report_type == "user":
                reasons = [
                    "👤 Fake account",
                    "📩 Spam messages",
                    "🔞 Pornography",
                    "💀 Violence",
                    "💰 Financial scam",
                    "⚖️ Illegal activities"
                ]
            else:  # group, channel, post
                reasons = [
                    "🔞 Pornography",
                    "💀 Violence",
                    "💰 Financial scam",
                    "⚖️ Illegal activities",
                    "📢 Fake news",
                    "👥 Impersonation"
                ]
            
            task_data["reasons"] = reasons
            
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton(reason, callback_data=f"reason:{i}")]
                for i, reason in enumerate(reasons[:6])  # First 6 reasons
            ])
            
            if len(reasons) > 6:
                keyboard.inline_keyboard.append([
                    InlineKeyboardButton("More reasons...", callback_data="more_reasons")
                ])
            
            keyboard.inline_keyboard.append([
                InlineKeyboardButton("❌ Cancel", callback_data="cancel_report")
            ])
            
            type_names = {
                "bot": "Bot",
                "group": "Group",
                "channel": "Channel",
                "user": "User",
                "post": "Post"
            }
            
            type_name = type_names.get(report_type, report_type)
            
            await message.reply(
                f"🚨 **Report {type_name}**\n\n"
                f"Target: `{target}`\n\n"
                "Select report reason:",
                reply_markup=keyboard
            )
            
            self.report_tasks[user_id] = task_data
        
        elif step == "get_description":
            description = message.text
            
            if len(description) < 10:
                await message.reply("❌ Description too short. Please provide more details (minimum 10 characters).")
                return
            
            task_data["description"] = description
            task_data["step"] = "get_count"
            
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("1 report per account", callback_data="count:1")],
                [InlineKeyboardButton("2 reports per account", callback_data="count:2")],
                [InlineKeyboardButton("3 reports per account", callback_data="count:3")],
                [InlineKeyboardButton("Custom number", callback_data="count:custom")],
                [InlineKeyboardButton("❌ Cancel", callback_data="cancel_report")]
            ])
            
            await message.reply(
                "📊 **Reports per Account**\n\n"
                "How many reports should each account send?\n\n"
                "Note: Too many reports may trigger spam detection.",
                reply_markup=keyboard
            )
            
            self.report_tasks[user_id] = task_data
        
        elif step == "get_custom_count":
            try:
                count = int(message.text)
                if count < 1 or count > 10:
                    await message.reply("❌ Number must be between 1 and 10. Please try again:")
                    return
                
                task_data["count"] = count
                task_data["step"] = "confirm"
                
                await self.show_report_confirmation(message, task_data)
                
                self.report_tasks[user_id] = task_data
            
            except ValueError:
                await message.reply("❌ Please enter a valid number between 1 and 10:")
    
    async def handle_report_callback(self, callback_query: CallbackQuery):
        data = callback_query.data
        user_id = callback_query.from_user.id
        
        if user_id not in self.report_tasks:
            await callback_query.answer("❌ Session expired", show_alert=True)
            return
        
        task_data = self.report_tasks[user_id]
        
        if data.startswith("reason:"):
            reason_idx = int(data.split(":")[1])
            reasons = task_data.get("reasons", [])
            
            if 0 <= reason_idx < len(reasons):
                task_data["reason"] = reasons[reason_idx]
                task_data["step"] = "get_description"
                
                await callback_query.message.edit_text(
                    f"📝 **Report Description**\n\n"
                    f"Reason: {reasons[reason_idx]}\n\n"
                    "Please describe the issue in detail (minimum 10 characters):\n\n"
                    "Type /cancel to cancel."
                )
                
                self.report_tasks[user_id] = task_data
        
        elif data == "more_reasons":
            reasons = task_data.get("reasons", [])
            
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton(reason, callback_data=f"reason:{i}")]
                for i, reason in enumerate(reasons[6:], 6)  # Remaining reasons
            ])
            
            keyboard.inline_keyboard.append([
                InlineKeyboardButton("⬅️ Back", callback_data="back_reasons")
            ])
            
            await callback_query.message.edit_text(
                "Select report reason:",
                reply_markup=keyboard
            )
        
        elif data == "back_reasons":
            reasons = task_data.get("reasons", [])
            
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton(reason, callback_data=f"reason:{i}")]
                for i, reason in enumerate(reasons[:6])
            ])
            
            if len(reasons) > 6:
                keyboard.inline_keyboard.append([
                    InlineKeyboardButton("More reasons...", callback_data="more_reasons")
                ])
            
            keyboard.inline_keyboard.append([
                InlineKeyboardButton("❌ Cancel", callback_data="cancel_report")
            ])
            
            await callback_query.message.edit_text(
                "Select report reason:",
                reply_markup=keyboard
            )
        
        elif data.startswith("count:"):
            count_str = data.split(":")[1]
            
            if count_str == "custom":
                task_data["step"] = "get_custom_count"
                await callback_query.message.edit_text(
                    "Enter custom number of reports per account (1-10):\n\n"
                    "Type /cancel to cancel."
                )
            else:
                count = int(count_str)
                task_data["count"] = count
                task_data["step"] = "confirm"
                
                await self.show_report_confirmation(callback_query, task_data)
            
            self.report_tasks[user_id] = task_data
        
        elif data == "start_reporting":
            await self.start_reporting(callback_query)
        
        elif data == "cancel_report":
            if user_id in self.report_tasks:
                del self.report_tasks[user_id]
            
            await callback_query.message.edit_text("❌ Report cancelled.")
        
        await callback_query.answer()
    
    async def show_report_confirmation(self, update, task_data: dict):
        user_id = update.from_user.id if isinstance(update, CallbackQuery) else update.from_user.id
        
        report_type = task_data.get("type")
        target = task_data.get("target")
        reason = task_data.get("reason")
        description = task_data.get("description", "No description")
        count = task_data.get("count", 1)
        
        type_names = {
            "bot": "🤖 Bot",
            "group": "👥 Group",
            "channel": "📢 Channel",
            "user": "👤 User",
            "post": "📝 Post"
        }
        
        type_name = type_names.get(report_type, report_type)
        
        # Get active accounts
        accounts = await db.accounts.find({"is_active": True}).to_list(length=100)
        
        confirmation = f"🚨 **Report Confirmation**\n\n"
        confirmation += f"🔧 **Type:** {type_name}\n"
        confirmation += f"🎯 **Target:** `{target}`\n"
        confirmation += f"📋 **Reason:** {reason}\n"
        confirmation += f"📝 **Description:** {description[:100]}...\n"
        confirmation += f"📊 **Reports/Account:** {count}\n"
        confirmation += f"📱 **Active Accounts:** {len(accounts)}\n"
        confirmation += f"📈 **Total Reports:** {len(accounts) * count}\n\n"
        confirmation += "⚠️ **Are you sure you want to start reporting?**\n"
        confirmation += "Use /stop to stop reporting at any time."
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Start Reporting", callback_data="start_reporting")],
            [InlineKeyboardButton("❌ Cancel", callback_data="cancel_report")]
        ])
        
        if isinstance(update, CallbackQuery):
            await update.message.edit_text(confirmation, reply_markup=keyboard)
        else:
            await update.reply(confirmation, reply_markup=keyboard)
        
        # Store accounts in task data
        task_data["accounts"] = accounts
        self.report_tasks[user_id] = task_data
    
    async def start_reporting(self, callback_query: CallbackQuery):
        user_id = callback_query.from_user.id
        
        if user_id not in self.report_tasks:
            await callback_query.answer("❌ Session expired", show_alert=True)
            return
        
        task_data = self.report_tasks[user_id]
        
        # Reset stop flag
        config.stop_reporting = False
        
        await callback_query.message.edit_text("🚨 Starting reports... This may take a while.")
        
        # Log start
        if config.REPORT_LOG_CHANNEL:
            log_msg = f"🚨 **Reporting Started**\n\n"
            log_msg += f"👤 **By:** {callback_query.from_user.mention}\n"
            log_msg += f"🎯 **Target:** `{task_data['target']}`\n"
            log_msg += f"📋 **Reason:** {task_data['reason']}\n"
            log_msg += f"📱 **Accounts:** {len(task_data['accounts'])}\n"
            await log_to_channel(config.REPORT_LOG_CHANNEL, log_msg)
        
        # Start reporting in background
        asyncio.create_task(self.execute_reporting(callback_query, task_data))
    
    async def execute_reporting(self, callback_query: CallbackQuery, task_data: dict):
        user_id = callback_query.from_user.id
        
        report_type = task_data.get("type")
        target = task_data.get("target")
        reason = task_data.get("reason")
        description = task_data.get("description", "")
        count = task_data.get("count", 1)
        accounts = task_data.get("accounts", [])
        
        success_count = 0
        fail_count = 0
        total_reports = 0
        results = []
        
        self.reporting_active = True
        
        from pyrogram import Client
        
        for i, account in enumerate(accounts):
            if config.stop_reporting:
                await callback_query.message.edit_text("⏹️ Reporting stopped by user.")
                self.reporting_active = False
                return
            
            if config.cancel_operation:
                await callback_query.message.edit_text("⏹️ Operation cancelled.")
                self.reporting_active = False
                return
            
            try:
                client = Client("report_session", session_string=account["session_string"])
                await client.connect()
                
                # Human-like behavior: random delays
                await asyncio.sleep(random.uniform(2, 5))
                
                try:
                    # Resolve target based on type
                    if report_type == "bot":
                        entity = await client.get_users(target)
                        entity_type = enums.ReportReasonType.CHILD_ABUSE  # Default
                    elif report_type == "user":
                        entity = await client.get_users(target)
                        entity_type = enums.ReportReasonType.CHILD_ABUSE
                    elif report_type == "group":
                        # Try to join first if needed
                        try:
                            entity = await client.get_chat(target)
                        except:
                            # Try to join
                            try:
                                if target.startswith("@"):
                                    await client.join_chat(target)
                                elif target.startswith("t.me/"):
                                    await client.join_chat(target)
                                entity = await client.get_chat(target)
                            except:
                                results.append(f"❌ {account['phone']}: Could not access group")
                                fail_count += 1
                                await client.disconnect()
                                continue
                        entity_type = enums.ReportReasonType.CHILD_ABUSE
                    elif report_type == "channel":
                        try:
                            entity = await client.get_chat(target)
                        except:
                            results.append(f"❌ {account['phone']}: Could not access channel")
                            fail_count += 1
                            await client.disconnect()
                            continue
                        entity_type = enums.ReportReasonType.CHILD_ABUSE
                    elif report_type == "post":
                        # Parse post link
                        if "t.me/c/" in target or "t.me/" in target:
                            # Extract channel and message ID
                            parts = target.split("/")
                            if len(parts) >= 2:
                                channel = parts[-2]
                                try:
                                    message_id = int(parts[-1])
                                except:
                                    message_id = None
                                
                                if message_id:
                                    try:
                                        entity = await client.get_chat(channel)
                                        # Report the specific message
                                        await client.report_chat(
                                            entity.id,
                                            enums.ReportReasonType.CHILD_ABUSE,
                                            message_id
                                        )
                                        success_count += 1
                                        total_reports += 1
                                        results.append(f"✅ {account['phone']}: Post reported")
                                    except Exception as e:
                                        results.append(f"❌ {account['phone']}: {str(e)[:50]}")
                                        fail_count += 1
                                else:
                                    results.append(f"❌ {account['phone']}: Invalid post link")
                                    fail_count += 1
                            
                            await client.disconnect()
                            continue
                        else:
                            results.append(f"❌ {account['phone']}: Invalid post link")
                            fail_count += 1
                            await client.disconnect()
                            continue
                    else:
                        results.append(f"❌ {account['phone']}: Unknown report type")
                        fail_count += 1
                        await client.disconnect()
                        continue
                    
                    # Send reports
                    reports_sent = 0
                    for report_num in range(count):
                        if config.stop_reporting:
                            break
                        
                        try:
                            if report_type == "post":
                                # Already handled above
                                break
                            else:
                                await client.report_chat(
                                    entity.id,
                                    entity_type,
                                    description[:200]  # Limit description length
                                )
                            
                            reports_sent += 1
                            total_reports += 1
                            
                            # Random delay between reports from same account
                            if report_num < count - 1:
                                await asyncio.sleep(random.uniform(10, 30))
                        
                        except Exception as e:
                            error_msg = str(e)
                            if "FLOOD_WAIT" in error_msg:
                                results.append(f"⏳ {account['phone']}: Flood wait")
                                break
                            elif "Too Many Requests" in error_msg:
                                results.append(f"⚠️ {account['phone']}: Too many requests")
                                break
                            else:
                                results.append(f"❌ {account['phone']}: Report {report_num+1} failed - {error_msg[:50]}")
                    
                    if reports_sent > 0:
                        success_count += 1
                        if reports_sent == count:
                            results.append(f"✅ {account['phone']}: All {count} reports sent")
                        else:
                            results.append(f"⚠️ {account['phone']}: {reports_sent}/{count} reports sent")
                    else:
                        fail_count += 1
                
                except Exception as e:
                    results.append(f"❌ {account['phone']}: {str(e)[:50]}")
                    fail_count += 1
                
                await client.disconnect()
                
                # Random delay between accounts
                await asyncio.sleep(random.uniform(5, 15))
            
            except Exception as e:
                results.append(f"❌ {account['phone']}: Connection error - {str(e)[:50]}")
                fail_count += 1
            
            # Update progress every 10 accounts
            if (i + 1) % 10 == 0:
                progress = f"🚨 **Progress:** {i + 1}/{len(accounts)}\n"
                progress += f"✅ Success: {success_count}\n"
                progress += f"❌ Failed: {fail_count}\n"
                progress += f"📊 Total Reports: {total_reports}"
                await callback_query.message.edit_text(progress)
        
        # Final result
        self.reporting_active = False
        
        result_text = f"🚨 **Reporting Complete!**\n\n"
        result_text += f"🎯 **Target:** `{target}`\n"
        result_text += f"📋 **Reason:** {reason}\n"
        result_text += f"✅ **Successful Accounts:** {success_count}\n"
        result_text += f"❌ **Failed Accounts:** {fail_count}\n"
        result_text += f"📊 **Total Reports Sent:** {total_reports}\n"
        result_text += f"📈 **Total Accounts:** {len(accounts)}\n\n"
        
        if results:
            result_text += "**First 20 Results:**\n"
            for res in results[:20]:
                result_text += f"{res}\n"
            
            if len(results) > 20:
                result_text += f"\n... and {len(results) - 20} more"
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Report Another", callback_data="report_again")],
            [InlineKeyboardButton("⬅️ Back", callback_data="back_to_admin")]
        ])
        
        await callback_query.message.edit_text(result_text, reply_markup=keyboard)
        
        # Log completion
        if config.REPORT_LOG_CHANNEL:
            log_msg = f"🚨 **Reporting Completed**\n\n"
            log_msg += f"✅ **Successful:** {success_count}\n"
            log_msg += f"❌ **Failed:** {fail_count}\n"
            log_msg += f"📊 **Total Reports:** {total_reports}\n"
            log_msg += f"🎯 **Target:** `{target}`\n"
            await log_to_channel(config.REPORT_LOG_CHANNEL, log_msg)
        
        # Cleanup
        if user_id in self.report_tasks:
            del self.report_tasks[user_id]
    
    async def show_report_stats(self, callback_query: CallbackQuery):
        total_accounts = await db.accounts.count_documents({})
        active_accounts = await db.accounts.count_documents({"is_active": True})
        
        text = f"🚨 **Report Statistics**\n\n"
        text += f"📈 **Accounts:**\n"
        text += f"• Total: {total_accounts}\n"
        text += f"• Active: {active_accounts}\n"
        text += f"• Inactive: {total_accounts - active_accounts}\n\n"
        
        if self.reporting_active:
            text += f"🔴 **Status:** Currently reporting\n"
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Refresh", callback_data="report_stats")],
            [InlineKeyboardButton("⬅️ Back", callback_data="back_to_admin")]
        ])
        
        await callback_query.message.edit_text(text, reply_markup=keyboard)

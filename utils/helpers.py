import re
import asyncio
from typing import List, Union
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

def create_paginated_keyboard(items: List, page: int, items_per_page: int = 10,
                              prefix: str = "item", callback_data: str = "select"):
    """Create paginated inline keyboard"""
    start_idx = page * items_per_page
    end_idx = start_idx + items_per_page
    page_items = items[start_idx:end_idx]
    
    keyboard = []
    for i, item in enumerate(page_items, start=1):
        item_num = start_idx + i
        keyboard.append([
            InlineKeyboardButton(
                f"{item_num}. {item.get('name', item.get('phone', 'Unknown'))}",
                callback_data=f"{callback_data}:{item.get('_id')}"
            )
        ])
    
    # Navigation buttons
    nav_buttons = []
    if page > 0:
        nav_buttons.append(
            InlineKeyboardButton("⬅️ Previous", callback_data=f"{prefix}_prev:{page-1}")
        )
    if end_idx < len(items):
        nav_buttons.append(
            InlineKeyboardButton("Next ➡️", callback_data=f"{prefix}_next:{page+1}")
        )
    
    if nav_buttons:
        keyboard.append(nav_buttons)
    
    return InlineKeyboardMarkup(keyboard)

def parse_account_numbers(input_str: str) -> List[int]:
    """Parse account numbers from string like '1,3,4' or '1-5' or '1,3-5'"""
    numbers = set()
    if not input_str:
        return []
    
    parts = input_str.replace(" ", "").split(",")
    
    for part in parts:
        if "-" in part:
            try:
                start, end = map(int, part.split("-"))
                if start < end:
                    numbers.update(range(start, end + 1))
                else:
                    numbers.update(range(end, start + 1))
            except:
                continue
        else:
            try:
                numbers.add(int(part))
            except:
                continue
    
    return sorted(list(numbers))

def validate_phone_number(phone: str) -> bool:
    """Validate phone number format"""
    pattern = r'^\+?[1-9]\d{7,14}$'
    return bool(re.match(pattern, phone))

async def chunk_list(lst, n):
    """Yield successive n-sized chunks from lst."""
    for i in range(0, len(lst), n):
        yield lst[i:i + n]

def create_account_selection_keyboard(accounts: List, selected: List = None, page: int = 0):
    """Create keyboard for account selection with checkboxes"""
    if selected is None:
        selected = []
    
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
                callback_data=f"select_acc:{idx}"
            )
        ])
    
    # Navigation buttons
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("⬅️", callback_data=f"acc_page:{page-1}"))
    
    if len(selected) > 0:
        nav_buttons.append(InlineKeyboardButton("🚀 Proceed", callback_data="acc_proceed"))
    
    if end_idx < len(accounts):
        nav_buttons.append(InlineKeyboardButton("➡️", callback_data=f"acc_page:{page+1}"))
    
    if nav_buttons:
        keyboard.append(nav_buttons)
    
    # Confirm selection button
    if len(selected) > 0:
        keyboard.append([
            InlineKeyboardButton(f"✅ Confirm ({len(selected)} selected)", callback_data="confirm_selection")
        ])
    
    return InlineKeyboardMarkup(keyboard)

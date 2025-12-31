from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, KeyboardButton, ReplyKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from database.models import Channel
from typing import List
from utils.texts import get_text

async def get_main_menu(lang: str = 'ru') -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.button(text=await get_text('main_menu_create', lang))
    builder.button(text=await get_text('main_menu_channels', lang))
    builder.button(text=await get_text('main_menu_settings', lang))
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True)

def get_channels_menu(channels: List[Channel]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for channel in channels:
        builder.button(text=channel.title, callback_data=f"select_channel_{channel.id}")
    builder.button(text="➕ Add Channel", callback_data="add_channel")
    builder.adjust(1)
    return builder.as_markup()

def get_post_creation_menu(has_content: bool = False, has_buttons: bool = False) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    
    if has_content:
        builder.button(text="🔗 Add URL Button", callback_data="add_btn_url")
        builder.button(text="🔔 Add Alert Button", callback_data="add_btn_alert")
        # builder.button(text="🇺🇸 Add Translation", callback_data="add_btn_translate")
        builder.button(text="❌ Clear Buttons", callback_data="clear_buttons")
        
        builder.button(text="✅ Done / Publish", callback_data="post_done")
        builder.button(text="🗑 Cancel", callback_data="post_cancel")
        
    builder.adjust(2, 2, 2)
    return builder.as_markup()

def get_publish_options_menu(is_pinned: bool = False, is_silent: bool = False) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🚀 Publish Now", callback_data="pub_now")
    builder.button(text="📅 Schedule", callback_data="pub_schedule")
    
    pin_text = "📌 Pin: On" if is_pinned else "📌 Pin: Off"
    builder.button(text=pin_text, callback_data="toggle_pin")
    
    silent_text = "🔕 Silent: On" if is_silent else "🔕 Silent: Off"
    builder.button(text=silent_text, callback_data="toggle_silent")
    
    builder.button(text="🔙 Back", callback_data="back_to_edit")
    builder.adjust(2, 2, 1)
    return builder.as_markup()
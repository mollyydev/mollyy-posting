from typing import Union
from aiogram.filters import BaseFilter
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from utils.checks import check_subscription
from handlers.base import get_lang
from utils.texts import get_text

class SubscriptionFilter(BaseFilter):
    async def __call__(self, event: Union[Message, CallbackQuery]) -> bool:
        # Allow checking subscription explicitly
        if isinstance(event, CallbackQuery) and event.data == "check_sub":
            return True
            
        # Allow language selection callbacks to pass through (as they are part of setup)
        if isinstance(event, CallbackQuery) and event.data.startswith("set_lang_"):
            return True

        user_id = event.from_user.id
        bot = event.bot
        
        # Check sub
        is_subbed = await check_subscription(bot, user_id)
        if is_subbed:
            return True
            
        # If not subbed, send prompt
        lang = await get_lang(user_id)
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=await get_text('sub_check_btn', lang), url="https://t.me/highprod")],
            [InlineKeyboardButton(text=await get_text('sub_check_verify', lang), callback_data="check_sub")]
        ])
        
        text = await get_text('sub_check_prompt', lang)
        
        if isinstance(event, Message):
            await event.answer(text, reply_markup=kb)
        elif isinstance(event, CallbackQuery):
            # Don't edit message if it's already the sub prompt?
            # Just answer with alert or send new message?
            # If we edit, we might disrupt flow. Better to send ephemeral or edit if relevant.
            # Simple approach: Answer with alert and send message.
            # await event.answer(text, show_alert=True) # Alert might be too long or annoying.
            # Let's try sending a fresh message to be sure.
            await event.message.answer(text, reply_markup=kb)
            await event.answer()
            
        return False
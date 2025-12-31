from aiogram import Router, F, types, Bot
from aiogram.fsm.context import FSMContext
from sqlalchemy import select
from datetime import datetime
import json

from database.db import get_db_session
from database.models import Channel, ScheduledPost, AlertStorage

router = Router()

# Helper to reconstruct keyboard from stored JSON
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from aiogram.utils.keyboard import InlineKeyboardBuilder

def reconstruct_keyboard(buttons_data):
    builder = InlineKeyboardBuilder()
    for i, btn in enumerate(buttons_data):
        if btn['type'] == 'url':
            # Ensure URL is valid string
            if btn.get('url'):
                builder.button(text=btn['text'], url=btn['url'])
        elif btn['type'] == 'webapp':
            # Ensure WebApp URL is valid string
            if btn.get('url'):
                builder.button(text=btn['text'], web_app=WebAppInfo(url=btn['url']))
        elif btn['type'] == 'alert':
            # Use stored UUID for alert
            uuid = btn.get('alert_id')
            if uuid:
                builder.button(text=btn['text'], callback_data=f"alert_{uuid}")
    builder.adjust(1)
    return builder.as_markup()

@router.callback_query(F.data.startswith("alert_"))
async def show_alert(callback: types.CallbackQuery):
    # Format: alert_{uuid}
    try:
        uuid = callback.data.split("_")[1]
        
        async for session in get_db_session():
            alert = await session.get(AlertStorage, uuid)
            if alert:
                await callback.answer(alert.text, show_alert=True)
            else:
                await callback.answer("Alert not found.", show_alert=True)

    except Exception as e:
        await callback.answer("Error showing alert.", show_alert=True)
        print(f"Alert error: {e}")

# This router should be included in main.py
from typing import Union
from aiogram.filters import BaseFilter
from aiogram.types import Message, CallbackQuery
from sqlalchemy import select

from data.config import ADMIN_IDS
from database.db import get_db_session
from database.models import Settings

class AdminFilter(BaseFilter):
    async def __call__(self, event: Union[Message, CallbackQuery]) -> bool:
        if event.from_user.id in ADMIN_IDS:
            return True
        
        # If not admin, send denied message and return False
        async for session in get_db_session():
            result = await session.execute(select(Settings))
            settings = result.scalars().first()
            denied_text = settings.access_denied_text if settings else "Access Denied."
            
            if isinstance(event, Message):
                await event.answer(denied_text)
            elif isinstance(event, CallbackQuery):
                await event.answer(denied_text, show_alert=True)
            
            return False
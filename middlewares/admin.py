from typing import Any, Awaitable, Callable, Dict
from aiogram import BaseMiddleware
from aiogram.types import Message, Update
from sqlalchemy import select
from data.config import ADMIN_IDS
from database.db import get_db_session
from database.models import Settings

class AdminMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Update, Dict[str, Any]], Awaitable[Any]],
        event: Update,
        data: Dict[str, Any],
    ) -> Any:
        user = data.get("event_from_user")
        if not user:
            return await handler(event, data)

        if user.id not in ADMIN_IDS:
            # If not admin, check DB for custom access denied message
            async for session in get_db_session():
                result = await session.execute(select(Settings))
                settings = result.scalars().first()
                denied_text = settings.access_denied_text if settings else "Access Denied."
                
                # Try to send message if event is a message
                if isinstance(event, Message):
                    await event.answer(denied_text)
                # Or if it's a callback query
                elif event.callback_query:
                    await event.callback_query.answer(denied_text, show_alert=True)
                
                return  # Stop propagation

        return await handler(event, data)
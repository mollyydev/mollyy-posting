import asyncio
from typing import Any, Awaitable, Callable, Dict, List, Union

from aiogram import BaseMiddleware
from aiogram.types import Message


class AlbumMiddleware(BaseMiddleware):
    def __init__(self, latency: float = 0.5):
        self.latency = latency
        self.album_data: Dict[str, List[Message]] = {}

    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any],
    ) -> Any:
        if not event.media_group_id:
            return await handler(event, data)

        try:
            self.album_data[event.media_group_id].append(event)
            return  # Don't propagate yet, wait for other media
        except KeyError:
            self.album_data[event.media_group_id] = [event]
            await asyncio.sleep(self.latency)

            # Get the collected messages
            messages = self.album_data.pop(event.media_group_id)
            
            # Sort by message_id just in case
            messages.sort(key=lambda x: x.message_id)

            # Pass the list of messages as 'album' in data
            data["album"] = messages
            
            # Use the first message to trigger the handler
            return await handler(event, data)
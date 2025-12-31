from aiogram import Router, F, types
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from sqlalchemy import select

from database.db import get_db_session
from database.models import Channel, Settings
from utils.keyboards import get_main_menu, get_channels_menu
from utils.states import ChannelState, PostState
from utils.texts import get_text

router = Router()

async def get_lang():
    # Helper to get global lang, better to cache or use middleware,
    # but for now query DB
    async for session in get_db_session():
        settings = (await session.execute(select(Settings))).scalars().first()
        return settings.language if settings else 'ru'
    return 'ru'

@router.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    lang = await get_lang()
    await message.answer(
        await get_text('start_welcome', lang),
        reply_markup=await get_main_menu(lang)
    )

@router.message(F.text.in_({"📢 Channels", "📢 Каналы"}))
async def show_channels(message: types.Message):
    async for session in get_db_session():
        result = await session.execute(select(Channel))
        channels = result.scalars().all()
        lang = await get_lang()
        await message.answer(
            await get_text('channels_list', lang),
            reply_markup=get_channels_menu(channels)
        )

@router.callback_query(F.data == "add_channel")
async def start_add_channel(callback: types.CallbackQuery, state: FSMContext):
    lang = await get_lang()
    await callback.message.answer(await get_text('add_channel_prompt', lang))
    await state.set_state(ChannelState.waiting_for_channel_forward)
    await callback.answer()

@router.message(ChannelState.waiting_for_channel_forward)
async def process_channel_forward(message: types.Message, state: FSMContext):
    lang = await get_lang()
    if not message.forward_from_chat:
        await message.answer("Please forward a message FROM the channel.") # Keep generic or add translation
        return
    
    chat = message.forward_from_chat
    if chat.type != 'channel':
        await message.answer("This doesn't look like a channel.")
        return

    # Check if we are admin there (try to get chat member)
    try:
        member = await message.bot.get_chat_member(chat.id, message.bot.id)
        if not member.status in ('administrator', 'creator'):
            await message.answer(await get_text('not_admin', lang))
            return
    except Exception as e:
        await message.answer(f"Error accessing channel: {e}. Make sure I'm added.")
        return

    # Save to DB
    async for session in get_db_session():
        # Check if exists
        result = await session.execute(select(Channel).where(Channel.telegram_id == chat.id))
        if result.scalars().first():
            await message.answer(await get_text('channel_exists', lang))
            await state.clear()
            return
        
        new_channel = Channel(
            telegram_id=chat.id,
            title=chat.title,
            added_by=message.from_user.id
        )
        session.add(new_channel)
        await session.commit()
        
    await message.answer(await get_text('channel_added', lang, title=chat.title))
    await state.clear()
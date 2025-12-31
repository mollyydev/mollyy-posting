from aiogram import Router, F, types
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from sqlalchemy import select

from database.db import get_db_session
from database.models import Channel, Settings, User
from utils.keyboards import get_main_menu, get_channels_menu
from utils.states import ChannelState, PostState
from utils.texts import get_text
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from utils.checks import check_subscription

router = Router()

async def get_lang(user_id: int = None):
    if not user_id:
        # Fallback for system messages or unknown user context (unlikely)
        return 'en'
        
    async for session in get_db_session():
        user = await session.get(User, user_id)
        if user:
            return user.language
    return 'en'

@router.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    
    async for session in get_db_session():
        user = await session.get(User, user_id)
        if not user:
            # New user, ask for language
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🇺🇸 English", callback_data="set_lang_en"),
                 InlineKeyboardButton(text="🇷🇺 Русский", callback_data="set_lang_ru")]
            ])
            await message.answer("🌍 Please choose your language / Пожалуйста, выберите язык:", reply_markup=kb)
            return
    
    # If user exists, SubscriptionFilter will run before this and block if needed.
    # If we reached here, user is subbed.
    lang = await get_lang(user_id)
    await message.answer(
        await get_text('start_welcome', lang),
        reply_markup=await get_main_menu(lang)
    )

@router.callback_query(F.data.startswith("set_lang_"))
async def set_language(callback: types.CallbackQuery):
    lang_code = callback.data.split("_")[-1]
    user_id = callback.from_user.id
    
    async for session in get_db_session():
        user = await session.get(User, user_id)
        if not user:
            user = User(id=user_id, telegram_id=user_id, language=lang_code)
            session.add(user)
        else:
            user.language = lang_code
        await session.commit()
    
    # SubscriptionFilter will catch next interaction if not subbed.
    # But for UX, we can check here too or just show welcome.
    # If we show welcome, next click will trigger filter.
    # Better to show prompt immediately if not subbed.
    if not await check_subscription(callback.bot, user_id):
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=await get_text('sub_check_btn', lang_code), url="https://t.me/highprod")],
            [InlineKeyboardButton(text=await get_text('sub_check_verify', lang_code), callback_data="check_sub")]
        ])
        await callback.message.edit_text(await get_text('sub_check_prompt', lang_code), reply_markup=kb)
        return

    await callback.message.delete()
    await callback.message.answer(
        await get_text('start_welcome', lang_code),
        reply_markup=await get_main_menu(lang_code)
    )

@router.callback_query(F.data == "check_sub")
async def verify_subscription(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    lang = await get_lang(user_id)
    
    if await check_subscription(callback.bot, user_id):
        await callback.message.delete()
        await callback.message.answer(
            await get_text('start_welcome', lang),
            reply_markup=await get_main_menu(lang)
        )
    else:
        await callback.answer(await get_text('sub_check_fail', lang), show_alert=True)

@router.message(F.text.in_({"📢 Channels", "📢 Каналы"}))
async def show_channels(message: types.Message):
    async for session in get_db_session():
        result = await session.execute(select(Channel))
        channels = result.scalars().all()
        lang = await get_lang(message.from_user.id)
        await message.answer(
            await get_text('channels_list', lang),
            reply_markup=get_channels_menu(channels)
        )

@router.callback_query(F.data == "add_channel")
async def start_add_channel(callback: types.CallbackQuery, state: FSMContext):
    lang = await get_lang(callback.from_user.id)
    await callback.message.answer(await get_text('add_channel_prompt', lang))
    await state.set_state(ChannelState.waiting_for_channel_forward)
    await callback.answer()

@router.message(ChannelState.waiting_for_channel_forward)
async def process_channel_forward(message: types.Message, state: FSMContext):
    lang = await get_lang(message.from_user.id)
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
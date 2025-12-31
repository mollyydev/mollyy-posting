from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import select

from database.db import get_db_session
from database.models import Settings, ScheduledPost, Channel, User
from utils.keyboards import get_main_menu
from utils.texts import get_text

router = Router()

class AdminState(StatesGroup):
    waiting_for_denied_text = State()

@router.message(F.text.in_({"⚙️ Settings", "⚙️ Настройки"}))
async def settings_menu(message: types.Message):
    from handlers.base import get_lang
    lang = await get_lang(message.from_user.id)
    await message.answer(
        await get_text('settings_menu', lang),
        reply_markup=types.InlineKeyboardMarkup(
            inline_keyboard=[
                [types.InlineKeyboardButton(text="🚫 Edit 'Access Denied' Text", callback_data="edit_denied_text")],
                [types.InlineKeyboardButton(text="📅 View Scheduled Posts", callback_data="view_scheduled")],
                [types.InlineKeyboardButton(text="🇷🇺 Switch to Russian / English 🇺🇸", callback_data="switch_lang")]
            ]
        )
    )

@router.callback_query(F.data == "switch_lang")
async def switch_language(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    async for session in get_db_session():
        user = await session.get(User, user_id)
        if not user:
            # Should exist if interacting, but just in case
            user = User(id=user_id, telegram_id=user_id, language='en')
            session.add(user)
        
        new_lang = 'en' if user.language == 'ru' else 'ru'
        user.language = new_lang
        await session.commit()
        
        from handlers.base import get_lang
        lang = new_lang
        await callback.message.answer(await get_text('language_selected', lang))
        await callback.message.answer(await get_text('start_welcome', lang), reply_markup=await get_main_menu(lang))
        await callback.answer()

@router.callback_query(F.data == "edit_denied_text")
async def edit_denied_text(callback: types.CallbackQuery, state: FSMContext):
    from handlers.base import get_lang
    lang = await get_lang(callback.from_user.id)
    await callback.message.answer(await get_text('edit_denied_text', lang))
    await state.set_state(AdminState.waiting_for_denied_text)
    await callback.answer()

@router.message(AdminState.waiting_for_denied_text)
async def save_denied_text(message: types.Message, state: FSMContext):
    async for session in get_db_session():
        # Get or create settings
        result = await session.execute(select(Settings))
        settings = result.scalars().first()
        if not settings:
            settings = Settings()
            session.add(settings)
        
        settings.access_denied_text = message.text
        await session.commit()
    
    from handlers.base import get_lang
    lang = await get_lang(message.from_user.id)
    await message.answer(await get_text('denied_updated', lang))
    await state.clear()

@router.callback_query(F.data == "view_scheduled")
async def view_scheduled(callback: types.CallbackQuery):
    async for session in get_db_session():
        # Get pending posts
        result = await session.execute(select(ScheduledPost).where(ScheduledPost.status == 'pending').order_by(ScheduledPost.run_date))
        posts = result.scalars().all()
        
        if not posts:
            from handlers.base import get_lang
            lang = await get_lang(callback.from_user.id)
            await callback.message.answer(await get_text('no_scheduled', lang))
            await callback.answer()
            return

        text = "📅 **Scheduled Posts:**\n\n"
        for post in posts:
            channel = await session.get(Channel, post.chat_id)
            channel_name = channel.title if channel else "Unknown"
            text += f"🆔 {post.id} | 📢 {channel_name}\n🕒 {post.run_date}\n\n"
        
        await callback.message.answer(text)
        await callback.answer()
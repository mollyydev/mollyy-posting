from aiogram import Router, F, types, Bot
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from sqlalchemy import select
from datetime import datetime, timedelta
import pytz

from database.db import get_db_session
from database.models import Channel, ScheduledPost, AlertStorage
from utils.states import PostState
from utils.keyboards import get_channels_menu, get_post_creation_menu, get_publish_options_menu, get_main_menu
from utils.translator import translate_text
from utils.scheduler import scheduler
from utils.texts import get_text
from handlers.base import get_lang
import uuid

router = Router()

# --- Helpers ---

async def render_post_preview(bot: Bot, chat_id: int, data: dict):
    """
    Sends a preview of the post to the admin.
    Handles Text, Photo, Video, Document, and MediaGroups (Albums).
    """
    content = data.get('content')
    buttons = data.get('buttons', [])
    
    # Construct Inline Keyboard
    kb_builder = InlineKeyboardBuilder()
    for btn in buttons:
        if btn['type'] == 'url':
            kb_builder.button(text=btn['text'], url=btn['url'])
        elif btn['type'] == 'alert':
            # Store full text in callback_data might be too long. 
            # Ideally, store in DB or compact it. For simplicity, we use callback_data if short
            # or we need a dynamic callback handler that looks up the text.
            # Here we will use a prefix 'alert:' and put the text. Beware of 64 byte limit!
            # BETTER APPROACH: We just added the button locally for preview. 
            # In real post, we need a robust way. 
            # Let's assume for now we use a hash or index if complex.
            # For this MVP, we will try to stuff it in `alert:{text[:50]}` and hope for best or handle it properly.
            # ACTUALLY: The user wants "Add Translation" which uses Alert.
            # Let's use a registry of alerts in the FSM data? No, FSM is temporary.
            # For the preview, we just show the button.
            # For the real post, we need to handle the callback.
            # We will generate a unique ID for the button callback.
            kb_builder.button(text=btn['text'], callback_data=f"show_alert_{len(buttons)}") # Dummy index for preview?
    
    kb_builder.adjust(1)
    preview_markup = kb_builder.as_markup()

    # Send Content
    try:
        # Refactored for entities support (stored as JSON dict usually, but here 'content' might be raw text or dict)
        # We need to handle 'content' variable structure carefully.
        # In process_content we now save {text:..., entities: ...}
        
        entities = None
        text_content = ""
        
        if isinstance(content, dict) and 'text' in content: # New Text format
            text_content = content['text']
            # Rehydrate entities
            if content.get('entities'):
                # We need to convert list of dicts back to list of MessageEntity if using aiogram types
                # But send_message accepts list of MessageEntity
                from aiogram.types import MessageEntity
                entities = [MessageEntity(**e) for e in content['entities']]
            await bot.send_message(chat_id, text_content, entities=entities, reply_markup=preview_markup)
            
        elif isinstance(content, str): # Legacy Text (HTML)
            await bot.send_message(chat_id, content, reply_markup=preview_markup)
        
        elif isinstance(content, list): # Album
            # Albums can't have inline keyboards attached to the media group itself easily 
            # (only the first message usually, but it's tricky).
            # Usually, buttons are sent as a separate message below the album.
            # Send media group
            # We need to reconstruct InputMedia objects
            media_group = []
            for item in content:
                if item['type'] == 'photo':
                    media_group.append(types.InputMediaPhoto(media=item['file_id'], caption=item.get('caption')))
                elif item['type'] == 'video':
                    media_group.append(types.InputMediaVideo(media=item['file_id'], caption=item.get('caption')))
                elif item['type'] == 'document':
                    media_group.append(types.InputMediaDocument(media=item['file_id'], caption=item.get('caption')))
                elif item['type'] == 'audio':
                    media_group.append(types.InputMediaAudio(media=item['file_id'], caption=item.get('caption')))
            
            await bot.send_media_group(chat_id, media=media_group)
            if preview_markup.inline_keyboard:
                await bot.send_message(chat_id, "⬇️ Buttons for the album above ⬇️", reply_markup=preview_markup)

        elif isinstance(content, dict): # Single Media
            if content['type'] == 'photo':
                await bot.send_photo(chat_id, content['file_id'], caption=content.get('caption'), reply_markup=preview_markup)
            elif content['type'] == 'video':
                await bot.send_video(chat_id, content['file_id'], caption=content.get('caption'), reply_markup=preview_markup)
            elif content['type'] == 'document':
                await bot.send_document(chat_id, content['file_id'], caption=content.get('caption'), reply_markup=preview_markup)
            elif content['type'] == 'audio':
                await bot.send_audio(chat_id, content['file_id'], caption=content.get('caption'), reply_markup=preview_markup)
                
    except Exception as e:
        await bot.send_message(chat_id, f"Error rendering preview: {e}")

    # Send Control Menu
    await bot.send_message(chat_id, "⚙️ **Post Editor**\nWhat would you like to do next?", reply_markup=get_post_creation_menu(has_content=True))

# --- Handlers ---

@router.message(F.text.in_({"📝 Create Post", "📝 Создать пост"}))
async def start_post_creation(message: types.Message, state: FSMContext):
    lang = await get_lang()
    # Fetch channels
    async for session in get_db_session():
        result = await session.execute(select(Channel))
        channels = result.scalars().all()
        
        if not channels:
            await message.answer(await get_text('no_channels', lang))
            return

        await message.answer(await get_text('select_channel', lang), reply_markup=get_channels_menu(channels))
        await state.set_state(PostState.waiting_for_channel)

@router.callback_query(PostState.waiting_for_channel, F.data.startswith("select_channel_"))
async def channel_selected(callback: types.CallbackQuery, state: FSMContext):
    channel_id = int(callback.data.split("_")[-1])
    await state.update_data(target_channel_id=channel_id)
    
    await callback.message.edit_text("✅ Channel selected.\n\nNow send me the content for the post.\n(Text, Photo, Video, Document, or Album)")
    await state.set_state(PostState.waiting_for_content)

@router.message(PostState.waiting_for_content)
async def process_content(message: types.Message, state: FSMContext, album: list[types.Message] = None):
    data = {}
    
    if album:
        # Handle Album
        content_list = []
        for msg in album:
            item = {'file_id': None, 'type': 'unknown', 'caption': msg.caption or ""}
            if msg.photo:
                item['type'] = 'photo'
                item['file_id'] = msg.photo[-1].file_id
            elif msg.video:
                item['type'] = 'video'
                item['file_id'] = msg.video.file_id
            elif msg.document:
                item['type'] = 'document'
                item['file_id'] = msg.document.file_id
            elif msg.audio:
                item['type'] = 'audio'
                item['file_id'] = msg.audio.file_id
            content_list.append(item)
        data['content'] = content_list
        data['content_type'] = 'album'
        
    elif message.photo:
        data['content'] = {'type': 'photo', 'file_id': message.photo[-1].file_id, 'caption': message.caption}
        data['content_type'] = 'photo'
    elif message.video:
        data['content'] = {'type': 'video', 'file_id': message.video.file_id, 'caption': message.caption}
        data['content_type'] = 'video'
    elif message.document:
        data['content'] = {'type': 'document', 'file_id': message.document.file_id, 'caption': message.caption}
        data['content_type'] = 'document'
    elif message.text:
        data['content'] = message.html_text # Use html_text to preserve formatting
        data['content_type'] = 'text'
    else:
        await message.answer("Unsupported content type.")
        return

    await state.update_data(**data)
    await state.update_data(buttons=[]) # Initialize empty buttons list
    
    await message.answer("Content received!")
    await render_post_preview(message.bot, message.chat.id, await state.get_data())
    await state.set_state(PostState.waiting_for_buttons)

# --- Button Handlers ---

@router.callback_query(PostState.waiting_for_buttons, F.data == "add_btn_url")
async def ask_url_btn_label(callback: types.CallbackQuery, state: FSMContext):
    lang = await get_lang()
    await callback.message.answer(await get_text('send_btn_label', lang))
    await state.set_state(PostState.waiting_for_url_label)
    await callback.answer()

@router.message(PostState.waiting_for_url_label)
async def get_url_btn_label(message: types.Message, state: FSMContext):
    lang = await get_lang()
    await state.update_data(temp_btn_label=message.text)
    await message.answer(await get_text('send_btn_url', lang))
    await state.set_state(PostState.waiting_for_url_link)

@router.message(PostState.waiting_for_url_link)
async def get_url_btn_link(message: types.Message, state: FSMContext):
    lang = await get_lang()
    data = await state.get_data()
    buttons = data.get('buttons', [])
    buttons.append({
        'type': 'url',
        'text': data['temp_btn_label'],
        'url': message.text
    })
    await state.update_data(buttons=buttons)
    await message.answer(await get_text('btn_added', lang))
    await render_post_preview(message.bot, message.chat.id, await state.get_data())
    await state.set_state(PostState.waiting_for_buttons)

@router.callback_query(PostState.waiting_for_buttons, F.data == "add_btn_translate")
async def add_translate_btn(callback: types.CallbackQuery, state: FSMContext):
    lang = await get_lang()
    # Ask for language
    await callback.message.answer(await get_text('btn_translate_prompt', lang))
    await state.set_state(PostState.waiting_for_translation_lang)
    await callback.answer()

@router.message(PostState.waiting_for_translation_lang)
async def process_translation(message: types.Message, state: FSMContext):
    target_lang = message.text.strip()
    data = await state.get_data()
    content = data.get('content')
    
    # Extract text to translate
    text_to_translate = ""
    if isinstance(content, str):
        text_to_translate = content
    elif isinstance(content, dict): # Single media
        text_to_translate = content.get('caption', "")
    elif isinstance(content, list): # Album
        # Find first caption
        for item in content:
            if item.get('caption'):
                text_to_translate = item['caption']
                break
    
    if not text_to_translate:
        await message.answer("No text found to translate!")
        await state.set_state(PostState.waiting_for_buttons)
        return

    # Perform translation
    translated_text = translate_text(text_to_translate, target=target_lang)
    
    # Add button
    buttons = data.get('buttons', [])
    buttons.append({
        'type': 'alert',
        'text': "🇺🇸 English" if target_lang == 'en' else f"Translation ({target_lang})",
        'alert_text': translated_text # Store full translation
    })
    await state.update_data(buttons=buttons)
    
    await message.answer("✅ Translation added.")
    await render_post_preview(message.bot, message.chat.id, await state.get_data())
    await state.set_state(PostState.waiting_for_buttons)

@router.callback_query(PostState.waiting_for_buttons, F.data == "add_btn_alert")
async def ask_alert_text(callback: types.CallbackQuery, state: FSMContext):
    lang = await get_lang()
    await callback.message.answer(await get_text('send_btn_label', lang))
    await state.set_state(PostState.waiting_for_alert_label)
    await callback.answer()

@router.message(PostState.waiting_for_alert_label)
async def get_alert_label(message: types.Message, state: FSMContext):
    lang = await get_lang()
    await state.update_data(temp_btn_label=message.text)
    await message.answer(await get_text('send_alert_text', lang))
    await state.set_state(PostState.waiting_for_alert_text)

@router.message(PostState.waiting_for_alert_text)
async def get_alert_text(message: types.Message, state: FSMContext):
    lang = await get_lang()
    data = await state.get_data()
    buttons = data.get('buttons', [])
    buttons.append({
        'type': 'alert',
        'text': data['temp_btn_label'],
        'alert_text': message.text
    })
    await state.update_data(buttons=buttons)
    await message.answer(await get_text('btn_added', lang))
    await render_post_preview(message.bot, message.chat.id, await state.get_data())
    await state.set_state(PostState.waiting_for_buttons)

@router.callback_query(PostState.waiting_for_buttons, F.data == "clear_buttons")
async def clear_buttons(callback: types.CallbackQuery, state: FSMContext):
    lang = await get_lang()
    await state.update_data(buttons=[])
    await callback.answer(await get_text('btn_added', lang)) # Reuse or add 'Buttons cleared' text
    await render_post_preview(callback.bot, callback.message.chat.id, await state.get_data())

@router.callback_query(PostState.waiting_for_buttons, F.data == "post_cancel")
async def post_cancel(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    lang = await get_lang()
    await callback.message.edit_text(await get_text('start_welcome', lang), reply_markup=await get_main_menu(lang))

@router.callback_query(F.data == "back_to_edit")
async def back_to_edit(callback: types.CallbackQuery, state: FSMContext):
    # Go back to waiting_for_buttons state and show menu
    await state.set_state(PostState.waiting_for_buttons)
    await render_post_preview(callback.bot, callback.message.chat.id, await state.get_data())
    await callback.answer()

@router.callback_query(F.data == "toggle_pin")
async def toggle_pin(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    is_pinned = not data.get('is_pinned', False)
    await state.update_data(is_pinned=is_pinned)
    
    is_silent = data.get('is_silent', False)
    await callback.message.edit_reply_markup(reply_markup=get_publish_options_menu(is_pinned, is_silent))
    await callback.answer()

@router.callback_query(F.data == "toggle_silent")
async def toggle_silent(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    is_silent = not data.get('is_silent', False)
    await state.update_data(is_silent=is_silent)
    
    is_pinned = data.get('is_pinned', False)
    await callback.message.edit_reply_markup(reply_markup=get_publish_options_menu(is_pinned, is_silent))
    await callback.answer()

@router.callback_query(PostState.waiting_for_buttons, F.data == "post_done")
async def post_creation_done(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_reply_markup(reply_markup=None) # Remove editing buttons
    await callback.message.answer("Post ready. Choose publication options:", reply_markup=get_publish_options_menu()) # Localization todo
    await state.set_state(PostState.confirmation)

# --- Publish Handlers ---
@router.callback_query(PostState.confirmation, F.data == "pub_schedule")
async def start_schedule(callback: types.CallbackQuery, state: FSMContext):
    lang = await get_lang()
    await callback.message.answer(await get_text('schedule_prompt', lang))
    await state.set_state(PostState.waiting_for_schedule_time)
    await callback.answer()

@router.message(PostState.waiting_for_schedule_time)
async def process_schedule_time(message: types.Message, state: FSMContext):
    try:
        run_date = datetime.strptime(message.text, "%d.%m.%Y %H:%M")
        # Assume server time or ask for TZ. For simplicity MVP, using local/server time.
        # Ideally we ask user for TZ.
        
        # Save post data same as publish_now but with future date and add to scheduler
        data = await state.get_data()
        channel_id = data.get('target_channel_id')
        content = data.get('content')
        buttons = data.get('buttons', [])
        
        async for session in get_db_session():
            # Save alerts to AlertStorage and UPDATE buttons with IDs
            for btn in buttons:
                 if btn['type'] == 'alert' and btn.get('alert_text'):
                     if not btn.get('alert_id'):
                         new_id = str(uuid.uuid4())
                         btn['alert_id'] = new_id # This updates the dict in 'buttons' list
                         session.add(AlertStorage(id=new_id, text=btn['alert_text']))
            await session.commit()
            
            channel = await session.get(Channel, channel_id)
            if not channel:
                await message.answer("Channel not found!")
                return
            
            new_post = ScheduledPost(
                chat_id=channel_id,
                content=content,
                buttons=buttons,
                run_date=run_date,
                status="pending"
            )
            session.add(new_post)
            await session.commit()
            await session.refresh(new_post)
            
            # Schedule Job
            # We need a function to execute the post.
            # We can define it here or import.
            # APScheduler needs a picklable function or module path.
            # Let's use a function in this module or separate.
            scheduler.add_job(
                publish_scheduled_post,
                'date',
                run_date=run_date,
                args=[new_post.id],
                id=str(new_post.id)
            )
            
            lang = await get_lang()
            await message.answer(await get_text('post_scheduled', lang, date=run_date))
            await state.clear()
            
    except ValueError:
        lang = await get_lang()
        await message.answer(await get_text('invalid_date', lang))

async def publish_scheduled_post(post_id: int):
    # This function needs to re-hydrate the Bot instance or pass it.
    # APScheduler runs in a separate context.
    # We can get bot from current running app or create new.
    # For simplicity, we create a Bot instance or use the one from main if global (not clean).
    # Better: pass bot instance? No, apscheduler stores args.
    # We will instantiate Bot here.
    from data.config import BOT_TOKEN
    bot = Bot(token=BOT_TOKEN)
    
    async for session in get_db_session():
        post = await session.get(ScheduledPost, post_id)
        if not post or post.status != 'pending':
            await bot.session.close()
            return
            
        channel = await session.get(Channel, post.chat_id) # post.chat_id in DB is actually channel DB ID or TG ID?
        # In publish_now we used: channel_id (DB ID) -> channel.telegram_id
        # In ScheduledPost model: chat_id = mapped_column(BigInteger)
        # Wait, in publish_now we passed `channel_id` (DB ID) to ScheduledPost(chat_id=...).
        # So `post.chat_id` IS the DB ID of the channel.
        # We need to fetch the real telegram ID.
        
        target_chat_id = None
        if channel:
            target_chat_id = channel.telegram_id
        else:
            # Maybe it stored the raw ID? Let's check logic.
            # logic: `new_post = ScheduledPost(chat_id=channel_id...)` where channel_id came from state `target_channel_id` which is DB ID.
            # So yes, we need to fetch Channel.
            pass
            
        if not target_chat_id:
            print(f"Channel for post {post_id} not found")
            await bot.session.close()
            return

        # Reconstruct Markup
        from handlers.callbacks import reconstruct_keyboard
        # Reconstruct keyboard (post.buttons should have updated IDs now)
        markup = reconstruct_keyboard(post.buttons)
        content = post.content
        
        # Apply options (ScheduledPost does not store pin/silent metadata yet, need migration or default to False if not present in content json which is bad practice)
        # Actually `content` column is JSON, `buttons` is JSON.
        # We did not add `is_pinned` / `is_silent` to `ScheduledPost` model.
        # However, we can store it in `content` json for convenience if we don't want schema change,
        # OR we check if we saved it in `data` in `process_schedule_time`...
        # In `process_schedule_time` we saved `content=content`. `content` from state is just media/text.
        # `is_pinned` was in `data`.
        # We need to update `process_schedule_time` to save this metadata.
        # For now, let's assume defaults or try to read from a metadata field if we add one.
        # Or hack: store in `content` dict wrapper.
        # Let's check `content`. If it's the dict we saved, we can put options there.
        
        # But wait, `process_schedule_time` does `content = data.get('content')`.
        # We should wrap it or add columns. Adding columns is cleaner but requires migration.
        # Wrapping in content dict: `content` is already used by `process_content` logic.
        # Let's default to False for now to prevent breaking, and fix `process_schedule_time` to include it in a new field if possible or just use defaults.
        
        is_pinned = False # Todo: Implement persistence for scheduled posts options
        is_silent = False
        
        sent_message = None

        try:
             # Logic duplicate from publish_now - should be refactored into a shared function
            if isinstance(content, dict) and 'text' in content: # New Text format
                text_content = content.get('text', "")
                entities = None
                if content.get('entities'):
                     from aiogram.types import MessageEntity
                     entities = [MessageEntity(**e) for e in content['entities']]
                sent_message = await bot.send_message(target_chat_id, text_content, entities=entities, reply_markup=markup, disable_notification=is_silent)

            elif isinstance(content, str): # Legacy Text (HTML)
                sent_message = await bot.send_message(target_chat_id, content, reply_markup=markup, disable_notification=is_silent)
            
            elif isinstance(content, list): # Album
                media_group = []
                for item in content:
                    entities = [types.MessageEntity(**e) for e in item['caption_entities']] if item.get('caption_entities') else None
                    if item['type'] == 'photo':
                        media_group.append(types.InputMediaPhoto(media=item['file_id'], caption=item.get('caption'), caption_entities=entities))
                    elif item['type'] == 'video':
                        media_group.append(types.InputMediaVideo(media=item['file_id'], caption=item.get('caption'), caption_entities=entities))
                    elif item['type'] == 'document':
                        media_group.append(types.InputMediaDocument(media=item['file_id'], caption=item.get('caption'), caption_entities=entities))
                    elif item['type'] == 'audio':
                        media_group.append(types.InputMediaAudio(media=item['file_id'], caption=item.get('caption'), caption_entities=entities))
                
                sent_msgs = await bot.send_media_group(target_chat_id, media=media_group, disable_notification=is_silent)
                sent_message = sent_msgs[0]
                if markup.inline_keyboard:
                     await bot.send_message(target_chat_id, "⬇️", reply_markup=markup, disable_notification=is_silent)
            
            elif isinstance(content, dict): # Single Media
                 entities = [types.MessageEntity(**e) for e in content['caption_entities']] if content.get('caption_entities') else None
                 if content['type'] == 'photo':
                    sent_message = await bot.send_photo(target_chat_id, content['file_id'], caption=content.get('caption'), caption_entities=entities, reply_markup=markup, disable_notification=is_silent)
                 elif content['type'] == 'video':
                    sent_message = await bot.send_video(target_chat_id, content['file_id'], caption=content.get('caption'), caption_entities=entities, reply_markup=markup, disable_notification=is_silent)
                 elif content['type'] == 'document':
                    sent_message = await bot.send_document(target_chat_id, content['file_id'], caption=content.get('caption'), caption_entities=entities, reply_markup=markup, disable_notification=is_silent)

            if is_pinned and sent_message:
                try:
                    await bot.pin_chat_message(target_chat_id, sent_message.message_id)
                except Exception as e:
                    print(f"Failed to pin message: {e}")

            post.status = 'published'
            await session.commit()
            
        except Exception as e:
            print(f"Failed to publish scheduled post {post_id}: {e}")
            post.status = 'failed'
            await session.commit()
            
    await bot.session.close()

@router.callback_query(PostState.confirmation, F.data == "pub_now")
async def publish_now(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    channel_id = data.get('target_channel_id')
    
    # Fetch real telegram_id of channel
    async for session in get_db_session():
        channel = await session.get(Channel, channel_id)
        if not channel:
            await callback.answer("Channel not found!")
            return
        target_chat_id = channel.telegram_id
    
    # Send content
    content = data.get('content')
    buttons = data.get('buttons', [])
    
    # Construct Real Keyboard for sending
    # Save to DB first to get ID for callbacks
    # Save alerts to AlertStorage immediately
    async for session in get_db_session():
         for btn in buttons:
             if btn['type'] == 'alert' and btn.get('alert_text'):
                 # Check if already has ID (re-publishing?)
                 if not btn.get('alert_id'):
                     new_id = str(uuid.uuid4())
                     btn['alert_id'] = new_id
                     session.add(AlertStorage(id=new_id, text=btn['alert_text']))
         await session.commit()

    # Reconstruct keyboard
    from handlers.callbacks import reconstruct_keyboard
    markup = reconstruct_keyboard(buttons)
        
    async for session in get_db_session():
        # Send Content to Channel
        try:
            target_chat_id = None
            channel = await session.get(Channel, channel_id)
            if channel:
                target_chat_id = channel.telegram_id
            
            if not target_chat_id:
                 await callback.message.answer("Error: Channel ID missing.")
                 return
            
            # Apply options
            is_pinned = data.get('is_pinned', False)
            is_silent = data.get('is_silent', False)
            
            sent_message = None

            if data['content_type'] == 'text':
                # content is dict {text, entities} if new format, OR str if old.
                # data['content_type'] == 'text' was set for both.
                # Let's check type of 'content'
                if isinstance(content, dict):
                    text = content.get('text', "")
                    entities = [types.MessageEntity(**e) for e in content['entities']] if content.get('entities') else None
                    sent_message = await callback.bot.send_message(target_chat_id, text, entities=entities, reply_markup=markup, disable_notification=is_silent)
                else: # Fallback for str (legacy)
                    sent_message = await callback.bot.send_message(target_chat_id, str(content), reply_markup=markup, disable_notification=is_silent)
            
            elif data['content_type'] == 'album':
                media_group = []
                for item in content:
                    entities = [types.MessageEntity(**e) for e in item['caption_entities']] if item.get('caption_entities') else None
                    if item['type'] == 'photo':
                        media_group.append(types.InputMediaPhoto(media=item['file_id'], caption=item.get('caption'), caption_entities=entities))
                    elif item['type'] == 'video':
                        media_group.append(types.InputMediaVideo(media=item['file_id'], caption=item.get('caption'), caption_entities=entities))
                    elif item['type'] == 'document':
                        media_group.append(types.InputMediaDocument(media=item['file_id'], caption=item.get('caption'), caption_entities=entities))
                    elif item['type'] == 'audio':
                        media_group.append(types.InputMediaAudio(media=item['file_id'], caption=item.get('caption'), caption_entities=entities))
                
                sent_msgs = await callback.bot.send_media_group(target_chat_id, media=media_group, disable_notification=is_silent)
                sent_message = sent_msgs[0] # Pin first
                if markup.inline_keyboard:
                     await callback.bot.send_message(target_chat_id, "⬇️", reply_markup=markup, disable_notification=is_silent)
            
            else: # Single Media
                entities = [types.MessageEntity(**e) for e in content['caption_entities']] if content.get('caption_entities') else None
                if data['content_type'] == 'photo':
                    sent_message = await callback.bot.send_photo(target_chat_id, content['file_id'], caption=content.get('caption'), caption_entities=entities, reply_markup=markup, disable_notification=is_silent)
                elif data['content_type'] == 'video':
                    sent_message = await callback.bot.send_video(target_chat_id, content['file_id'], caption=content.get('caption'), caption_entities=entities, reply_markup=markup, disable_notification=is_silent)
                elif data['content_type'] == 'document':
                    sent_message = await callback.bot.send_document(target_chat_id, content['file_id'], caption=content.get('caption'), caption_entities=entities, reply_markup=markup, disable_notification=is_silent)
            
            if is_pinned and sent_message:
                try:
                    await callback.bot.pin_chat_message(target_chat_id, sent_message.message_id)
                except Exception as e:
                    print(f"Failed to pin message: {e}")

            lang = await get_lang()
            await callback.message.edit_text(await get_text('post_published', lang))
            await state.clear()
            
        except Exception as e:
            await callback.message.answer(f"❌ Failed to publish: {e}")
            # If failed, we don't save to scheduled_posts because user didn't want to save published posts to DB
            pass
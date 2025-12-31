from aiogram.fsm.state import State, StatesGroup

class PostState(StatesGroup):
    waiting_for_channel = State()
    waiting_for_content = State()
    waiting_for_buttons = State()
    
    # Sub-states for adding specific buttons
    waiting_for_url_label = State()
    waiting_for_url_link = State()
    
    waiting_for_alert_label = State()
    waiting_for_alert_text = State()
    
    waiting_for_webapp_label = State()
    waiting_for_webapp_url = State()
    
    waiting_for_translation_lang = State()

    confirmation = State()
    
    # Scheduling
    waiting_for_timezone = State()
    waiting_for_schedule_time = State()

class ChannelState(StatesGroup):
    waiting_for_channel_forward = State()
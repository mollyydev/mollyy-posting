from sqlalchemy import BigInteger, String, Integer, DateTime, JSON, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from database.db import Base
from datetime import datetime

class Channel(Base):
    __tablename__ = 'channels'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    title: Mapped[str] = mapped_column(String)
    added_by: Mapped[int] = mapped_column(BigInteger)

class Settings(Base):
    __tablename__ = 'bot_settings'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    access_denied_text: Mapped[str] = mapped_column(String, default="Access Denied.")
    language: Mapped[str] = mapped_column(String, default="ru") # Added language

class ScheduledPost(Base):
    __tablename__ = 'scheduled_posts'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    chat_id: Mapped[int] = mapped_column(BigInteger)
    # content will store JSON: {'text': ..., 'entities': [...], 'media': [...]}
    content: Mapped[dict] = mapped_column(JSON) 
    buttons: Mapped[list] = mapped_column(JSON)
    run_date: Mapped[datetime] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String, default="pending") 
    is_pinned: Mapped[bool] = mapped_column(Boolean, default=False)
    is_silent: Mapped[bool] = mapped_column(Boolean, default=False)

class AlertStorage(Base):
    """Stores text for alert buttons to handle callback data limits."""
    __tablename__ = 'alert_storage'

    id: Mapped[str] = mapped_column(String, primary_key=True) # UUID
    text: Mapped[str] = mapped_column(String)
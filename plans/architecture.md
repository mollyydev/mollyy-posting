# Mollyy Posting Bot Architecture

## 1. Technology Stack
- **Framework**: `aiogram` (v3.x) - Modern asynchronous Telegram Bot API framework.
- **Database**: `SQLAlchemy` (Async) + `aiosqlite` - ORM for SQLite database.
- **Scheduling**: `APScheduler` - For scheduling posts at specific times.
- **Translation**: `deep-translator` (or `googletrans` fallback) - For the "Translate to English" feature.
- **Environment**: `python-dotenv` - Managing secrets.

## 2. Database Schema (SQLite)

### Table: `channels`
Stores connected channels managed by the bot.
- `id` (Integer, Primary Key): Database ID.
- `telegram_id` (BigInteger, Unique): The actual Telegram ID of the channel (e.g., -100...).
- `title` (String): Channel title for display in menus.
- `added_by` (BigInteger): ID of the admin who added it.

### Table: `scheduled_posts`
Stores metadata for posts scheduled for the future (useful for listing/canceling).
- `id` (Integer, Primary Key).
- `chat_id` (BigInteger): Target channel ID.
- `content` (JSON/Text): Serialized content ID (file_id) or text.
- `buttons` (JSON): Serialized inline keyboard structure.
- `run_date` (DateTime): When it should be posted.
- `status` (String): 'pending', 'published', 'failed'.

### Table: `bot_settings`
Global settings (single row usually).
- `id` (Integer, PK).
- `access_denied_text` (String): Text shown to non-admin users.

## 3. Bot Structure & Logic

### Middleware
1.  **`AdminMiddleware`**: Intercepts every update. Checks `event.from_user.id` against a list of `ADMIN_IDS` in `.env`.
    - If User NOT Admin: Sends the configured "Access Denied" message from DB. Stops propagation.
    - If User IS Admin: Passes update to handlers.
2.  **`AlbumMiddleware`**: Collects `message` updates that are part of a `MediaGroup` (album) into a single event list to handle albums as one unit (crucial for "Attach any file").

### Finite State Machine (FSM) States
- **`PostState`**:
    - `waiting_for_channel`: Admin selecting which channel to post to.
    - `waiting_for_content`: Admin sending text/photo/video/file/album.
    - `waiting_for_buttons`: Admin adding buttons (loop).
    - `waiting_for_button_details`: Inputting URL, Alert Text, or WebApp URL.
    - `waiting_for_translation_lang`: Selecting language for auto-translation button.
    - `confirmation`: Reviewing the post preview.
    - `waiting_for_time`: Inputting schedule time (if not publishing immediately).

### Key Workflows

#### A. Post Creation
1.  Admin selects channel.
2.  Admin sends content.
    - *Logic*: If text, save text. If media, save `file_id` + caption. If album, save list of `file_ids` + caption. Preserve `MessageEntity` (bold, italic, links) explicitly.
3.  Bot sends "Post Preview" and a control keyboard:
    - [Add URL Button]
    - [Add Alert Button] (Pop-up text)
    - [Add WebApp Button]
    - [Add Translation 🇺🇸]
    - [Done / Publish Settings]

#### B. Button: Translation
1.  Admin clicks "Add Translation".
2.  Bot asks for language (e.g., "English").
3.  Bot uses Google Translate API to translate the current post's text/caption.
4.  Bot saves this text.
5.  A new button "🇺🇸 English" is added to the post.
    - *Action*: When a user in the channel clicks this, `callback_query` triggers.
    - *Response*: `answer_callback_query(..., show_alert=True)` displaying the translated text.
    - *Constraint*: Alerts have a 200-char limit. If translation > 200 chars, we might need to send a temporary message or trim it. *Correction based on user request*: User asked for "separate window" (Alert) but acknowledged limit? The prompt says "Alert". If > 200 chars, we will truncate with "..." or use `show_alert=True` strictly.

#### C. Scheduling
1.  Admin selects "Schedule".
2.  Bot asks "Timezone?" (Default to Server or User selection).
3.  Bot asks "Date/Time?" (Format: `DD.MM HH:MM`).
4.  Bot calculates delta, adds job to `APScheduler`.
5.  Job triggers `send_message` / `copy_message` at target time.

### Project Structure
```
mollyy-posting/
├── .env                # Secrets
├── main.py             # Entry point
├── config.py           # Configuration loader
├── database/
│   ├── models.py       # SQLAlchemy models
│   └── db.py           # Engine setup
├── middlewares/
│   ├── admin.py
│   └── album.py
├── handlers/
│   ├── base.py         # Start, Help, Channel Management
│   ├── posting.py      # Post creation flow
│   └── callbacks.py    # Button interactions (public & admin)
├── utils/
│   ├── translator.py   # Translation logic
│   └── scheduler.py    # APScheduler wrappers
└── plans/              # Documentation
# Mollyy Posting Bot

A powerful Telegram bot for managing channel posts with advanced features like button management, scheduling, translation, and admin control.

## Features

- **Post Creation**: Support for Text, Photos, Videos, Documents, and **Media Albums**.
- **Button Management**: Add URL buttons, WebApp buttons, and custom Alert buttons.
- **Auto-Translation**: One-click "🇺🇸 English" button that adds an alert with the translated text.
- **Scheduling**: Schedule posts for the future with timezone support.
- **Channel Management**: Easily add and manage multiple channels.
- **Admin Security**: Access restricted to configured admin IDs with customizable "Access Denied" messages.

## Installation

1.  **Clone the repository**:
    ```bash
    git clone <repository_url>
    cd mollyy-posting
    ```

2.  **Create a virtual environment**:
    ```bash
    python -m venv .venv
    # Windows
    .venv\Scripts\activate
    # Linux/Mac
    source .venv/bin/activate
    ```

3.  **Install dependencies**:
    ```bash
    pip install -r requirements.txt
    ```


4.  **Configuration**:
    - Rename `data/.env.example` to `data/.env`.
    - Edit `data/.env` and fill in your `BOT_TOKEN` and `ADMIN_IDS`.

5.  **Database Setup**:
    - Run migrations to create the database:
    ```bash
    alembic upgrade head
    ```

6.  **Run the Bot**:
    ```bash
    python main.py
    ```

## Usage

1.  Start the bot with `/start`.
2.  Go to **📢 Channels** and click **➕ Add Channel**. Forward a message from your channel to the bot (Bot must be an admin in the channel).
3.  Go to **📝 Create Post**, select a channel, and send your content.
4.  Add buttons or translation as needed.
5.  Publish immediately or schedule for later.

## Project Structure

- `data/`: Configuration and Database file.
- `database/`: Database models and connection logic.
- `handlers/`: Bot command and event handlers.
- `middlewares/`: Admin check and Album handling middleware.
- `utils/`: Helper functions (Scheduler, Translator, Keyboards).
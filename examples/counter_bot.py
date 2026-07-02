# Counter Bot Example
# This bot counts messages and replies with the current count.
# First message -> "1", second -> "2", and so on.
# Run: PYTHONPATH=src python examples/counter_bot.py

import os
import sys
from pathlib import Path

from telegram import Update
from telegram.ext import ContextTypes, MessageHandler, filters

# Add src/ to Python path so we can import telegram_bot package
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from telegram_bot.bot import build_application
from telegram_bot.config import load_settings


async def count_messages(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler that counts messages and replies with the current count."""
    message = update.message
    # Guard: ignore updates that don't contain a text message
    if message is None or message.text is None:
        return

    # Initialize counter on first run (bot_data persists across updates in a session)
    if "message_count" not in context.bot_data:
        context.bot_data["message_count"] = 0

    # Increment and retrieve the current count
    context.bot_data["message_count"] += 1
    count = context.bot_data["message_count"]

    # Reply with the count as a string
    await message.reply_text(str(count))


def main() -> None:
    """Set up and run the bot using long-polling."""
    # Load BOT_TOKEN and other settings from .env file
    settings = load_settings()
    # Build the application with default handlers (start, help) from bot.py
    application = build_application(settings)
    # Register counter handler: triggers on text messages that are NOT commands
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, count_messages))
    # Start receiving updates via Telegram's long-polling API
    application.run_polling()


if __name__ == "__main__":
    main()

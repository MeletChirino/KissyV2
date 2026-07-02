# Echo Bot Example
# This bot simply echoes back any text message it receives.
# Run: PYTHONPATH=src python examples/echo_bot.py

import os
import sys
from pathlib import Path

from telegram import Update
from telegram.ext import ContextTypes, MessageHandler, filters

# Add src/ to Python path so we can import telegram_bot package
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from telegram_bot.bot import build_application
from telegram_bot.config import load_settings


async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler that echoes received text messages back to the user."""
    message = update.message
    # Guard: ignore updates that don't contain a text message
    if message is None or message.text is None:
        return
    # Reply with the same text the user sent
    await message.reply_text(message.text)


def main() -> None:
    """Set up and run the bot using webhooks."""
    # Load BOT_TOKEN and other settings from .env file
    settings = load_settings()
    # Build the application with default handlers (start, help) from bot.py
    application = build_application(settings)
    # Register echo handler: triggers on text messages that are NOT commands
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))
    # Start receiving updates via Telegram's webhook (requires HTTPS in production)
    application.run_webhook(
        listen=settings.webhook_listen,
        port=settings.webhook_port,
        url_path=settings.bot_token,
        webhook_url=f"{settings.webhook_url}/{settings.bot_token}",
        secret_token=settings.webhook_secret_token,
    )


if __name__ == "__main__":
    main()

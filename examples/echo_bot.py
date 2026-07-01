import os
import sys
from pathlib import Path

from telegram import Update
from telegram.ext import ContextTypes, MessageHandler, filters

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from telegram_bot.bot import build_application
from telegram_bot.config import load_settings


async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.message
    if message is None or message.text is None:
        return
    await message.reply_text(message.text)


def main() -> None:
    settings = load_settings()
    application = build_application(settings)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))
    application.run_polling()


if __name__ == "__main__":
    main()


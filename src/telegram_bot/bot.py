from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from telegram_bot.config import Settings, load_settings

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    if message is None:
        return
    await message.reply_text("Hello! Send /help to see what I do.")


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    if message is None:
        return
    await message.reply_text("/start - greet the bot\n/help - this message")


async def post_shutdown(application: Application) -> None:
    try:
        await application.bot.delete_webhook()
    except Exception:
        logger.exception("Failed to delete webhook on shutdown")
    else:
        logger.info("Webhook removed")


def build_application(settings: Settings) -> Application:
    application = (
        Application.builder()
        .token(settings.bot_token)
        .post_shutdown(post_shutdown)
        .build()
    )
    application.bot_data["settings"] = settings
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_cmd))
    return application


def main() -> None:
    settings = load_settings()
    application = build_application(settings)
    application.run_webhook(
        listen=settings.webhook_listen,
        port=settings.webhook_port,
        url_path=settings.bot_token,
        webhook_url=f"{settings.webhook_url}/{settings.bot_token}",
        secret_token=settings.webhook_secret_token,
    )

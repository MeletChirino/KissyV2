# Ollama Bot Example
# ===================
# This example wires a Telegram bot (running via webhook) to a local
# Ollama server. The flow is:
#
#   1. Telegram delivers an incoming message to our webhook endpoint.
#   2. The bot shows a "typing..." indicator so the user sees feedback
#      while the LLM thinks.
#   3. The bot forwards the user's text to Ollama's /api/chat endpoint
#      via the OllamaClient in src/ollama/__init__.py.
#   4. The model's reply is sent back to the same Telegram chat.
#
# Required environment variables (see .env / .env.example):
#   BOT_TOKEN          - token from @BotFather
#   WEBHOOK_URL        - public HTTPS URL Telegram can POST updates to
#   WEBHOOK_LISTEN     - interface to bind (default 0.0.0.0)
#   WEBHOOK_PORT       - port to listen on (default 8443)
#   WEBHOOK_SECRET_TOKEN - optional shared secret for the webhook
#   OLLAMA_HOST        - e.g. 127.0.0.1:11434 (no scheme, no trailing slash)
#   OLLAMA_MODEL       - e.g. llama3.2 (must be pulled on the server first)
#
# Run:
#   PYTHONPATH=src python examples/ollama_bot.py

import asyncio  # For offloading blocking I/O to a worker thread.
import json  # json.JSONDecodeError is one of the failures we report back.
import logging  # Standard logging; telegram.ext also uses this.
import os  # Reads OLLAMA_HOST / OLLAMA_MODEL from the environment.
import sys  # Used to add src/ to sys.path below.
import urllib.error  # URLError is raised when Ollama is unreachable.
from pathlib import Path  # Used to build the src/ import path portably.

from telegram import Update  # The Telegram Update object passed to handlers.
from telegram.constants import ChatAction  # "typing" indicator enum value.
from telegram.ext import (  # PTB building blocks.
    ContextTypes,
    MessageHandler,
    filters,
)

# Make `from ollama import ...` and `from telegram_bot import ...` work
# without installing the project as a package. Mirrors the layout used
# by examples/echo_bot.py.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ollama import OllamaClient, OllamaError  # Our thin Ollama HTTP client.
from telegram_bot.bot import build_application  # Default Application builder.
from telegram_bot.config import load_settings  # Loads .env into a Settings object.

# Configure root logging. python-telegram-bot also logs to this logger.
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Persona injected as the first message of every Ollama conversation.
# Ollama treats the "system" role as instructions that frame every reply.
SYSTEM_PROMPT = (
    "You are an assistant at a brodery house. USER is your master. "
    "Say Hi to the user very loud anthusiastic way"
)


def build_messages(prompt: str) -> list[dict[str, str]]:
    """Assemble the messages array sent to Ollama.

    Ollama's /api/chat endpoint expects an ordered list of role/content
    pairs. We always prepend the system prompt so the model keeps its
    persona across turns.
    """
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]


async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler attached to every non-command text message.

    Telegram invokes this coroutine for each update that matches the
    MessageHandler filter registered in main().
    """
    # update.message may be None for edited messages, channel posts, etc.
    # Only reply to user text messages with actual content.
    message = update.message
    if message is None or not message.text:
        return

    # Pull the shared OllamaClient out of bot_data. We stored it there
    # in main() so every handler reuses the same connection settings
    # (host, model, timeout) without re-reading env vars per message.
    ollama: OllamaClient | None = context.application.bot_data.get("ollama")
    if ollama is None:
        await message.reply_text("Ollama client not initialized.")
        return

    # Show the "typing..." indicator in the chat. This expires after ~5s
    # automatically; for long generations we'd need to refresh it.
    await message.chat.send_action(ChatAction.TYPING)

    # OllamaClient.chat() is a blocking HTTP call (urllib). Running it
    # directly would stall PTB's asyncio event loop, so we dispatch it
    # to a worker thread via asyncio.to_thread.
    try:
        answer = await asyncio.to_thread(
            ollama.chat, build_messages(message.text)
        )
    except urllib.error.URLError as exc:
        # Connection refused, DNS failure, timeout from urllib, etc.
        logger.exception("Ollama request failed")
        await message.reply_text(f"Ollama unreachable: {exc.reason}")
        return
    except (json.JSONDecodeError, KeyError, OllamaError) as exc:
        # Ollama returned something we couldn't parse, or the message
        # field was empty. Surface a short message to the user and log
        # the full traceback server-side.
        logger.exception("Ollama returned an unexpected response")
        await message.reply_text(f"Ollama error: {exc}")
        return
    except TimeoutError:
        # asyncio.to_thread surfaces socket timeouts as TimeoutError.
        await message.reply_text("Ollama timed out.")
        return

    # Telegram caps a single text message at 4096 characters. If the
    # model's reply fits, send it as one message; otherwise chunk it
    # into consecutive reply_text() calls (no overlap, no slicing bugs).
    if len(answer) <= 4096:
        await message.reply_text(answer)
        return

    for chunk in [answer[i : i + 4096] for i in range(0, len(answer), 4096)]:
        await message.reply_text(chunk)


def main() -> None:
    """Entry point: load config, build the bot, start the webhook."""
    # load_settings() reads BOT_TOKEN / WEBHOOK_* from .env (via dotenv).
    settings = load_settings()

    # build_application() returns an Application with the default
    # /start and /help command handlers already registered. See
    # src/telegram_bot/bot.py for details.
    application = build_application(settings)

    # Read Ollama config from the environment and build the shared
    # client. We fail fast here (before the webhook is registered) so
    # misconfiguration is obvious in the logs.
    host = os.getenv("OLLAMA_HOST")
    model = os.getenv("OLLAMA_MODEL")
    if not host or not model:
        raise SystemExit("OLLAMA_HOST and OLLAMA_MODEL must be set in .env")
    application.bot_data["ollama"] = OllamaClient(host=host, model=model)

    # Register our chat handler. filters.TEXT matches any text message;
    # ~filters.COMMAND excludes /foo messages so /start and /help from
    # build_application() keep working.
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, chat)
    )

    # Start the webhook server. Telegram will POST updates to
    # {webhook_url}/{bot_token}, and we serve them on
    # {webhook_listen}:{webhook_port}/{bot_token}. The optional
    # secret_token is checked via the X-Telegram-Bot-Api-Secret-Token
    # header when Telegram sends updates.
    application.run_webhook(
        listen=settings.webhook_listen,
        port=settings.webhook_port,
        url_path=settings.bot_token,
        webhook_url=f"{settings.webhook_url}/{settings.bot_token}",
        secret_token=settings.webhook_secret_token,
    )


if __name__ == "__main__":
    main()

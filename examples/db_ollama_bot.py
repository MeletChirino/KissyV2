# Ollama + Database Bot Example
# =============================
# Wires a Telegram bot (webhook) to a local Ollama server, with full
# per-chat conversation history persisted to SQLite.
#
# Flow per incoming text message in a given chat:
#
#   1. If there is no active row for this chat_id, insert one with
#      status=1 and an empty transcript. Otherwise load the existing
#      active row.
#   2. Send the transcript + the new user message to Ollama's /api/chat
#      endpoint (sliding window if the transcript has grown past the
#      OLLAMA_CONTEXT_CHARS budget).
#   3. Append "USER: ...\n\nSYSTEM: ...\n\n" to the row's conversation
#      field so the next turn can resume from the same transcript.
#   4. Reply to Telegram with the model's answer.
#
# Conversation control commands:
#
#   /exit  - close the current active row (status=0) and say goodbye.
#   /new   - same as /exit, but explicitly framed as "start a new
#            conversation next message" (semantics identical today;
#            kept distinct so future state can diverge).
#
# Required environment variables (see .env / .env.example):
#   BOT_TOKEN            - token from @BotFather
#   WEBHOOK_URL          - public HTTPS URL Telegram can POST updates to
#   WEBHOOK_LISTEN       - interface to bind (default 0.0.0.0)
#   WEBHOOK_PORT         - port to listen on (default 8443)
#   WEBHOOK_SECRET_TOKEN - optional shared secret for the webhook
#   OLLAMA_HOST          - e.g. 127.0.0.1:11434 (no scheme, no slash)
#   OLLAMA_MODEL         - e.g. llama3.2 (must be pulled on the server)
#
# Optional:
#   CONVERSATIONS_DB     - path to the SQLite file
#                          (default: data/conversations.db)
#   OLLAMA_CONTEXT_CHARS - approximate per-request transcript budget
#                          sent to Ollama; older turns are dropped when
#                          the transcript exceeds this size (default 8000)
#
# Run:
#   PYTHONPATH=src python examples/db_ollama_bot.py

import asyncio
import json
import logging
import os
import sys
import urllib.error
from pathlib import Path

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# Make `from telegram_bot import ...` work without installing the project.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ollama import OllamaClient, OllamaError  # noqa: E402
from telegram_bot.bot import build_application  # noqa: E402
from telegram_bot.config import load_settings  # noqa: E402
from telegram_bot import db  # noqa: E402

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are a helpful assistant. Keep replies concise."
)

# Separator between transcript turns. The DB stores turns using
# "USER:...\n\nSYSTEM:...\n\n"; the same markers are used to split
# turns back out when building the Ollama request.
TURN_SEPARATOR = "\n\n"

# Cap on how much of the stored transcript is sent back to Ollama.
# We always send the *tail* of the transcript so the most recent context
# is preserved. Persistence is lossless — the full transcript stays in
# the row even when we trim for the model.
DEFAULT_CONTEXT_CHARS = 8000


def build_messages(transcript: str, new_user_text: str, context_chars: int) -> list[dict[str, str]]:
    """Assemble the messages array sent to Ollama.

    The system prompt is always first. The stored transcript is parsed
    back into alternating USER/SYSTEM turns; if it doesn't fit in
    ``context_chars`` we keep only the tail. Finally the current user
    message is appended.
    """
    messages: list[dict[str, str]] = [{"role": "system", "content": SYSTEM_PROMPT}]

    history = parse_transcript(transcript)
    if context_chars and len(transcript) > context_chars:
        history = trim_to_budget(history, context_chars)

    for role, content in history:
        messages.append({"role": role, "content": content})

    messages.append({"role": "user", "content": new_user_text})
    return messages


def parse_transcript(transcript: str) -> list[tuple[str, str]]:
    """Parse the stored transcript back into (role, content) pairs.

    The DB stores turns as "USER:foo\n\nSYSTEM:bar\n\n" repeated. We
    split on that pattern and recover the role from the prefix. Content
    may contain newlines — they are preserved.
    """
    if not transcript:
        return []

    turns: list[tuple[str, str]] = []
    chunks = transcript.split(TURN_SEPARATOR)
    for chunk in chunks:
        if not chunk:
            continue
        head, sep, rest = chunk.partition(":")
        if not sep:
            continue
        role = {"USER": "user", "SYSTEM": "assistant"}.get(head.strip().upper())
        if role is None:
            continue
        turns.append((role, rest))
    return turns


def trim_to_budget(turns: list[tuple[str, str]], budget: int) -> list[tuple[str, str]]:
    """Drop oldest turns until the joined transcript fits in ``budget``.

    Always returns at least the most recent turn, even if it alone
    exceeds the budget — better to send something than to error out.
    """
    while len(turns) > 1:
        joined_len = sum(len(c) + len(role) + 2 for role, c in turns)
        if joined_len <= budget:
            break
        turns.pop(0)
    return turns


def get_active_row_id(context: ContextTypes.DEFAULT_TYPE, chat_id: int) -> int:
    """Return the active row id for ``chat_id``, caching it in bot_data.

    The bot runs as a single process; multiple chats arriving in quick
    succession would each do a SELECT, but for clarity we resolve the
    row id on first use and store it in ``chat_data`` keyed by chat id.
    """
    cache: dict[int, int] = context.application.bot_data.setdefault("active_rows", {})
    if chat_id in cache:
        return cache[chat_id]

    db_path = context.application.bot_data["db_path"]
    row = db.get_active(db_path, chat_id)
    if row is None:
        cache[chat_id] = db.create_active(db_path, chat_id)
    else:
        cache[chat_id] = int(row["id"])
    return cache[chat_id]


def forget_active_row(context: ContextTypes.DEFAULT_TYPE, chat_id: int) -> None:
    cache: dict[int, int] = context.application.bot_data.setdefault("active_rows", {})
    cache.pop(chat_id, None)


async def end_conversation(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    farewell: str,
) -> None:
    """Close the active row for this chat and reply with a farewell."""
    message = update.effective_message
    if message is None:
        return
    chat = update.effective_chat
    if chat is None:
        return
    chat_id = chat.id

    db_path = context.application.bot_data["db_path"]
    row = db.get_active(db_path, chat_id)
    if row is not None:
        db.close_active(db_path, int(row["id"]))
    forget_active_row(context, chat_id)
    await message.reply_text(farewell)


async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    if message is None:
        return
    await message.reply_text(
        "Hi! Send any message to start a conversation. "
        "Use /exit or /new to end it."
    )


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    if message is None:
        return
    await message.reply_text(
        "/start - greet the bot\n"
        "/help  - this message\n"
        "/exit  - end the current conversation\n"
        "/new   - end the current conversation (start fresh next time)\n\n"
        "Anything else is sent to Ollama and the reply is stored."
    )


async def exit_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await end_conversation(update, context, "Goodbye! Conversation closed.")


async def new_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await end_conversation(update, context, "Conversation closed. Send a new message to start fresh.")


async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle a regular text message: persist, call Ollama, reply."""
    message = update.message
    if message is None or not message.text:
        return
    chat = update.effective_chat
    if chat is None:
        return

    ollama: OllamaClient | None = context.application.bot_data.get("ollama")
    if ollama is None:
        await message.reply_text("Ollama client not initialized.")
        return
    db_path: str = context.application.bot_data["db_path"]
    context_chars: int = context.application.bot_data["context_chars"]

    row_id = get_active_row_id(context, chat.id)
    transcript = db.get_transcript(db_path, row_id)

    await message.chat.send_action(ChatAction.TYPING)

    try:
        answer = await asyncio.to_thread(
            ollama.chat,
            build_messages(transcript, message.text, context_chars),
        )
    except urllib.error.URLError as exc:
        logger.exception("Ollama request failed")
        await message.reply_text(f"Ollama unreachable: {exc.reason}")
        return
    except (json.JSONDecodeError, KeyError, OllamaError) as exc:
        logger.exception("Ollama returned an unexpected response")
        await message.reply_text(f"Ollama error: {exc}")
        return
    except TimeoutError:
        await message.reply_text("Ollama timed out.")
        return

    db.append_turn(db_path, row_id, message.text, answer)

    if len(answer) <= 4096:
        await message.reply_text(answer)
        return
    for chunk in [answer[i : i + 4096] for i in range(0, len(answer), 4096)]:
        await message.reply_text(chunk)


def main() -> None:
    settings = load_settings()

    # Build the default application (registers /start, /help) and then
    # override /start and /help with versions that mention /exit and /new.
    application = build_application(settings)
    application.add_handler(CommandHandler("start", start_cmd))
    application.add_handler(CommandHandler("help", help_cmd))
    application.add_handler(CommandHandler("exit", exit_cmd))
    application.add_handler(CommandHandler("new", new_cmd))

    host = os.getenv("OLLAMA_HOST")
    model = os.getenv("OLLAMA_MODEL")
    if not host or not model:
        raise SystemExit("OLLAMA_HOST and OLLAMA_MODEL must be set in .env")

    db_path = db.resolve_db_path()
    db.ensure_schema(db_path)

    application.bot_data["ollama"] = OllamaClient(host=host, model=model)
    application.bot_data["db_path"] = str(db_path)
    application.bot_data["context_chars"] = int(
        os.getenv("OLLAMA_CONTEXT_CHARS", str(DEFAULT_CONTEXT_CHARS))
    )

    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, chat)
    )

    application.run_webhook(
        listen=settings.webhook_listen,
        port=settings.webhook_port,
        url_path=settings.bot_token,
        webhook_url=f"{settings.webhook_url}/{settings.bot_token}",
        secret_token=settings.webhook_secret_token,
    )


if __name__ == "__main__":
    main()

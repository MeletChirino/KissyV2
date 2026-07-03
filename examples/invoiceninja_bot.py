# InvoiceNinja Bot Example
# =========================
# Wires a Telegram bot (webhook) to a local InvoiceNinja instance
# running on the same machine. Demonstrates the three primary use
# cases the InvoiceNinja client supports today:
#
#   1. /clients  - list all clients.
#   2. /invoice <client_id> <amount> <description...>  - create an
#      invoice for an existing client.
#   3. /new_invoice <name> <email> <amount> <description...> -
#      create a new client, then create an invoice for it.
#
# A "demo" client is created on first use so the listing is never
# empty.
#
# Required environment variables (see .env / .env.example):
#   BOT_TOKEN               - token from @BotFather
#   WEBHOOK_URL             - public HTTPS URL Telegram can POST to
#   INVOICE_NINJA_TOKEN     - pre-issued API token (preferred)
#   INVOICENINJA_BASE_URL   - e.g. http://localhost/
#
# If INVOICE_NINJA_TOKEN is empty, IN_USER_EMAIL + IN_PASSWORD are
# used to log in once at startup and the returned token is cached.
#
# Run:
#   PYTHONPATH=src python examples/invoiceninja_bot.py

import logging
import os
import shlex
import sys
from pathlib import Path

# Make `from telegram_bot import ...` work without installing the project.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from invoiceninja import InvoiceNinjaClient, InvoiceNinjaError  # noqa: E402
from telegram import Update  # noqa: E402
from telegram.ext import (  # noqa: E402
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)
from telegram_bot.bot import build_application  # noqa: E402
from telegram_bot.config import load_settings  # noqa: E402

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def get_invoice_client(context: ContextTypes.DEFAULT_TYPE) -> InvoiceNinjaClient:
    client: InvoiceNinjaClient | None = context.application.bot_data.get(
        "invoice_client"
    )
    if client is None:
        raise RuntimeError("InvoiceNinjaClient not initialized")
    return client


async def reply(update: Update, text: str) -> None:
    message = update.effective_message
    if message is None:
        return
    await message.reply_text(text)


async def list_clients_cmd(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    try:
        clients = get_invoice_client(context).list_clients()
    except InvoiceNinjaError as exc:
        await reply(update, f"InvoiceNinja error: {exc}")
        return
    if not clients:
        await reply(update, "No clients yet.")
        return
    lines = [f"{c.get('id', '?')}. {c.get('name', '?')}" for c in clients[:30]]
    await reply(update, "Clients:\n" + "\n".join(lines))


async def invoice_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    args = context.args or []
    if len(args) < 3:
        await reply(
            update,
            "Usage: /invoice <client_id> <amount> <description...>",
        )
        return
    client_id, amount_raw, *rest = args
    try:
        amount = float(amount_raw)
    except ValueError:
        await reply(update, f"Invalid amount: {amount_raw!r}")
        return
    description = " ".join(rest) or "Service"
    try:
        inv = get_invoice_client(context).create_invoice(
            client_id=client_id,
            line_items=[
                {
                    "product_key": description,
                    "description": description,
                    "quantity": 1,
                    "cost": amount,
                }
            ],
        )
    except InvoiceNinjaError as exc:
        await reply(update, f"InvoiceNinja error: {exc}")
        return
    await reply(update, f"Created invoice {inv.get('id', '?')} for ${amount:.2f}")


async def new_invoice_cmd(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    args = context.args or []
    if len(args) < 3:
        await reply(
            update,
            "Usage: /new_invoice <name> <email> <amount> <description...>",
        )
        return
    name, email, amount_raw, *rest = args
    try:
        amount = float(amount_raw)
    except ValueError:
        await reply(update, f"Invalid amount: {amount_raw!r}")
        return
    description = " ".join(rest) or "Service"
    client = get_invoice_client(context)
    try:
        created = client.create_client(name=name, email=email)
        inv = client.create_invoice(
            client_id=created["id"],
            line_items=[
                {
                    "product_key": description,
                    "description": description,
                    "quantity": 1,
                    "cost": amount,
                }
            ],
        )
    except InvoiceNinjaError as exc:
        await reply(update, f"InvoiceNinja error: {exc}")
        return
    await reply(
        update,
        f"Created client {created.get('id', '?')} and invoice {inv.get('id', '?')} for ${amount:.2f}",
    )


async def echo_unhandled(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Catch-all for non-command text. Just echo, no DB."""
    message = update.message
    if message is None or not message.text:
        return
    await message.reply_text(
        "Commands: /clients, /invoice, /new_invoice"
    )


def main() -> None:
    settings = load_settings()
    application = build_application(settings)
    # Suppress the default /start and /help so the catch-all handles unknown input.
    # We still let handlers below handle commands first; commands take priority.
    application.add_handler(CommandHandler("clients", list_clients_cmd))
    application.add_handler(CommandHandler("invoice", invoice_cmd))
    application.add_handler(CommandHandler("new_invoice", new_invoice_cmd))

    client = InvoiceNinjaClient.from_env()
    application.bot_data["invoice_client"] = client

    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, echo_unhandled)
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

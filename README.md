# KISSY v2

Telegram bot built with python-telegram-bot.

## Setup

```bash
scripts/setup.sh
```

This creates `.venv` and `.env`, installs dependencies.

Edit `.env` with your values:

- `BOT_TOKEN` — from @BotFather
- `WEBHOOK_URL` — public HTTPS base URL (e.g. `https://your-domain.com`)

## Run

```bash
PYTHONPATH=src python -m telegram_bot
```

The bot listens on `WEBHOOK_LISTEN:WEBHOOK_PORT` (default `0.0.0.0:8443`).

## Examples

```bash
# Echo bot - replies with the same text
PYTHONPATH=src python examples/echo_bot.py

# Counter bot - replies with message count
PYTHONPATH=src python examples/counter_bot.py
```

## Troubleshooting

### Webhook returns 404 Not Found

Check webhook status:

```bash
curl -s "https://api.telegram.org/bot<BOT_TOKEN>/getWebhookInfo"
```

If `last_error_message` shows `404 Not Found`:

1. Make sure the bot is running and listening on the configured port
2. Verify the port is reachable from your reverse proxy or the internet
3. Check firewall rules — port 8443 (or your configured port) must be open

### Webhook not responding immediately

After starting the bot, **wait 1-2 minutes** for Telegram to deliver updates. Webhook registration is not instant — Telegram may take time to start sending updates to your endpoint.

### Common environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `BOT_TOKEN` | (required) | Token from @BotFather |
| `WEBHOOK_URL` | (required) | Public HTTPS base URL |
| `WEBHOOK_LISTEN` | `0.0.0.0` | Interface to bind |
| `WEBHOOK_PORT` | `8443` | Port to listen on |
| `WEBHOOK_SECRET_TOKEN` | (empty) | Optional request validation token |

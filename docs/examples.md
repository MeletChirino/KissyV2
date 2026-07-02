# Examples

Runnable demonstrations in `examples/`. Every entry point assumes:

- `scripts/setup.sh` has been run so `.venv` and `.env` exist.
- You launch from the repo root with `PYTHONPATH=src` so the `src/`
  layout is importable without an editable install.

Unless stated otherwise, every example needs `BOT_TOKEN` (and most also
need `WEBHOOK_URL`) in `.env`.

| File | What it does | Transport | DB? |
| --- | --- | --- | --- |
| [`echo_bot.py`](#echo_botpy) | Replies to any non-command text with the same text. | Webhook | No |
| [`counter_bot.py`](#counter_botpy) | Replies with a running counter of received text messages. | Long-polling | No |
| [`ollama_bot.py`](#ollama_botpy) | Forwards each text message to a local Ollama server and replies with the model's answer. Handles connection errors, JSON errors, timeouts, and Telegram's 4096-char limit. | Webhook | No |
| [`ollama_smoketest.py`](#ollama_smoketestpy) | One-shot CLI that posts a fixed prompt to Ollama and prints the response. No Telegram involved. | n/a | No |

None of the examples write to the `conversations` table on purpose —
they are kept DB-free to stay focused on one concept each. See
`src/telegram_bot/db/` (when the persistence helpers land) for the
shared insert / query code.

---

## echo_bot.py

Minimal "hello world"-style handler. Demonstrates the pattern used by
all the other examples: build the default application with
`telegram_bot.bot.build_application(settings)` (which already registers
`/start` and `/help`), then attach exactly one `MessageHandler`.

What it shows:

- Loading config via `telegram_bot.config.load_settings()`.
- Adding a `MessageHandler` with the filter
  `filters.TEXT & ~filters.COMMAND` so commands remain handled by the
  defaults and only plain text reaches `echo`.
- Running the bot through `application.run_webhook(...)` — `WEBHOOK_URL`
  must be reachable from Telegram (HTTPS in production).

Run:

```bash
PYTHONPATH=src python examples/echo_bot.py
```

Send any non-command message; the bot replies verbatim. `/start` and
`/help` still come from the defaults.

## counter_bot.py

Shows how to keep per-process state with `context.bot_data`. Each
non-command text message increments a counter and the bot replies with
the new value.

What it shows:

- State stored in `context.bot_data` (a dict that persists across
  updates for the life of the `Application`) is process-local — restart
  the bot and the count resets to 0.
- Running through `application.run_polling()` instead of webhooks, so it
  works without a public HTTPS endpoint. Useful for local development.

Run:

```bash
PYTHONPATH=src python examples/counter_bot.py
```

Send a few messages; first reply is `1`, then `2`, etc.

## ollama_bot.py

Wires the bot to a local Ollama server via `src/ollama.OllamaClient` and
forwards each incoming text message through the `/api/chat` endpoint.
The persona (system prompt) is fixed; the user message is whatever the
sender typed.

What it shows:

- Reading extra env vars (`OLLAMA_HOST`, `OLLAMA_MODEL`) directly via
  `os.getenv`, since `Settings` only knows about Telegram-side config.
- Storing a shared HTTP client in `application.bot_data` so every
  handler reuses the same connection settings (no re-reading the env
  per message).
- Sending `ChatAction.TYPING` so the user gets "typing..." feedback
  while the model thinks. Telegram drops the indicator after ~5 s, so
  long generations will show gaps.
- Offloading the blocking `urllib` call with `asyncio.to_thread` so PTB's
  event loop stays responsive while Ollama is thinking.
- Handling the three realistic failure modes: `URLError` (server
  unreachable), `json.JSONDecodeError` / `KeyError` / `OllamaError`
  (malformed response), and `TimeoutError` (slow model / hang).
- Splitting replies longer than 4096 characters (Telegram's per-message
  cap) into consecutive `reply_text()` calls.

Required in `.env`:

```
OLLAMA_HOST=127.0.0.1:11434
OLLAMA_MODEL=llama3.2   # must be pulled on the server first
```

Run:

```bash
PYTHONPATH=src python examples/ollama_bot.py
```

Then message the bot from Telegram.

## ollama_smoketest.py

Bypasses Telegram entirely. Sends a single hard-coded prompt to Ollama
and prints the model reply to stdout. Use it to confirm `OllamaClient`
is wired correctly before adding the bot on top.

What it shows:

- Importing `OllamaClient` without going through `build_application`.
- That `OllamaClient` is independent of Telegram — you can drive it
  from any script that has `OLLAMA_HOST` and `OLLAMA_MODEL` set.

Required in `.env` (same as `ollama_bot.py`):

```
OLLAMA_HOST=127.0.0.1:11434
OLLAMA_MODEL=llama3.2
```

Run:

```bash
PYTHONPATH=src python examples/ollama_smoketest.py
```

Expected output (model-dependent):

```
POST http://127.0.0.1:11434/api/chat
model=llama3.2 prompt='Tell me a joke'
---- response ----
<the joke>
------------------
```

If the server is unreachable you get `Connection failed: <reason>` and
a non-zero exit — useful for first-boot troubleshooting.

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
| [`db_ollama_bot.py`](#db_ollama_botpy) | Same as `ollama_bot.py` but with full per-chat conversation history persisted to SQLite. The active row is created on first message and closed by `/exit` or `/new`. | Webhook | Yes |
| [`invoiceninja_bot.py`](#invoiceninja_botpy) | Wires the bot to InvoiceNinja: list clients, create an invoice for an existing client, or create a new client + invoice in one go. | Webhook | No |
| [`ollama_smoketest.py`](#ollama_smoketestpy) | One-shot CLI that posts a fixed prompt to Ollama and prints the response. No Telegram involved. | n/a | No |

The DB-related example imports `telegram_bot.db` (in
`src/telegram_bot/db.py`), a thin wrapper around `sqlite3` that owns
`create_active`, `append_turn`, `get_active`, `close_active`, and
`get_transcript`.

The InvoiceNinja example uses `invoiceninja.InvoiceNinjaClient` (in
`src/invoiceninja/__init__.py`), a thin wrapper around the
`/api/v1` REST endpoints. The current surface covers clients and
invoices; the transport layer is shared so adding more endpoints
later is small.

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

## db_ollama_bot.py

`ollama_bot.py` with a real persistence layer. Builds on the same
`OllamaClient` and webhook plumbing, plus `telegram_bot.db` for
SQLite storage.

What it shows:

- **Active-row lookup by `chat_id`.** Each Telegram chat has at most
  one row with `status = 1`. First message in a chat inserts it;
  subsequent messages reuse the same row. The lookup is indexed
  (`idx_conversations_chat_active` on `(chat_id, status)`).
- **Append-only transcript.** The `conversation` column stores turns
  in the form `USER:foo\n\nSYSTEM:bar\n\n` repeated. Persisted in full
  — we never edit history.
- **Session control.** `/exit` and `/new` both set `status = 0` and
  say goodbye. Next text message starts a fresh row. The handler
  caches the active row id in `bot_data["active_rows"]` to avoid
  hitting the DB on every turn.
- **Context windowing.** A configurable budget
  (`OLLAMA_CONTEXT_CHARS`, default 8000) caps how much of the stored
  transcript is sent to Ollama per turn. The model sees the *tail* of
  the transcript; older turns are dropped. The full transcript stays
  in the row, so widening the budget later doesn't lose data.
- **Ollama request shape.** Each call sends
  `[system, ...history, current_user]`. The system prompt is fixed;
  history is parsed back from the stored string by splitting on
  `\n\n` and reading the `USER:` / `SYSTEM:` prefix.
- **Same error and 4096-char handling as `ollama_bot.py`**, but with
  one important difference: a failed Ollama call does *not* roll back
  the row — the row is created/loaded before the call, and on error
  we just don't append a turn. This keeps the DB consistent even if
  Ollama flakes.

Required in `.env`:

```
BOT_TOKEN=...
WEBHOOK_URL=https://...
OLLAMA_HOST=127.0.0.1:11434
OLLAMA_MODEL=llama3.2
```

Optional:

```
CONVERSATIONS_DB=/path/to/conversations.db   # default: data/conversations.db
OLLAMA_CONTEXT_CHARS=8000                    # transcript budget sent to Ollama
```

Run:

```bash
PYTHONPATH=src python examples/db_ollama_bot.py
```

Try it:

1. Send any message — bot replies from Ollama.
2. Send another — bot replies using the previous turn as context.
3. Send `/exit` — bot says goodbye, closes the row.
4. Send a new message — a new row is created (old transcript is
   preserved with `status = 0`).

Inspect what was stored:

```bash
sqlite3 data/conversations.db "SELECT id, chat_id, status, length(conversation) FROM conversations"
sqlite3 data/conversations.db "SELECT conversation FROM conversations WHERE id = 1"
```

## invoiceninja_bot.py

Wires the bot to a local InvoiceNinja instance via
`invoiceninja.InvoiceNinjaClient`. The client is built once with
`InvoiceNinjaClient.from_env()` and stored in `bot_data`, so handlers
just call methods on it.

What it shows:

- **Auth.** Reads `INVOICE_NINJA_TOKEN` first. If empty, the client
  will log in with `IN_USER_EMAIL` / `IN_PASSWORD` on first use and
  cache the returned token.
- **Three target use cases:**
  - `/clients` — calls `list_clients()` and prints `id` and `name`.
  - `/invoice <client_id> <amount> <description…>` — calls
    `create_invoice()` with a single line item.
  - `/new_invoice <name> <email> <amount> <description…>` — calls
    `create_client()` then `create_invoice()` for that client.
- **Error handling.** All REST errors are caught as
  `InvoiceNinjaError` and surfaced to the user with a short message;
  the full exception is logged. Connection errors, non-2xx responses,
  and unparseable JSON are all funneled through the same exception
  class.

Required in `.env`:

```
BOT_TOKEN=...
WEBHOOK_URL=https://...
INVOICE_NINJA_TOKEN=...                 # preferred
INVOICENINJA_BASE_URL=http://localhost/ # or http://nginx/ from a sibling container
```

If you don't have a token yet, leave `INVOICE_NINJA_TOKEN` empty —
the client will log in with `IN_USER_EMAIL` / `IN_PASSWORD` on the
first request.

Run:

```bash
PYTHONPATH=src python examples/invoiceninja_bot.py
```

Try it:

```
/clients
/invoice 1 150.00 Consulting
/new_invoice Acme acme@example.com 99 Setup fee
```

The `InvoiceNinjaClient` surface today is small by design. To add a
new endpoint, call `self._request(method, path, json_body=..., params=...)`
and return whatever shape makes sense for the caller; the existing
`_extract_object` and `_extract_list` helpers normalize the most
common response shapes (`{"data": {...}}`, `{"data": [{...}]}`, and
bare lists).

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

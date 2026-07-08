# KISSY v2

Telegram bot assistant for a small custom sewing and embroidery workshop. Helps the owner register invoices and track clients with outstanding balances through a frictionless Telegram interface.

See [`docs/01_system_architecture.md`](docs/01_system_architecture.md) for the
overall system architecture and component responsibilities.

See [`docs/02_use_cases.md`](docs/02_use_cases.md) for the full catalog of
behaviors the system must implement: 36 v1 use cases (Telegram read/write,
dialog lifecycle, notifications, Streamlit auth/Kanban/health, admin/abuse,
data lifecycle) plus 2 deferred, each with main flow, alt/exception flows,
security notes, and a sequence diagram.

See [`docs/history/`](docs/history/README.md) for a per-session log of the
work done so far, plus [`docs/history/roadmap.md`](docs/history/roadmap.md)
for the upcoming-session plan and [`docs/history/mvp-scope.md`](docs/history/mvp-scope.md)
for the locked-in MVP definition.

## What it does (MVP)

The MVP is intentionally small:

1. **Register invoices** via Telegram — including the new-client composite flow (the only multi-op case).
2. **Remind the owner about clients with debts** — both on demand ("quién me debe") and as a daily push at 08:30.

Everything else (tasks, projects, Streamlit, admin bot, voice messages, time logging) is documented in the use cases but is **not** in MVP. See the MVP scope note in `docs/02_use_cases.md` and the per-session logs in `docs/history/`.

## Toolchain

| Tool | Purpose | Why |
|---|---|---|
| [`uv`](https://docs.astral.sh/uv/) | Package manager + virtualenv + lockfile | One command (`uv sync`) replaces `pip` + `venv` + lockfile. Beginner-friendly. |
| Python 3.12 | Runtime | Stable, supported until 2028. |
| `pytest` + `pytest-asyncio` | Tests | De facto standard; needed for the bot's async handlers. |
| `respx`, `freezegun` | HTTP mocking, time mocking | Used to test the Invoice Ninja + Ollama clients deterministically. |
| `ruff` | Linter + formatter | One Rust tool replaces `flake8` + `isort` + `black`. |
| `mypy --strict` | Typechecker | Mature; pairs with `pydantic` for the LLM JSON schemas. |

`pyproject.toml` is the single source of truth for all of the above.

## Setup

> Run these on the Debian server (or any Linux/macOS dev box). The macOS you
> are reading this on should remain a "clean" machine — only the Debian box
> gets the runtime toolchain.

```bash
# 1. Clone the repo and cd into it.
git clone <your-repo-url> kissyv2
cd kissyv2

# 2. Run the bootstrap script. It will:
#    - install uv (if missing) via scripts/install_uv.sh
#    - run `uv sync` to create .venv and install deps
#    - create .env from .env.example (you edit it next)
#    - initialize the SQLite database
bash scripts/setup.sh
```

Manual equivalent (if you prefer to drive it yourself):

```bash
# Install uv (one-time).
bash scripts/install_uv.sh

# Install dependencies + create .venv.
uv sync

# Create .env from .env.example and fill it in.
cp .env.example .env
$EDITOR .env
```

## Run the full MVP stack

The MVP is two things that must both be up: **Invoice Ninja** (in Docker)
and **the bot** (on the host). The order matters.

```bash
# 1. Start Invoice Ninja (app + nginx + mysql + redis).
bash scripts/start_ninja.sh

# 2. Open http://localhost/ in a browser.
#    Log in with IN_USER_EMAIL / IN_PASSWORD from .env.
#    Go to 'User -> API Tokens' and copy the static token.
#    Paste it into INVOICE_NINJA_TOKEN in .env.

# 3. Start the bot.
uv run python -m telegram_bot
```

The bot listens on `WEBHOOK_LISTEN:WEBHOOK_PORT` (default `0.0.0.0:8443`) at path `/<BOT_TOKEN>`. It talks to Invoice Ninja over loopback at `INVOICENINJA_BASE_URL` (default `http://localhost/`).

For a deeper look at how the bot and Ninja talk to each other, see [`docs/ninja-bot-integration.md`](docs/ninja-bot-integration.md). For a "run the bot on boot" setup, see `scripts/systemd/kissy-bot.service.example`.

## Test, lint, typecheck

```bash
uv run pytest            # run all tests
uv run pytest -k smoke   # run a single test by name substring
uv run ruff check .      # lint
uv run ruff format .     # auto-fix formatting
uv run mypy src tests    # typecheck
```

The order `format → lint → typecheck → test` is the recommended local pre-commit chain.

## Database

The bot stores conversation records in a local SQLite database at `data/conversations.db`. Schema lives in `scripts/db/schema.sql` and is applied by `scripts/db/create_db.sh` (called by `scripts/setup.sh`).

> Session 0.1 ships the existing schema. Session 0.2 will add the new tables
> (`audit_log`, `healthchecks`, etc.) defined in `docs/02_use_cases.md`.

Inspect or query it directly:

```bash
sqlite3 data/conversations.db ".schema conversations"
sqlite3 data/conversations.db "SELECT id, status, substr(conversation, 1, 80) FROM conversations"
```

## Environment

See `.env.example` for the full list. MVP-required keys (already pre-populated in `.env.example`):

- `BOT_TOKEN` — from @BotFather
- `WEBHOOK_URL` — public HTTPS base URL
- `INFERENCE_PROVIDER` — `ollama` (default) | `openai` | `google`
- `OLLAMA_HOST` — Ollama server address (e.g. `192.168.1.138:30068`)
- `OLLAMA_MODEL` — model name (e.g. `gemma2:9b`)
- `INVOICENINJA_BASE_URL`, `INVOICE_NINJA_TOKEN` — Invoice Ninja API
- `OWNER_PHONE_ALLOWLIST` — single phone, E.164
- `USER_NAME` — display name used in greetings and notifications

Full reference in [`docs/02_use_cases.md` Appendix A](docs/02_use_cases.md#14-appendix-a--environment-variables-reference).

## Examples

The `examples/` directory contains small demo bots that exercise the building blocks. They run the same way:

```bash
uv run python examples/echo_bot.py
uv run python examples/db_ollama_bot.py
```

See [`docs/examples.md`](docs/examples.md) for what each one does.

## Troubleshooting

### Webhook returns 404 Not Found

Check webhook status:

```bash
curl -s "https://api.telegram.org/bot<BOT_TOKEN>/getWebhookInfo"
```

If `last_error_message` shows `404 Not Found`:

1. Make sure the bot is running and listening on the configured port.
2. Verify the port is reachable from your reverse proxy or the internet.
3. Check firewall rules — port 8443 (or your configured port) must be open.

### Webhook not responding immediately

After starting the bot, **wait 1-2 minutes** for Telegram to deliver updates. Webhook registration is not instant — Telegram may take time to start sending updates to your endpoint.

### `uv` is not found after install

Open a new shell, or `source ~/.local/bin/env` (zsh/bash). The install script prints the exact command for your shell.

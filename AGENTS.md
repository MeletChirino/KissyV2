# AGENTS.md

Repo is early-stage. This file is a stub — fill in sections below as tooling lands.

Before making any changes, read [`docs/01_system_architecture.md`](docs/01_system_architecture.md)
for the full system architecture, component responsibilities, and communication protocols.

Before implementing any behavior, read [`docs/02_use_cases.md`](docs/02_use_cases.md)
for the catalog of use cases (Telegram read/write, dialog lifecycle, notifications,
Streamlit auth/Kanban/health, admin/abuse, data lifecycle) plus deferred cases. Each
use case lists its main flow, alt/exception flows, security notes, and a sequence
diagram. Behavior must conform to those flows; do not invent flows not documented there.

## Layout (verified)

- Python project using the `src/` layout.
- Package: `src/telegram_bot/`
  - `__init__.py` — empty package marker.
  - `__main__.py` — entry point (`python -m telegram_bot`).
  - `config.py` — env loading via `python-dotenv`; `load_settings()` returns a frozen `Settings` dataclass.
  - `bot.py` — `python-telegram-bot` `Application` builder; `build_application(settings)` and `main()`.
- Repo name (`kissyv2`) suggests this is a rewrite/iteration of a previous project; no shared state with older repos should be assumed.

## Run

```
scripts/setup.sh                 # creates .venv + .env, installs deps
# then edit .env (BOT_TOKEN, WEBHOOK_URL)
PYTHONPATH=src python -m telegram_bot
```

`PYTHONPATH=src` is required because the project uses the `src/` layout and has no editable install (no `pyproject.toml`/`setup.py`). Drop the prefix once the package is installed (e.g. `pip install -e .`).

The bot serves the webhook on `WEBHOOK_LISTEN:WEBHOOK_PORT` (default `0.0.0.0:8443`) at path `/<BOT_TOKEN>`, and registers the same URL with Telegram's `setWebhook`. Telegram will refuse to deliver to anything other than HTTPS in production, and only to ports 443/80/88/8443 unless the webhook is registered with an `ip_address`.

## Environment (see `.env.example`)

- `BOT_TOKEN` (required) — token from @BotFather.
- `WEBHOOK_URL` (required) — public HTTPS base URL, no trailing slash.
- `WEBHOOK_LISTEN` (default `0.0.0.0`)
- `WEBHOOK_PORT` (default `8443`)
- `WEBHOOK_SECRET_TOKEN` (optional, recommended) — must be 1-256 chars from `[A-Za-z0-9_-]`.

`.env` is git-ignored; never commit it.

## What does NOT exist yet (do not waste time looking)

- No `README*` or `pyproject.toml`. Manifest is `requirements.txt` only.
- No test framework, fixtures, or `tests/` directory.
- No linter/formatter/typechecker config (`.ruff.toml`, `mypy.ini`, etc.).
- No CI (`.github/`, `.gitlab-ci.yml`, etc.) or pre-commit config.
- No `opencode.json`, `.cursorrules`, `.cursor/rules/`, or `CLAUDE.md`.
- No Dockerfile or deploy config.

## Examples

- `examples/echo_bot.py` — extends `telegram_bot.bot.build_application` with a `MessageHandler` that echoes non-command text, then runs polling. Run with `PYTHONPATH=src python examples/echo_bot.py`. Same env vars as the main bot (`scripts/setup.sh` creates them).

## Conventions to settle once tooling exists

- [ ] Add `README.md` with setup + run instructions.
- [ ] Pick a test runner and document how to run a single test.
- [ ] Pick a linter/formatter/typechecker and document the required order (e.g. `format -> lint -> typecheck -> test`).
- [ ] Decide whether the bot token is loaded only from `.env` or also from a secret manager in production.
- [ ] Decide deployment target (Docker, systemd, cloud run, etc.) and the working directory the entrypoint runs from.

## Open questions for the owner

- Branch / PR / release expectations.
- Whether the bot is exposed directly or behind a reverse proxy (nginx/Caddy) that handles TLS. The current code listens with HTTP and expects a proxy in front.

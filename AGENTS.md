# AGENTS.md

Operational guide for AI coding agents (and humans) working in this repo.

Before making any changes, read:
- [`docs/01_system_architecture.md`](docs/01_system_architecture.md) — system architecture, component responsibilities, communication protocols.
- [`docs/02_use_cases.md`](docs/02_use_cases.md) — the catalog of use cases (Telegram read/write, dialog lifecycle, notifications, Streamlit auth/Kanban/health, admin/abuse, data lifecycle) plus deferred cases. Each use case lists its main flow, alt/exception flows, security notes, and a sequence diagram. **Behavior must conform to those flows; do not invent flows not documented there.**
- [`docs/ninja-bot-integration.md`](docs/ninja-bot-integration.md) — how the bot reaches Invoice Ninja at runtime (loopback, host vs Docker, URL topology). Read this before touching any code that talks to Ninja.
- [`docs/invoiceninja.md`](docs/invoiceninja.md) — Invoice Ninja Docker stack, env vars, and admin setup.
- [`docs/history/README.md`](docs/history/README.md) — per-session logs of the work done so far. Read the most recent one **and** the relevant sections of [`docs/history/roadmap.md`](docs/history/roadmap.md) and [`docs/history/mvp-scope.md`](docs/history/mvp-scope.md) before starting a new session. The deployment identity (server IP, hostname, runbook prompt) also lives in `roadmap.md` — load it before proposing any session.

## Layout (verified)

- Python project using the `src/` layout, managed by `uv`.
- Package: `src/telegram_bot/`
  - `__init__.py` — empty package marker.
  - `__main__.py` — entry point (`python -m telegram_bot`).
  - `config.py` — env loading via `python-dotenv`; `load_settings()` returns a frozen `Settings` dataclass. **Will be rewritten in Session 0.3 to load every Appendix A variable and validate at boot.**
  - `bot.py` — `python-telegram-bot` `Application` builder; `build_application(settings)` and `main()`.
- `tests/` — pytest suite. Runs via `uv run pytest`. `pythonpath = ["src"]` is set in `pyproject.toml` so tests can `import telegram_bot` directly.
- `docs/history/` — per-session logs.

## Toolchain (locked in Session 0.1)

| Tool | Use | Command |
|---|---|---|
| `uv` | Package manager, venv, lockfile | `uv sync`, `uv run ...` |
| `pytest` + `pytest-asyncio` | Tests | `uv run pytest` |
| `respx`, `freezegun` | HTTP + time mocking | (used inside tests) |
| `ruff` | Lint + format | `uv run ruff check .`, `uv run ruff format .` |
| `mypy --strict` | Typecheck | `uv run mypy src tests` |
| Python | 3.12 | pinned in `.python-version` |

The recommended local loop is `uv run ruff format . && uv run ruff check . && uv run mypy src tests && uv run pytest`.

## Run

```bash
# One-time bootstrap (also installs uv if missing).
bash scripts/setup.sh

# Edit .env with your real values.
$EDITOR .env

# Daily driver.
uv run python -m telegram_bot
```

`uv run` automatically uses the `.venv` that `uv sync` creates. No `source .venv/bin/activate`, no `PYTHONPATH` prefix.

The bot serves the webhook on `WEBHOOK_LISTEN:WEBHOOK_PORT` (default `0.0.0.0:8443`) at path `/<BOT_TOKEN>`, and registers the same URL with Telegram's `setWebhook`. Telegram will refuse to deliver to anything other than HTTPS in production, and only to ports 443/80/88/8443 unless the webhook is registered with an `ip_address`.

## Environment (see `.env.example`)

Full reference: [`docs/02_use_cases.md` Appendix A](docs/02_use_cases.md#14-appendix-a--environment-variables-reference).

Critical variables (validated at boot in Session 0.3):
- `BOT_TOKEN` (required) — token from @BotFather.
- `WEBHOOK_URL` (required) — public HTTPS base URL, no trailing slash.
- `OWNER_PHONE_ALLOWLIST` (required) — single phone, E.164.
- `INVOICENINJA_BASE_URL` + `INVOICE_NINJA_TOKEN` (required) — Invoice Ninja API.
- `INFERENCE_PROVIDER` + `OLLAMA_HOST` + `OLLAMA_MODEL` — current inference stack.

`.env` is git-ignored; never commit it.

## Conventions (settled)

- [x] Add `README.md` with setup + run instructions.
- [x] Pick a test runner and document how to run a single test (`uv run pytest -k <substring>`).
- [x] Pick a linter/formatter/typechecker and document the required order (`format → lint → typecheck → test`).
- [ ] Decide whether the bot token is loaded only from `.env` or also from a secret manager in production. **Deferred to post-MVP.**
- [ ] Decide deployment target (Docker, systemd, cloud run, etc.) and the working directory the entrypoint runs from. **Deferred to post-MVP; production is Debian on Proxmox for now, then a commercial VPS.**

## Session workflow

1. The owner drives sessions interactively. Each session is one logical change set.
2. Per-session logs go in `docs/history/session-X.Y.md` with goals, decisions, files added/modified/removed, commands the owner runs, and known follow-ups.
3. The owner reviews and commits. AI agents never commit on their own.
4. Branching: `master` only (per owner, solo project). No PR review.

## What does NOT exist yet (do not waste time looking)

- No CI (`.github/`, `.gitlab-ci.yml`, etc.) or pre-commit config.
- No Dockerfile or deploy config.
- No `opencode.json`, `.cursorrules`, `.cursor/rules/`, or `CLAUDE.md`.
- No `audit_log`, `healthchecks`, `claims`, `admin_bind_codes` tables yet — these land in Session 0.2.
- No `KissyEngine`, `InferenceProvider`, Ninja client, or scheduler yet — Phases 2–5 of the original WBS.
- No Streamlit app code yet (deferred from MVP).

## Examples

- `examples/echo_bot.py` — extends `telegram_bot.bot.build_application` with a `MessageHandler` that echoes non-command text, then runs polling. Run with `uv run python examples/echo_bot.py`.
- `examples/counter_bot.py`, `examples/db_ollama_bot.py`, `examples/invoiceninja_bot.py` — see [`docs/examples.md`](docs/examples.md).

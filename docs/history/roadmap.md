# Roadmap

Future-session plan. **This file is the single source of truth for what
each upcoming session does, so we can resume work across weeks without
re-deriving the plan from chat history.**

Each session is one PR (or one small group of commits). The owner reviews
and commits. The owner's pattern: SSH into the Debian box, run the
session's commands, verify, commit on master.

The cadence target is **one session per owner availability window** —
the owner is a junior engineer with limited weeknight time, so each
session is scoped to be completable in 30–90 minutes of focused work
plus reading/review.

## Production server (Debian on Proxmox)

| Field | Value |
|---|---|
| IP (LAN) | `192.168.1.25` |
| Hostname | `demo-kissy` |
| LAN DNS | `kissy.home` (resolvable from the local network) |
| OS | Debian (Proxmox VM) |
| Outbound HTTPS to `https://astral.sh` | ✅ confirmed (Session 0.1) |
| Future plan | commercial VPS |
| Bot runs on | host (not in Docker) — see `docs/ninja-bot-integration.md` |
| Ninja runs in | Docker compose on the same host |

These numbers live here, not in `.env.example`, because they are
deployment facts, not configuration values. When you move to the
commercial VPS, update this block and re-run through this checklist:

- [ ] Same `.env` carried over (BOT_TOKEN, Ninja creds, etc.).
- [ ] `git pull` on the new box to fetch `uv.lock`.
- [ ] `bash scripts/install_uv.sh` (outbound HTTPS to astral.sh required).
- [ ] `uv sync` to materialize `.venv` from the lockfile.
- [ ] `INVOICENINJA_BASE_URL` updated if Ninja moves to a different
      host (default `http://localhost/` works only when Ninja and the
      bot share a host).

## How to start a new session

When you SSH into the box and want to begin a session, paste this
verbatim into the chat:

```
We are working on the Kissy v2 Telegram bot. The repo is at the current
directory. The session plan is in docs/history/ — read these three files
in order before doing anything:

1. docs/history/session-0.1.md  (what we already did)
2. docs/history/mvp-scope.md   (what MVP actually means)
3. docs/history/roadmap.md     (what the next session is — Session 0.2
                                is DB schema + config loader)

Production server: 192.168.1.25 (hostname demo-kissy, LAN DNS kissy.home),
Debian on Proxmox. Outbound HTTPS to astral.sh is open. Bot runs on the
host, Ninja runs in Docker compose on the same host.

Before starting Session 0.2, confirm:
- `uv --version` works (run `bash scripts/install_uv.sh` if not)
- `uv sync` runs cleanly
- `uv run pytest` is green (the smoke test from Session 0.1)

Then propose the diff for Session 0.2 file by file BEFORE writing
anything. Wait for my approval before running uv sync, pytest, or any
destructive command. The same apply-to-MVP-gate rules from earlier
sessions: I commit, you don't.

One last thing: I am a junior engineer. Explain technical terms when
they come up, and ask before doing anything that touches my real
.env file, the docker-compose stack, or anything outside the repo.
```

This prompt is the **handoff contract**. It does three things:

1. Forces the next agent to read the roadmap instead of asking you
   "what were we doing?" — saves ~10 minutes of recap.
2. Locks the "propose before write" rule that every previous session
   honored, so the cadence stays consistent.
3. Tells the agent you're a junior so technical terms get explained
   in plain language instead of being assumed.


## Conventions for sessions

- One session = one logical change set = one PR-sized commit (or a small
  group of them).
- Every session produces a `docs/history/session-X.Y.md` log written by
  the AI agent before commit.
- Every session ends with a **stop** — the agent does not start the next
  session without the owner's go-ahead.
- "Status: completed" means files were written; verification is the
  owner's job on the Debian box.
- "Status: blocked" means a decision is needed; the log records the
  blocker and what to ask.
- "Out of scope for this session" is always explicit; future sessions
  are listed in the log's "Known follow-ups" section.

## Sessions

### Session 0.1 — Toolchain bootstrap + Ninja runbook ✅ completed

- Installed `uv` as the package manager, replaced `pip` + `requirements.txt`
  with `pyproject.toml` + `uv.lock`. Pinned Python 3.12.
- Picked `pytest` + `pytest-asyncio` + `respx` + `freezegun` for tests,
  `ruff` for lint+format, `mypy --strict` for typecheck.
- Added a `tests/` skeleton with a smoke test, and `scripts/install_uv.sh`
  for the Debian box.
- Added the Ninja runbook (`scripts/start_ninja.sh`,
  `docs/ninja-bot-integration.md`, `scripts/systemd/kissy-bot.service.example`).
- See [`session-0.1.md`](session-0.1.md).

### Session 0.2 — Database schema + config loader (proposed)

**Goal:** land the new tables defined in `docs/02_use_cases.md` and the
validated config loader. No Telegram behavior yet.

**Files to add:**

- `src/telegram_bot/db/__init__.py`
- `src/telegram_bot/db/schema.sql` — moves from `scripts/db/schema.sql`
  to a package-managed file. Adds:
  - `audit_log` (append-only; SQLite triggers block UPDATE/DELETE)
  - `healthchecks` (component, status, latency_ms, ts)
  - `owner_google_email` (single-row config)
  - `claims` (token, chat_id, expected_email, used, expires_at)
  - `admin_bind_codes` (token, used, expires_at)
  - Indexes for the sweep queries.
- `src/telegram_bot/db/migrate.py` — versioned migration runner.
- `src/telegram_bot/db/repositories.py` — `ConversationRepository`,
  `AuditLogRepository`, `HealthRepository`, `ClaimsRepository`.
- `src/telegram_bot/config.py` — rewritten to load every Appendix A
  env var and validate at boot, fail-fast.
- `tests/test_config.py` — locks the env contract.
- `tests/test_db.py` — schema applies; triggers block UPDATE/DELETE on
  `audit_log`; migration runner works.

**Files to modify:**

- `scripts/db/create_db.sh` — points at the new schema location and the
  migration runner.
- `scripts/setup.sh` — drops the legacy `pip`/`venv` fallback (uv is
  now the only path).

**Verification on the Debian box:**

```bash
uv sync
uv run pytest
bash scripts/setup.sh
sqlite3 data/conversations.db ".tables"   # expect: audit_log, conversations, healthchecks, schema_migrations
sqlite3 data/conversations.db ".schema audit_log"
```

**Stop.** Owner reviews schema + config contract.

### Session 0.3 — Inference provider + Ninja client (proposed)

**Goal:** build the two client libraries that KissyEngine will compose.
No Telegram wiring yet.

**Files to add:**

- `src/telegram_bot/inference/__init__.py`
- `src/telegram_bot/inference/provider.py` — abstract `InferenceProvider`
  with `extract_intent(messages) -> {intent, params, confidence}`.
- `src/telegram_bot/inference/ollama.py` — Ollama implementation.
- `src/telegram_bot/security/__init__.py`
- `src/telegram_bot/security/schemas.py` — Pydantic models for the MVP
  intents (`outstanding_balances`, `create_invoice`, `create_client`).
- `src/telegram_bot/security/dispatcher.py` — allowlist of
  `(intent, handler)`; rejects anything else; logs rejections.
- `src/telegram_bot/invoiceninja/__init__.py`
- `src/telegram_bot/invoiceninja/client.py` — typed Ninja client
  (`httpx`); every successful call appends to `audit_log`.
- `tests/test_inference_ollama.py` — mocked Ollama, asserts strict JSON.
- `tests/test_ninja_client.py` — `respx`-mocked HTTP; asserts audit
  appends; asserts `amount ≤ outstanding` rule for payments.
- `requirements` updates in `pyproject.toml`: `httpx`, `pydantic`,
  `apscheduler` (deferred to Session 0.5 but pin now).

**Stop.** Owner reviews the JSON schemas for the three MVP intents.

### Session 0.4 — KissyEngine core (proposed)

**Goal:** the in-process orchestrator. Dialog state machine, 50-msg cap,
idle close, multi-intent handoff, rate limiter, ID-first clarification
helper.

**Files to add:**

- `src/telegram_bot/kissy_engine.py` — owns config, db, inference,
  ninja client, dispatcher, dialog state.
- `src/telegram_bot/dialogs.py` — `Dialog` dataclass, open/close,
  message counter, idle check.
- `src/telegram_bot/security/rate_limit.py` — in-memory token bucket
  per chat.
- `tests/test_kissy_engine.py` — unit tests for cap, idle close,
  multi-intent, rate limit.

**Stop.** Owner reviews the state machine transitions.

### Session 0.5 — Telegram bot wiring for MVP-1 / MVP-2 / MVP-3 (proposed)

**Goal:** the bot actually answers the owner's phone.

**Files to add:**

- `src/telegram_bot/handlers/__init__.py`
- `src/telegram_bot/handlers/messages.py` — free-text routing into
  KissyEngine; replies with previews and inline keyboards.
- `src/telegram_bot/handlers/callbacks.py` — `Confirmar` / `Editar`
  callback handler. Carries `correlation_id`.
- `src/telegram_bot/handlers/wiring.py` — register handlers on the
  `Application`.
- `src/telegram_bot/bot.py` — modified to bootstrap the engine, attach
  handlers, register the webhook.

**Files to modify:**

- `src/telegram_bot/__main__.py` — call the new bootstrap.
- `tests/test_bot_handlers.py` — uses `python-telegram-bot` test
  utilities; covers the three flows end-to-end with mocked Ninja and
  mocked inference.

**Stop.** Owner dogfoods the three flows on the real phone.

### Session 0.6 — Scheduler (proposed)

**Goal:** MVP-4 daily push, idle close sweep, retention purge.

**Files to add:**

- `src/telegram_bot/scheduler/__init__.py`
- `src/telegram_bot/scheduler/jobs.py` — three jobs:
  - Daily 08:30 → `KissyEngine.send_outstanding_balances_to_owner()`.
  - Sweep every N minutes → close dialogs idle ≥ `CONVERSATION_IDLE_MINUTES`.
  - Sweep daily → purge closed dialogs older than
    `CONVERSATION_RETENTION_DAYS`.
- `src/telegram_bot/scheduler/runner.py` — APScheduler bootstrap.
- `src/telegram_bot/notifications/daily_debts.py` — composes the
  Spanish message with relative time phrases (server-computed).
- `tests/test_scheduler.py` — `freezegun` to advance time.
- `tests/test_relative_time.py` — Spanish date phrasing.

**Stop.** Owner verifies the daily push lands at 08:30 (manual
trigger first, then real).

### Session 0.7 — MVP gate (proposed)

**Goal:** smoke test, runbook, README updates, and a written "MVP
shipped" log.

**Files to add:**

- `scripts/dev_run.sh` — boots the bot with `APP_ENV=development`.
- `tests/smoke_e2e.py` — single end-to-end script that exercises all
  three MVP flows against a fake Telegram update.
- `docs/runbooks/mvp.md` — operator runbook for the Debian box.

**Files to modify:**

- `README.md` — "MVP run" instructions finalized; toolchain section
  cross-checked.
- `AGENTS.md` — conventions check; known-follow-ups updated.

**Stop.** MVP shipped. Owner dogfoods for one week.

## Post-MVP slices (not scheduled)

These are documented in `docs/02_use_cases.md` and will be re-planned
once MVP is live. They are NOT in this roadmap because we agreed to
re-derive the WBS after the MVP gate.

- Tasks and projects (UC-T-R03, UC-T-W07..W10) + Kanban (UC-S-K01..K04)
- Streamlit (UC-S-A01..A03, UC-S-K01..K04)
- Admin bot (UC-ADM-01..06) — note UC-ADM-01 baseline is in MVP
- Payments (UC-T-W05, UC-T-W06)
- Voice transcription (UC-DEFER-V01)
- Time logging in Streamlit (UC-DEFER-K03)
- Weekly digest / Monday sections
- Tax computation
- MCP server (UC-DEFER-MCP-01 — placeholder to be added)
- Moving the bot into Docker (post-MVP per AGENTS.md)
- Commercial VPS deploy

## How to read this file

- If you're starting a new session, read the most recent completed
  session log first (e.g. `session-0.1.md`).
- Then read the **next** session's block in this file.
- Then ask the owner for the green light to start.
- The owner commits; you do not.

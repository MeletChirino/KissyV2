# Ninja ↔ Bot integration

How the Kissy Telegram bot reaches Invoice Ninja at runtime. This is the
operational glue between the two pieces. For the architecture overview, see
[`docs/01_system_architecture.md`](01_system_architecture.md). For the use
cases the bot drives, see [`docs/02_use_cases.md`](02_use_cases.md).

## The short version

```
+------------------+        HTTP REST (port 80)        +------------------+
|   Kissy bot      |  ----------------------------->   |   nginx (docker) |
|   (host process) |                                   +--------+---------+
|   python -m      |                                            |
|   telegram_bot   |                                            v
+------------------+                                   +------------------+
                                                       |   app (docker)   |
                                                       |  invoiceninja    |
                                                       |  -debian:latest  |
                                                       +--------+---------+
                                                                |
                                                      +---------+----------+
                                                      | mysql + redis      |
                                                      | (docker compose)   |
                                                      +--------------------+
```

- The bot runs **on the Debian host** via `uv run python -m telegram_bot`.
- The Ninja stack (app + nginx + mysql + redis) runs **inside Docker** via `docker compose`.
- The bot talks to Ninja over **loopback HTTP** at `INVOICENINJA_BASE_URL=http://localhost/`.
- The bot does **not** need to be on the same Docker network as Ninja during MVP.

## Why this layout for MVP

- **Simplicity.** One process to manage (the bot) on the host; one stack to manage (Ninja) in Docker. No shared networks, no service discovery, no `docker exec` to get a shell into the bot.
- **No rebuild loop.** When you change the bot, you don't rebuild a container. You re-run `uv run` on the host and you're done.
- **Matches the current repo.** `docker-compose.yaml` already defines the four Ninja services. Adding the bot as a fifth service now would require a `Dockerfile` and a multi-stage build pipeline, which is out of scope for MVP (deferred to post-MVP per `AGENTS.md`).

## When this layout changes (post-MVP)

When you move to a commercial VPS, the typical next step is to add the bot
as a fifth service in `docker-compose.yaml` and put **both** behind a
single reverse proxy that handles TLS for the Ninja UI **and** the
Telegram webhook. That's a separate session.

## Startup order (Debian box)

```bash
# 1. Bring up the Ninja stack.
bash scripts/start_ninja.sh

# 2. Open http://localhost/ in a browser.
#    Log in with IN_USER_EMAIL / IN_PASSWORD from .env.
#    Go to 'User -> API Tokens' and copy the static token.
#    Paste it into INVOICE_NINJA_TOKEN in .env.

# 3. Start the bot (separate terminal, or as a systemd service — see below).
uv run python -m telegram_bot
```

`scripts/start_ninja.sh` performs a health-check on the `app` container and
prints a reminder to fetch the API token.

## Network details

| From | To | Protocol | Address | Auth |
|---|---|---|---|---|
| bot (host) | nginx (docker) | HTTP | `http://localhost/` (loopback) | none (loopback only) |
| bot (host) | nginx (docker) | HTTPS | `https://kissy.chirino-net.duckdns.org/` if you front nginx with TLS | none |
| Telegram | bot (host) | HTTPS | `https://<WEBHOOK_URL>/<BOT_TOKEN>` | optional `WEBHOOK_SECRET_TOKEN` |
| bot (host) | Ollama (LAN) | HTTP REST | `http://192.168.1.138:30068` (configurable) | none (private LAN) |

### Why `INVOICENINJA_BASE_URL=http://localhost/` and not `http://nginx/`

- `http://nginx/` would only work if the bot were **inside the same Docker
  network** as Ninja. For MVP, the bot runs on the host, so it talks to
  the published port (80) on loopback.
- If you ever run the bot inside Docker too, change the URL to
  `http://nginx/` and add the bot service to `docker-compose.yaml` on the
  same network. That is the post-MVP migration.

### `REQUIRE_HTTPS` in .env

`docker-compose.yaml` exposes Ninja on port 80 only (no TLS). That is fine
while the bot and Ninja are on the same Debian box talking over loopback.

When you expose Ninja to the internet (e.g. on a commercial VPS), set
`REQUIRE_HTTPS=true` in `.env` and put a TLS-terminating proxy in front of
nginx. `docs/invoiceninja.md` covers this in more depth.

## Running the bot as a systemd service (recommended for MVP)

The MVP runbook assumes you'll start the bot on demand. For a real
"always-on" deploy, wrap it in a systemd unit. A starter unit lives at
`scripts/systemd/kissy-bot.service.example` (not enabled by default).
Inspect it, customize the `User=`, `WorkingDirectory=`, and `ExecStart=`
lines, then `sudo systemctl enable --now kissy-bot`.

## What I have NOT done (and why)

- I have **not** modified `docker-compose.yaml` to add the bot. That would
  require a `Dockerfile` and a multi-stage build, which is post-MVP.
- I have **not** put the bot behind the existing nginx container. The bot
  serves its own webhook directly; nginx would only get in the way for
  the MVP local-network deploy.
- I have **not** changed `INVOICENINJA_BASE_URL` in your real `.env`.
  Keep it at `http://localhost/` for MVP.

# MVP scope

Locked in during the planning conversation. The MVP is small on purpose:
the owner is a junior engineer, the system runs on a single Debian box,
and the goal is to ship something the owner can dogfood in under a week
of focused work.

## What "MVP" means here

The MVP is **only** these four user stories. Everything else documented in
`docs/02_use_cases.md` is out of MVP and is built in follow-up slices.

- **MVP-1** As `OWNER`, I can send a free-text message like "factura para
  María López, 2 bordados de logo, $80" and the bot creates the invoice
  in Invoice Ninja, confirming with `Confirmar` / `Editar`.
- **MVP-2** As `OWNER`, I can register an invoice for a new client in the
  same flow (UC-T-W11 composite).
- **MVP-3** As `OWNER`, I can ask "quién me debe" and the bot returns a
  list of clients with outstanding balances (top 5, plus a "Ver todos"
  button if more).
- **MVP-4** As `OWNER`, I receive a Telegram message at 08:30 listing
  clients with debts. If nobody owes anything, the bot still sends a
  short message naming the client closest to settling and a relative time
  phrase (e.g. "el más cercano es Acme, $12, vence el próximo domingo").

## Use cases that ship in MVP

| UC | In MVP? | Notes |
|---|---|---|
| UC-T-W03 · Create invoice | ✅ | MVP-1 |
| UC-T-W11 · Create invoice for new client (composite) | ✅ | MVP-2 |
| UC-T-W01 · Create client | ✅ (as part of UC-T-W11) | only the composite path |
| UC-T-R05 · Outstanding balances per client | ✅ | MVP-3 |
| UC-N-01 · Daily debt push (08:30) | ✅ (daily only) | MVP-4. Weekly sections are **out** of MVP. |
| UC-T-L01 · 50-msg cap with summary prompt | ✅ (baseline) | required for any dialog code |
| UC-T-L02 · Idle close (30 min) | ✅ (baseline) | required for PII retention |
| UC-T-L04 · Notification reschedule vs active dialog | ✅ (baseline) | required by MVP-4 |
| UC-T-L03 · Multi-intent handoff | ✅ (baseline) | required because UC-T-W11 is the only multi-op exception |
| UC-ADM-01 · Rate limit >100 msgs/min | ✅ (baseline) | required security baseline |
| UC-DL-02 · Purge closed dialogs (N=30 days) | ✅ | required for PII retention |
| UC-T-R01..R04, UC-T-W02, UC-T-W04..W10 | ❌ | deferred |
| UC-T-W05 · Record payment | ❌ | owner can record in Ninja UI; add later |
| UC-T-W06 · Unapply payment | ❌ | deferred |
| UC-T-R05's weekly digest | ❌ | owner asked to keep it out of MVP |
| UC-N-01 weekly sections (Monday) | ❌ | out of MVP per owner |
| UC-S-A*, UC-S-K*, UC-ADM-02..06, UC-DL-01, UC-DL-03 | ❌ | out of MVP |
| UC-DEFER-V01 (voice), UC-DEFER-K03 (time logging) | ❌ | already deferred |

## Architectural decisions locked in for MVP

- **Inference:** Ollama on the private LAN. Model `gemma2:9b` (owner
  confirmed the Proxmox box has the RAM; if not, fall back to `:4b` and
  pull it first).
- **Inference provider:** abstract interface in code; Ollama is the only
  implementation for MVP. OpenAI/Google are out of MVP but the interface
  must not lock us in.
- **LLM contract:** strict JSON `{intent, params, confidence}` validated
  by Pydantic. The dispatcher in code is the **only** path to Ninja.
  The LLM never calls Ninja endpoints directly. This is the primary
  prompt-injection mitigation.
- **Writes require confirmation.** Every write shows a preview with
  `Confirmar` and `Editar` buttons. `Editar` opens "¿Qué quieres
  cambiar?" and the dialog continues. There is no `Cancelar` button
  (the doc says `Cancelar` only appears in the no-candidate branch of
  UC-T-W11, which is its only place).
- **No tax computation in MVP.** Server computes `subtotal` and `total`
  from line items; no tax line. Tax computation is a future version.
- **Client field policy (UC-T-W01):** `name` and `phone` are mandatory;
  `cedula` and `address` are strongly suggested (warning row in preview
  if missing).
- **ID-first clarification for PATCH ops** (deferred to non-MVP writes,
  but the helper must exist in code for UC-T-W11's fuzzy match anyway).
- **Dialog cap: 50 messages** (configurable via `CONVERSATION_MSG_CAP`).
- **Streamlit auth tiered by env:** Google OAuth in production; password
  in development. Streamlit is out of MVP but the auth contract is
  documented.
- **Single composite multi-op exception:** UC-T-W11 only. All other
  multi-intents trigger the "Listo, ahora enfoquémonos en la siguiente
  tarea" handoff.
- **Bot runs on the host, Ninja runs in Docker.** Loopback HTTP between
  them. See `docs/ninja-bot-integration.md`.
- **MCP server:** deferred to a later iteration when larger models are
  adopted. Tracked as UC-DEFER-MCP-01 (placeholder, not yet added to
  the doc; will be added in a follow-up).

## Environment inputs (captured for MVP)

| Key | Value | Source |
|---|---|---|
| `OLLAMA_HOST` | `192.168.1.138:30068` | owner, chat |
| `OLLAMA_MODEL` | `gemma2:9b` | owner, chat (was `:2b` in `.env`; will update on Debian box) |
| `OWNER_PHONE_ALLOWLIST` | `+573114052771` | owner, chat |
| `BOT_NAME` | `kissy` | owner, chat |
| `MAX_OUTSTANDING_BALANCES_IN_LIST` | `5` | owner, chat |
| Daily debt push time | 08:30 (SUMMARY_HOUR=8, SUMMARY_MINUTE=30) | doc §13 |
| Bot token, Ninja URL/token, etc. | already in owner's `.env` | `.env` |

## What the owner does NOT need to learn for MVP

- Docker networking beyond `docker compose up -d`.
- Reverse proxies / TLS termination (Ninja serves over plain HTTP on
  loopback; bot exposes its own webhook directly).
- systemd (we ship an example unit but MVP is "run by hand").
- Streamlit, OAuth, MCP, voice, time logging, weekly digest, admin bot.

## Deployment identity (persisted in `roadmap.md`)

The production server's LAN IP, hostname, and DNS name are recorded in
[`roadmap.md`](roadmap.md) under "Production server (Debian on Proxmox)",
along with a copy-paste-ready prompt for starting a new session. Update
that block (not this one) when the deployment target moves to a
commercial VPS.

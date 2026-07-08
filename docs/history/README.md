# Session history

One file per session. Each log records: goals, decisions, files added/modified/removed, commands the owner runs, known follow-ups, and open questions.

| File | Purpose |
|---|---|
| [README.md](README.md) | This index. |
| [mvp-scope.md](mvp-scope.md) | Locked-in MVP scope (user stories MVP-1..MVP-4, which UCs ship, which decisions are final). |
| [roadmap.md](roadmap.md) | Future-session plan (Sessions 0.2 onward). Single source of truth so we can resume work across weeks. |
| [session-0.1.md](session-0.1.md) | Toolchain bootstrap (`uv`, `pyproject.toml`, tests skeleton) + Ninja runbook. Completed. |

## Conventions

- Session numbers are `MAJOR.MINOR` where MAJOR is a phase and MINOR is the step inside that phase.
- "Status: completed" means files were written; verification is the owner's job on the Debian server.
- "Status: blocked" means a decision is needed before the next step; the log records the blocker.
- Per-session logs follow the template in `session-0.1.md` (Goals, Decisions, Files added/modified/removed, Commands, Known follow-ups, Open questions).
- `roadmap.md` is updated whenever the future-session plan changes. The owner reads it before starting a new session.
- `mvp-scope.md` is updated only when the owner explicitly changes the MVP definition.

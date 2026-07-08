#!/usr/bin/env bash
# scripts/setup.sh
# ----------------
# Bootstraps the project on a fresh machine using `uv`.
#
# What it does, in order:
#   1. Verifies Python 3.12 is available (we pin it in .python-version).
#   2. Verifies sqlite3 is available (or installs it via the system package manager).
#   3. Verifies `uv` is on PATH; if not, runs scripts/install_uv.sh.
#   4. Runs `uv sync` to create .venv and install runtime + dev dependencies.
#   5. Creates .env from .env.example if .env does not exist.
#   6. Initializes the SQLite database (best-effort; safe to re-run).
#
# Idempotent: safe to re-run.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

if [ -t 1 ]; then
    green() { printf '\033[32m%s\033[0m\n' "$*"; }
    red()   { printf '\033[31m%s\033[0m\n' "$*"; }
    yellow() { printf '\033[33m%s\033[0m\n' "$*"; }
else
    green()  { printf '%s\n' "$*"; }
    red()    { printf '%s\n' "$*"; }
    yellow() { printf '%s\n' "$*"; }
fi

# 1. Python ---------------------------------------------------------------
if ! command -v python3 >/dev/null 2>&1; then
    red "ERROR: python3 was not found on PATH. Install Python 3.12 and retry."
    exit 1
fi
green "Found python3 ($(python3 --version 2>&1))"

# 2. sqlite3 --------------------------------------------------------------
if ! command -v sqlite3 >/dev/null 2>&1; then
    yellow "sqlite3 was not found on PATH - attempting to install it"
    if command -v apt-get >/dev/null 2>&1; then
        sudo apt-get update -qq && sudo apt-get install -y -qq sqlite3 \
            || { red "ERROR: failed to install sqlite3 via apt-get"; exit 1; }
    elif command -v dnf >/dev/null 2>&1; then
        sudo dnf install -y sqlite || { red "ERROR: failed to install sqlite via dnf"; exit 1; }
    elif command -v yum >/dev/null 2>&1; then
        sudo yum install -y sqlite || { red "ERROR: failed to install sqlite via yum"; exit 1; }
    elif command -v apk >/dev/null 2>&1; then
        sudo apk add --no-cache sqlite || { red "ERROR: failed to install sqlite via apk"; exit 1; }
    elif command -v pacman >/dev/null 2>&1; then
        sudo pacman -Sy --noconfirm sqlite || { red "ERROR: failed to install sqlite via pacman"; exit 1; }
    else
        red "ERROR: sqlite3 was not found and no supported package manager was detected."
        exit 1
    fi
fi
green "Found sqlite3 ($("sqlite3" -version 2>&1 | head -n1))"

# 3. uv -------------------------------------------------------------------
if ! command -v uv >/dev/null 2>&1; then
    yellow "uv was not found on PATH - running scripts/install_uv.sh"
    bash "$SCRIPT_DIR/install_uv.sh"
fi
green "Found uv ($(uv --version 2>&1))"

# 4. uv sync --------------------------------------------------------------
yellow "Installing project dependencies (uv sync)"
uv sync

# 5. .env -----------------------------------------------------------------
if [ -f ".env" ]; then
    green ".env already exists - leaving it unchanged"
else
    if [ ! -f ".env.example" ]; then
        red "ERROR: .env.example not found at $PROJECT_ROOT/.env.example"
        exit 1
    fi
    yellow "Creating .env from .env.example"
    cp .env.example .env
    green "Created .env - fill in BOT_TOKEN, OWNER_PHONE_ALLOWLIST, etc. before starting the bot"
fi

# 6. Database -------------------------------------------------------------
# Session 0.1: the new schema lands in Session 0.2. Until then, we only
# initialize the existing conversations table if the script exists, and
# never fail the setup if the DB is missing or out of date.
if [ -f "$PROJECT_ROOT/scripts/db/create_db.sh" ]; then
    if bash "$PROJECT_ROOT/scripts/db/create_db.sh"; then
        green "Database initialized"
    else
        yellow "WARNING: database initialization failed. Re-run scripts/db/create_db.sh manually."
    fi
else
    yellow "Skipping database initialization - scripts/db/create_db.sh not found"
fi

green "Setup complete."
green "Next:"
green "  1. Edit .env with your BOT_TOKEN, OWNER_PHONE_ALLOWLIST, etc."
green "  2. Run:    uv run python -m telegram_bot"

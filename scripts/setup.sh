#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

VENV_DIR="$PROJECT_ROOT/.venv"

if [ -t 1 ]; then
    green() { printf '\033[32m%s\033[0m\n' "$*"; }
    red() { printf '\033[31m%s\033[0m\n' "$*"; }
    yellow() { printf '\033[33m%s\033[0m\n' "$*"; }
else
    green() { printf '%s\n' "$*"; }
    red() { printf '%s\n' "$*"; }
    yellow() { printf '%s\n' "$*"; }
fi

if ! command -v python3 >/dev/null 2>&1; then
    red "ERROR: python3 was not found on PATH. Install Python 3.10+ and retry."
    exit 1
fi

if ! command -v sqlite3 >/dev/null 2>&1; then
    yellow "sqlite3 was not found on PATH - attempting to install it"
    if command -v apt-get >/dev/null 2>&1; then
        if ! sudo apt-get update -qq && sudo apt-get install -y -qq sqlite3; then
            red "ERROR: failed to install sqlite3 via apt-get. Install it manually and retry."
            exit 1
        fi
    elif command -v dnf >/dev/null 2>&1; then
        if ! sudo dnf install -y sqlite; then
            red "ERROR: failed to install sqlite via dnf. Install it manually and retry."
            exit 1
        fi
    elif command -v yum >/dev/null 2>&1; then
        if ! sudo yum install -y sqlite; then
            red "ERROR: failed to install sqlite via yum. Install it manually and retry."
            exit 1
        fi
    elif command -v apk >/dev/null 2>&1; then
        if ! sudo apk add --no-cache sqlite; then
            red "ERROR: failed to install sqlite via apk. Install it manually and retry."
            exit 1
        fi
    elif command -v pacman >/dev/null 2>&1; then
        if ! sudo pacman -Sy --noconfirm sqlite; then
            red "ERROR: failed to install sqlite via pacman. Install it manually and retry."
            exit 1
        fi
    else
        red "ERROR: sqlite3 was not found and no supported package manager (apt-get/dnf/yum/apk/pacman) was detected."
        red "       Install sqlite3 manually and retry."
        exit 1
    fi
    if ! command -v sqlite3 >/dev/null 2>&1; then
        red "ERROR: sqlite3 still not on PATH after install. Check your PATH and retry."
        exit 1
    fi
    green "Installed sqlite3 ($("sqlite3" -version 2>&1 | head -n1))"
else
    green "Found sqlite3 ($("sqlite3" -version 2>&1 | head -n1))"
fi

if [ ! -f "requirements.txt" ]; then
    red "ERROR: requirements.txt not found in $PROJECT_ROOT"
    exit 1
fi

VENV_PY="$VENV_DIR/bin/python"
JUST_CREATED=0

if [ -d "$VENV_DIR" ]; then
    green "Found existing virtualenv at $VENV_DIR"
else
    yellow "No virtualenv found - creating one at $VENV_DIR"
    if ! python3 -m venv "$VENV_DIR"; then
        red "ERROR: failed to create virtualenv. Is python3-venv available?"
        red "       On Debian/Ubuntu you may need: sudo apt install python3-venv"
        exit 1
    fi
    JUST_CREATED=1
    green "Created virtualenv at $VENV_DIR"
fi

if ! source "$VENV_DIR/bin/activate"; then
    red "ERROR: failed to activate virtualenv at $VENV_DIR/bin/activate"
    exit 1
fi
green "Activated virtualenv ($("$VENV_PY" --version 2>&1))"

if [ "$JUST_CREATED" -eq 1 ]; then
    yellow "Upgrading pip"
    python -m pip install --upgrade pip --quiet || red "WARNING: failed to upgrade pip - continuing"

    yellow "Installing dependencies from requirements.txt"
    if ! python -m pip install -r requirements.txt; then
        red "ERROR: failed to install dependencies from requirements.txt"
        exit 1
    fi
    green "Installed dependencies"
fi

if [ -f ".env" ]; then
    green ".env already exists - leaving it unchanged"
else
    if [ ! -f ".env.example" ]; then
        red "ERROR: .env.example not found at $PROJECT_ROOT/.env.example"
        exit 1
    fi
    yellow "Creating .env from .env.example"
    if ! cp .env.example .env; then
        red "ERROR: failed to create .env from .env.example"
        exit 1
    fi
    green "Created .env - fill in BOT_TOKEN and WEBHOOK_URL before starting the bot"
fi

if [ -f "$PROJECT_ROOT/scripts/db/create_db.sh" ]; then
    if bash "$PROJECT_ROOT/scripts/db/create_db.sh"; then
        green "Database initialized"
    else
        red "ERROR: database initialization failed. Run scripts/db/create_db.sh manually to see details."
        exit 1
    fi
else
    yellow "Skipping database initialization - scripts/db/create_db.sh not found"
fi

green "Setup complete."
green "Next: edit .env, then run: python -m telegram_bot"

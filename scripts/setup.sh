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

green "Setup complete."
green "Next: edit .env, then run: python -m telegram_bot"

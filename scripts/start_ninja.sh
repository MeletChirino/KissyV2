#!/usr/bin/env bash
# scripts/start_ninja.sh
# ----------------------
# Brings up the Invoice Ninja stack (app + nginx + mysql + redis) on the
# Debian production box using docker compose.
#
# The Kissy bot itself is NOT in docker compose during MVP. It runs on the
# host via `uv run python -m telegram_bot` and reaches Ninja over loopback
# at http://localhost/ (which is what INVOICENINJA_BASE_URL points to).
#
# Idempotent: safe to re-run; `docker compose up -d` is a no-op when
# services are already running.
#
# What this script does, in order:
#   1. Sanity-checks that .env exists and has the required keys.
#   2. Sanity-checks that docker + docker compose are installed.
#   3. Runs `docker compose pull` to fetch the latest images.
#   4. Runs `docker compose up -d` to start the stack.
#   5. Waits for the `app` container to become healthy.
#   6. Prints the URL and a one-liner reminder to log in and create an
#      API token for the bot to use.

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

# 1. .env must exist and have the required keys.
if [ ! -f .env ]; then
    red "ERROR: .env not found. Run 'bash scripts/setup.sh' first."
    exit 1
fi
for key in INVOICENINJA_BASE_URL INVOICE_NINJA_TOKEN DB_DATABASE DB_USERNAME DB_PASSWORD DB_ROOT_PASSWORD APP_KEY APP_URL; do
    if ! grep -q "^${key}=" .env; then
        red "ERROR: .env is missing required key: ${key}"
        exit 1
    fi
done
green ".env looks complete"

# 2. docker + compose.
if ! command -v docker >/dev/null 2>&1; then
    red "ERROR: docker is not installed. Install it via 'sudo apt install docker.io' or the official Docker repo."
    exit 1
fi
if docker compose version >/dev/null 2>&1; then
    COMPOSE_CMD="docker compose"
elif command -v docker-compose >/dev/null 2>&1; then
    COMPOSE_CMD="docker-compose"
else
    red "ERROR: docker compose plugin not found. Install 'docker-compose-plugin' or the legacy binary."
    exit 1
fi
green "Using: ${COMPOSE_CMD}"

# 3-4. Pull + up.
yellow "Pulling images (this may take a minute on first run)..."
${COMPOSE_CMD} pull

yellow "Starting services..."
${COMPOSE_CMD} up -d

# 5. Wait for health.
yellow "Waiting for the 'app' container to become healthy (up to 90s)..."
DEADLINE=$(( $(date +%s) + 90 ))
while [ "$(date +%s)" -lt "${DEADLINE}" ]; do
    STATE="$(${COMPOSE_CMD} ps --format json app 2>/dev/null | grep -o '"Health":"[^"]*"' | cut -d'"' -f4 || true)"
    if [ "${STATE}" = "healthy" ]; then
        green "Invoice Ninja app is healthy."
        break
    fi
    sleep 3
done
if [ "${STATE:-}" != "healthy" ]; then
    yellow "WARNING: app did not become healthy within 90s. Check logs:"
    yellow "  ${COMPOSE_CMD} logs --tail=100 app"
    yellow "The rest of the stack may still be usable. Continuing."
fi

# 6. Tell the user what to do next.
IN_URL="$(grep '^APP_URL=' .env | head -n1 | cut -d'=' -f2- | tr -d '"')"
IN_USER="$(grep '^IN_USER_EMAIL=' .env | head -n1 | cut -d'=' -f2- | tr -d '"')"

echo
green "Invoice Ninja is up at: ${IN_URL}"
green "Default admin login:   ${IN_USER}  (password from IN_PASSWORD in .env)"
echo
yellow "Next steps:"
yellow "  1. Open ${IN_URL} in a browser and log in."
yellow "  2. Go to 'User -> API Tokens' and copy the static token."
yellow "  3. Paste it into INVOICE_NINJA_TOKEN in .env."
yellow "  4. Start the bot:    uv run python -m telegram_bot"
echo

#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

DB_DIR="$PROJECT_ROOT/data"
DB_FILE="$DB_DIR/conversations.db"
SCHEMA_FILE="$SCRIPT_DIR/schema.sql"

if [ -t 1 ]; then
    green() { printf '\033[32m%s\033[0m\n' "$*"; }
    red() { printf '\033[31m%s\033[0m\n' "$*"; }
    yellow() { printf '\033[33m%s\033[0m\n' "$*"; }
else
    green() { printf '%s\n' "$*"; }
    red() { printf '%s\n' "$*"; }
    yellow() { printf '%s\n' "$*"; }
fi

if ! command -v sqlite3 >/dev/null 2>&1; then
    red "ERROR: sqlite3 was not found on PATH. Install it and retry."
    red "       On Debian/Ubuntu you may need: sudo apt install sqlite3"
    exit 1
fi

if [ ! -f "$SCHEMA_FILE" ]; then
    red "ERROR: schema file not found at $SCHEMA_FILE"
    exit 1
fi

if [ ! -d "$DB_DIR" ]; then
    yellow "Creating data directory at $DB_DIR"
    if ! mkdir -p "$DB_DIR"; then
        red "ERROR: failed to create directory $DB_DIR"
        exit 1
    fi
    green "Created data directory at $DB_DIR"
fi

if [ -f "$DB_FILE" ]; then
    yellow "Database already exists at $DB_FILE - leaving it untouched"
else
    yellow "Creating SQLite database at $DB_FILE"
    if ! sqlite3 "$DB_FILE" < "$SCHEMA_FILE"; then
        red "ERROR: failed to create database at $DB_FILE"
        exit 1
    fi
    green "Created SQLite database at $DB_FILE"
fi

yellow "Verifying schema"
if ! sqlite3 "$DB_FILE" ".tables"; then
    red "ERROR: failed to verify schema in $DB_FILE"
    exit 1
fi

green "Database is ready at $DB_FILE"

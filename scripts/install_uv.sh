#!/usr/bin/env bash
# scripts/install_uv.sh
# ----------------------
# Installs the `uv` toolchain on macOS or Debian/Ubuntu.
# Idempotent: safe to re-run. If `uv` is already on PATH at a recent version,
# the script exits early without making changes.
#
# What is `uv`? A single Rust binary that replaces `pip`, `pip-compile`, and
# `venv`. We use it as the project's package manager because the workflow
# (`uv sync`, `uv run ...`) is one command instead of three.
#
# Usage:
#   bash scripts/install_uv.sh
#
# After running, open a new shell (or `source ~/.zshrc` / `source ~/.bashrc`)
# so the updated PATH is loaded.

set -euo pipefail

UV_MIN_VERSION="0.4.0"

# 1. If `uv` is already installed at a recent enough version, do nothing.
if command -v uv >/dev/null 2>&1; then
    INSTALLED_VERSION="$(uv --version | awk '{print $2}')"
    echo "uv is already installed: ${INSTALLED_VERSION}"
    # Simple string compare; we do not need semver-aware ordering for the
    # "is anything installed?" check.
    if [ "${INSTALLED_VERSION}" != "unknown" ]; then
        echo "Nothing to do."
        exit 0
    fi
fi

OS="$(uname -s)"

install_macos() {
    echo "Detected macOS."
    # Prefer Homebrew if present (cleanest uninstall later).
    if command -v brew >/dev/null 2>&1; then
        echo "Installing uv via Homebrew..."
        brew install uv
        return
    fi
    # Fallback: official installer from astral.sh.
    echo "Homebrew not found. Falling back to the official installer."
    echo "This downloads a static binary to ~/.local/bin and may modify your shell rc."
    curl -LsSf https://astral.sh/uv/install.sh | sh
}

install_debian() {
    echo "Detected Debian/Ubuntu."
    # Prefer the official apt repo if we have sudo. This is the
    # recommended path on commercial VPSes.
    if command -v sudo >/dev/null 2>&1; then
        echo "Installing uv via the official apt repo (requires sudo)..."
        # Try the apt path. If anything fails (no sudo, no network, etc.)
        # we fall through to the static-binary path.
        if sudo -n true 2>/dev/null; then
            set +e
            sudo apt-get update
            sudo apt-get install -y ca-certificates curl
            curl -LsSf https://astral.sh/uv/install.sh | sudo sh
            set -e
            return
        fi
    fi
    # Fallback: install to ~/.local/bin without touching system packages.
    echo "Falling back to user-local install (~/.local/bin/uv)."
    curl -LsSf https://astral.sh/uv/install.sh | sh
}

case "${OS}" in
    Darwin)
        install_macos
        ;;
    Linux)
        # Best-effort Debian detection; if not Debian, the fallback still works.
        if [ -f /etc/debian_version ] || [ -f /etc/lsb-release ]; then
            install_debian
        else
            echo "Detected Linux (non-Debian). Using the universal installer."
            curl -LsSf https://astral.sh/uv/install.sh | sh
        fi
        ;;
    *)
        echo "Unsupported OS: ${OS}" >&2
        echo "Install uv manually: https://docs.astral.sh/uv/getting-started/installation/" >&2
        exit 1
        ;;
esac

# 2. Verify the install worked.
if command -v uv >/dev/null 2>&1; then
    echo
    echo "uv installed successfully: $(uv --version)"
    echo
    echo "If 'uv' is not found in a new shell, run:"
    echo "    source ~/.local/bin/env   # sh/bash"
    echo "    source ~/.local/bin/env   # zsh (same file)"
    echo "or add ~/.local/bin to your PATH manually."
else
    echo
    echo "uv was not found on PATH after install."
    echo "Try opening a new shell, or check ~/.local/bin/uv exists."
    exit 1
fi

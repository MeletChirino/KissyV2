from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


def _required(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required env var: {name}")
    return value


@dataclass(frozen=True)
class Settings:
    bot_token: str
    webhook_url: str
    webhook_listen: str
    webhook_port: int
    webhook_secret_token: str | None


def load_settings() -> Settings:
    secret = os.getenv("WEBHOOK_SECRET_TOKEN")
    return Settings(
        bot_token=_required("BOT_TOKEN"),
        webhook_url=_required("WEBHOOK_URL").rstrip("/"),
        webhook_listen=os.getenv("WEBHOOK_LISTEN", "0.0.0.0"),
        webhook_port=int(os.getenv("WEBHOOK_PORT", "8443")),
        webhook_secret_token=secret or None,
    )

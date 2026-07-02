"""Ollama client for local LLM chat completions.

Speaks Ollama's HTTP API directly via the standard library (no extra
dependencies). Blocking calls only — wrap in asyncio.to_thread when
calling from async code.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

DEFAULT_TIMEOUT = float(os.getenv("OLLAMA_TIMEOUT", "120"))


class OllamaError(RuntimeError):
    """Raised when the Ollama response cannot be parsed or is empty."""


class OllamaClient:
    """Stateful Ollama client. Holds host, model, and default timeout."""

    def __init__(
        self,
        host: str,
        model: str,
        *,
        timeout: float | None = None,
    ) -> None:
        if not host:
            raise ValueError("host is required")
        if not model:
            raise ValueError("model is required")
        self._host = host.rstrip("/")
        self._model = model
        self._timeout = timeout if timeout is not None else DEFAULT_TIMEOUT

    @property
    def host(self) -> str:
        return self._host

    @property
    def model(self) -> str:
        return self._model

    @property
    def timeout(self) -> float:
        return self._timeout

    def set_host(self, host: str) -> None:
        if not host:
            raise ValueError("host is required")
        self._host = host.rstrip("/")

    def set_model(self, model: str) -> None:
        if not model:
            raise ValueError("model is required")
        self._model = model

    def set_timeout(self, timeout: float) -> None:
        self._timeout = timeout

    def chat(self, messages: list[dict[str, str]], *, stream: bool = False) -> str:
        """Send a chat completion request and return the assistant text.

        `messages` must be a list of ``{"role": ..., "content": ...}`` dicts.
        """
        payload = {
            "model": self._model,
            "messages": messages,
            "stream": stream,
        }
        request = urllib.request.Request(
            f"http://{self._host}/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self._timeout) as response:
                body = json.loads(response.read().decode("utf-8"))
        except urllib.error.URLError:
            raise

        message = body.get("message") or {}
        content = (message.get("content") or "").strip()
        if not content:
            raise OllamaError(f"Ollama returned no content: {body}")
        return content

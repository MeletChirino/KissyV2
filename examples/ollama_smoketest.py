# Ollama Smoke Test
# Sends a single prompt to an Ollama server and prints the response.
#
# Requires:
#   OLLAMA_HOST   (e.g. 127.0.0.1:11434)
#   OLLAMA_MODEL  (e.g. llama3.2, must be pulled on the server)
#
# Run: PYTHONPATH=src python examples/ollama_smoketest.py

import os
import sys
import urllib.error
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ollama import OllamaClient, OllamaError
from telegram_bot.config import load_settings

PROMPT = "Tell me a joke"


def main() -> None:
    load_settings()

    host = os.getenv("OLLAMA_HOST")
    model = os.getenv("OLLAMA_MODEL")
    if not host or not model:
        raise SystemExit("OLLAMA_HOST and OLLAMA_MODEL must be set in .env")

    client = OllamaClient(host=host, model=model)
    messages = [{"role": "user", "content": PROMPT}]
    print(f"POST http://{client.host}/api/chat")
    print(f"model={client.model} prompt={PROMPT!r}")
    try:
        content = client.chat(messages)
    except urllib.error.URLError as exc:
        raise SystemExit(f"Connection failed: {exc.reason}")
    except OllamaError as exc:
        raise SystemExit(str(exc))

    print("---- response ----")
    print(content)
    print("------------------")


if __name__ == "__main__":
    main()

"""Provider-agnostic chat client over the OpenAI-compatible /chat/completions
shape (stdlib only — no SDK lock-in). Local Ollama by default; any hosted
provider is an env-var change:

  STEWARD_LLM_BASE_URL  default http://localhost:11434/v1
  STEWARD_LLM_MODEL     default gpt-oss:20b
  STEWARD_LLM_API_KEY   optional bearer token
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request


class LLMUnavailable(Exception):
    """The model endpoint failed; the gateway reports it, never fakes it."""


def chat_completion(messages: list[dict[str, str]], timeout: float = 120.0) -> str:
    base_url = os.environ.get("STEWARD_LLM_BASE_URL", "http://localhost:11434/v1")
    model = os.environ.get("STEWARD_LLM_MODEL", "gpt-oss:20b")
    api_key = os.environ.get("STEWARD_LLM_API_KEY", "")

    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/chat/completions",
        data=json.dumps(
            {"model": model, "messages": messages, "temperature": 0.2, "stream": False}
        ).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            **({"Authorization": f"Bearer {api_key}"} if api_key else {}),
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
        return payload["choices"][0]["message"]["content"]
    except (urllib.error.URLError, KeyError, IndexError, json.JSONDecodeError, TimeoutError) as e:
        raise LLMUnavailable(f"{type(e).__name__}: {e}") from e

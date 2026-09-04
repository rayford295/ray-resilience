"""Provider-agnostic chat client over the OpenAI-compatible /chat/completions
shape (stdlib only — no SDK lock-in). Local Ollama by default; any hosted
provider is an env-var change:

  STEWARD_LLM_BASE_URL  default http://localhost:11434/v1
  STEWARD_LLM_MODEL     default gpt-oss:20b
  STEWARD_LLM_API_KEY   optional bearer token
"""

from __future__ import annotations

import base64
import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


class LLMUnavailable(Exception):
    """The model endpoint failed; the gateway reports it, never fakes it."""


def image_part(source: str | Path | bytes, mime: str = "image/jpeg") -> dict[str, Any]:
    """One image as an OpenAI-style content part (base64 data URL).

    Vision models behind the same /chat/completions shape (Ollama's qwen2.5vl,
    llama3.2-vision, gemma3; hosted providers alike) accept a message whose
    `content` is a list of parts instead of a string. The bytes are inlined, so
    nothing is fetched by the model host and no URL to an image ever leaves
    this process — the same keyless/offline property the rest of the gateway
    keeps.
    """
    data = source if isinstance(source, bytes) else Path(source).read_bytes()
    encoded = base64.b64encode(data).decode("ascii")
    return {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{encoded}"}}


def text_part(text: str) -> dict[str, Any]:
    return {"type": "text", "text": text}


def chat_completion(
    messages: list[dict[str, Any]],
    timeout: float = 120.0,
    *,
    response_format: dict[str, Any] | None = None,
    temperature: float = 0.2,
    model: str | None = None,
) -> str:
    """Return the assistant text. `messages[*].content` may be a string or a
    list of parts (see image_part). `response_format={"type": "json_object"}`
    asks the endpoint to constrain output to JSON where it supports that;
    callers still parse defensively because not every server honours it."""
    base_url = os.environ.get("STEWARD_LLM_BASE_URL", "http://localhost:11434/v1")
    model = model or os.environ.get("STEWARD_LLM_MODEL", "gpt-oss:20b")
    api_key = os.environ.get("STEWARD_LLM_API_KEY", "")

    body: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "stream": False,
    }
    if response_format is not None:
        body["response_format"] = response_format
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/chat/completions",
        data=json.dumps(body).encode("utf-8"),
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

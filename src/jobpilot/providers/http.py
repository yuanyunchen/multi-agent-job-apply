"""An OpenAI-compatible HTTP provider.

The key is never stored in the settings file: the file names an **environment
variable**, and the key is read from the environment at call time.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass

from ..testmode import ensure_live
from .base import Health, ModelResult, redact, schema_hint


@dataclass
class OpenAICompatibleProvider:
    base_url: str
    model: str
    api_key_env: str
    name: str = "openai_compatible"
    capabilities: frozenset[str] = frozenset({"screen", "review"})
    timeout: float = 120.0

    @property
    def _key(self) -> str:
        return os.environ.get(self.api_key_env, "")

    def health(self) -> Health:
        if not self.base_url or not self.model:
            return Health(False, "this service is missing its address or model name")
        if not self._key:
            return Health(
                False,
                f"I need the key in the environment variable {self.api_key_env} before I can use this service.",
            )
        return Health(True, "configured")

    def complete(self, prompt: str, *, schema: dict | None = None, timeout: int = 600) -> ModelResult:
        ensure_live("network")
        import urllib.error
        import urllib.request

        if not self._key:
            return ModelResult(False, "", self.name, failure="not_signed_in")
        body = json.dumps(
            {
                "model": self.model,
                "messages": [{"role": "user", "content": prompt + schema_hint(schema)}],
            }
        ).encode("utf-8")
        request = urllib.request.Request(
            self.base_url.rstrip("/") + "/chat/completions",
            data=body,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._key}",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=min(self.timeout, timeout)) as response:
                payload = json.loads(response.read().decode("utf-8", "replace"))
        except urllib.error.HTTPError as exc:
            failure = "rate_limited" if exc.code == 429 else "error"
            return ModelResult(False, "", self.name, failure=failure)
        except (OSError, ValueError):
            return ModelResult(False, "", self.name, failure="error")
        try:
            text = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            return ModelResult(False, "", self.name, failure="refused")
        return ModelResult(True, redact(text), self.name, usage=payload.get("usage") or {})

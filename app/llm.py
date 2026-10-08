"""LLM access layer.

* LLMClient talks to any OpenAI-compatible chat API (OpenAI by default; set OPENAI_BASE_URL for
  Gemini/Azure/Ollama/etc.). JSON mode is used for every structured call.
* If no API key is configured, `available` is False and every caller transparently uses a
  deterministic offline fallback, so the whole system still runs end-to-end (and in CI).
"""
from __future__ import annotations

import json
import os
import re


class LLMUnavailable(Exception):
    pass


class LLMClient:
    def __init__(self, api_key: str | None = None, model: str | None = None, base_url: str | None = None,
                 timeout: float = 30.0):
        self.api_key = api_key if api_key is not None else os.getenv("OPENAI_API_KEY", "")
        if self.api_key in ("your_api_key_here", "sk-..."):
            self.api_key = ""
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self.base_url = base_url or os.getenv("OPENAI_BASE_URL") or None
        self.timeout = timeout
        self._client = None

    @property
    def available(self) -> bool:
        return bool(self.api_key)

    @property
    def mode(self) -> str:
        return f"llm:{self.model}" if self.available else "offline"

    def _get(self):
        if not self.available:
            raise LLMUnavailable("OPENAI_API_KEY is not set")
        if self._client is None:
            from openai import OpenAI
            self._client = OpenAI(api_key=self.api_key, base_url=self.base_url,
                                  timeout=self.timeout, max_retries=2)
        return self._client

    def chat(self, system: str, user: str, json_mode: bool = False) -> str:
        try:
            kwargs = {"response_format": {"type": "json_object"}} if json_mode else {}
            resp = self._get().chat.completions.create(
                model=self.model, temperature=0,
                messages=[{"role": "system", "content": system}, {"role": "user", "content": user}], **kwargs)
            return resp.choices[0].message.content or ""
        except LLMUnavailable:
            raise
        except Exception as exc:  # network/auth/rate-limit -> caller falls back
            raise LLMUnavailable(f"{type(exc).__name__}: {exc}") from exc

    def chat_json(self, system: str, user: str) -> dict:
        text = self.chat(system, user + "\n\nReturn ONLY a valid JSON object.", json_mode=True)
        return parse_json(text)


def parse_json(text: str) -> dict:
    text = text.strip()
    text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.M).strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, flags=re.S)
        if not m:
            raise LLMUnavailable("LLM did not return JSON")
        data = json.loads(m.group(0))
    if not isinstance(data, dict):
        raise LLMUnavailable("LLM JSON is not an object")
    return data


def get_llm() -> LLMClient:
    return LLMClient()

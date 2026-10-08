"""LLM tool with guaranteed fallback: real LLM output is schema-checked; on failure/invalid output the
deterministic offline implementation is used and the reason is reported."""
from __future__ import annotations

from app import llm_offline
from app.core.tools import tool


@tool("llm", "LLM generation/classification with schema validation and offline fallback", needs_ctx=True)
def llm(ctx, task: str, facts: dict, system: str = "", prompt: str = "") -> dict:
    required = llm_offline.REQUIRED_KEYS[task]
    reason = None
    if ctx.llm.available:
        try:
            out = ctx.llm.chat_json(system, prompt)
            if all(k in out and out[k] not in (None, "", []) for k in required):
                return {"source": f"llm:{ctx.llm.model}", "content": out}
            reason = f"LLM output missing keys {[k for k in required if k not in out]}"
        except Exception as exc:
            reason = str(exc)
    else:
        reason = "no API key configured"
    content = llm_offline.TASKS[task](facts)
    ctx.note(f"offline fallback used ({reason})")
    return {"source": "offline_fallback", "content": content, "fallback_reason": reason}

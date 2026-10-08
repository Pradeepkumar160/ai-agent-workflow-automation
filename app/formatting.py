"""Human-readable rendering of an AgentResponse (used by the CLI and the demo report)."""
from __future__ import annotations

from app.models import AgentResponse

MARK = {"success": "[OK]", "failed": "[FAILED]", "blocked": "[BLOCKED]", "not_run": "[ -- ]", "running": "[...]"}


def render(resp: AgentResponse, show_tools: bool = True) -> str:
    sel, res = resp.selection, resp.result
    out = [f"Request: {resp.request}", ""]
    if sel.workflow_id is None:
        out += ["Selected Workflow: (none)", f"Reason: {sel.reason}", f"Agent: {sel.clarification}"]
        return "\n".join(out)
    out += [f"Selected Workflow: {sel.workflow_id} - {sel.workflow_name}",
            f"Routing: {sel.method}, confidence {sel.confidence:.2f}", f"Why: {sel.reason}"]
    if sel.alternatives:
        out.append("Alternatives: " + ", ".join(f"{a['workflow_id']} ({a['score']})" for a in sel.alternatives))
    shown = {k: v for k, v in res.inputs.items() if k not in res.defaults_used}
    out.append(f"Inputs: {shown or '(none extracted)'}")
    if res.defaults_used:
        out.append("Defaults used (sample data / settings): " + ", ".join(res.defaults_used))
    out += ["", "Steps Executed:"]
    for s in res.steps:
        line = f"  {s.index + 1}. {MARK.get(s.status, s.status)} {s.name}  ({s.duration_ms:.1f} ms)"
        if show_tools and s.tool_calls:
            line += "  tools: " + ", ".join(
                f"{t.tool}{'(retried x' + str(t.attempts) + ')' if t.attempts > 1 else ''}" for t in s.tool_calls)
        out.append(line)
        if s.detail:
            out.append(f"       - {s.detail}")
    out += ["", f"Status: {res.status.upper()}  ({res.duration_ms:.0f} ms, LLM mode: {res.llm_mode})"]
    if res.status == "needs_input":
        out.append(f"Agent needs more info: {res.question}")
    elif res.error:
        out.append(f"Error: {res.error}")
    out += ["", "Result:", res.summary]
    return "\n".join(out)

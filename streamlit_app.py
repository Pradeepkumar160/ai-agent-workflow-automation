"""Streamlit demo UI:  streamlit run streamlit_app.py"""
import json
import tempfile
from pathlib import Path

import streamlit as st

from app.agent import WorkflowAgent
from app.core import registry

ROOT = Path(__file__).resolve().parent
ICON = {"success": "OK", "failed": "FAILED", "blocked": "BLOCKED", "not_run": "--", "running": "..."}
STATUS_BOX = {"success": st.success, "escalated": st.warning, "needs_input": st.warning, "failed": st.error,
              "not_implemented": st.error}

st.set_page_config(page_title="AI Agent Workflow Automation", layout="wide")


@st.cache_resource
def get_agent():
    return WorkflowAgent()


agent = get_agent()
st.title("AI Agent Workflow Automation")
st.caption("Excel-defined workflows -> agent routing -> tool execution -> conditions/errors -> result")

with st.sidebar:
    st.subheader("Workflows (loaded from Excel)")
    for w in agent.catalog.all():
        st.markdown(f"**{w.workflow_id}** {w.workflow_name}" + ("" if registry.get_spec(w.workflow_id) else "  (not implemented)"))
    st.divider()
    st.caption(f"LLM mode: `{agent.llm.mode}`" + ("" if agent.llm.available else "  (set OPENAI_API_KEY for LLM routing/generation)"))
    override = st.selectbox("Workflow override", ["Auto-route (agent decides)"] + agent.catalog.ids())

examples = {"": ""}
try:
    import pandas as pd
    q = pd.read_excel(agent.catalog.excel_path, sheet_name="Test_Questions")
    examples.update({f"{r.Workflow_ID}: {r.Test_Request}": r.Test_Request for r in q.itertuples()})
except Exception:
    pass
choice = st.selectbox("Example requests (from the Excel Test_Questions sheet)", list(examples))
request = st.text_area("Your request", value=examples[choice], height=80, placeholder="Which products need restocking?")
c1, c2 = st.columns(2)
upload = c1.file_uploader("Optional: upload a CSV/XLSX for the workflow to process (vendor file, keywords, ...)",
                          type=["csv", "xlsx", "xls"])
extra = c2.text_area("Optional explicit inputs (JSON)", value="", height=110,
                     placeholder='{"task_description": "Build a Python API", "goal": "Launch", "dates": "Oct 10-20"}')

if st.button("Run", type="primary", use_container_width=True):
    inputs, ok = {}, True
    if extra.strip():
        try:
            inputs = json.loads(extra)
        except json.JSONDecodeError as exc:
            st.error(f"Inputs JSON is invalid: {exc}")
            ok = False
    if upload is not None:
        tmp = Path(tempfile.mkdtemp()) / upload.name
        tmp.write_bytes(upload.getvalue())
        request = f"{request} {tmp}"
    if ok and request.strip():
        wid = None if override.startswith("Auto") else override
        st.session_state["resp"] = agent.handle(request, inputs, workflow_id=wid)
    elif ok:
        st.error("Enter a request.")

resp = st.session_state.get("resp")
if resp:
    sel, res = resp.selection, resp.result
    st.subheader("1. Selected workflow")
    if sel.workflow_id is None:
        st.warning(sel.clarification)
    else:
        a, b, c = st.columns(3)
        a.metric("Workflow", f"{sel.workflow_id}")
        b.metric("Confidence", f"{sel.confidence:.0%}")
        c.metric("Routing method", sel.method)
        st.write(f"**{sel.workflow_name}** - {sel.reason}")
        if res.inputs:
            st.caption("Inputs used: " + json.dumps({k: v for k, v in res.inputs.items() if k not in res.defaults_used}, default=str)
                       + (f"  | defaults: {', '.join(res.defaults_used)}" if res.defaults_used else ""))
        st.subheader("2. Steps executed")
        for s in res.steps:
            tools = ", ".join(t.tool for t in s.tool_calls)
            st.markdown(f"`{ICON.get(s.status, s.status)}` **{s.index + 1}. {s.name}** &nbsp; {s.duration_ms:.1f} ms"
                        + (f" &nbsp; tools: `{tools}`" if tools else "") + (f"  \n&nbsp;&nbsp;&nbsp;&nbsp;_{s.detail}_" if s.detail else ""))
        st.subheader("3. Result")
        STATUS_BOX.get(res.status, st.info)(f"Status: {res.status.upper()}")
        if res.status == "needs_input":
            st.info(res.question)
        elif res.error:
            st.error(res.error)
        if res.summary and res.status != "needs_input":
            st.code(res.summary, language="text")
        for art in res.artifacts:
            p = ROOT / art if not Path(art).is_absolute() else Path(art)
            if p.exists():
                st.download_button(f"Download {p.name}", p.read_bytes(), file_name=p.name, key=str(p))
        with st.expander("Structured output (JSON)"):
            st.json(res.data)
        with st.expander("Tool-call trace"):
            st.json([{"step": s.name, "tool_calls": [t.__dict__ for t in s.tool_calls]} for s in res.steps])

# Adding an 11th workflow

Adding a workflow touches **two places only**. Router, engine, CLI and UI are not edited.

## 1. Add a row to `data/AI_Agent_Workflow_Assessment.xlsx` (sheet `Workflows`)

| Workflow_ID | Workflow_Name | Trigger | Inputs | Steps | Decision_Logic | Tools_Required | Expected_Output |
|---|---|---|---|---|---|---|---|
| WF011 | Supplier Lead Time Analysis | User asks to analyse supplier delivery lead times | Delivery CSV | Load deliveries → calculate lead time → flag slow suppliers | Flag suppliers above 7 days | CSV reader; calculator | Lead-time report |

The router builds its index from every column, so the new workflow is routable immediately.

## 2. Add `app/workflows/wf011_lead_time.py`

```python
from app.core.registry import InputSpec, workflow

@workflow("WF011", inputs=[
    InputSpec("deliveries_path", "Delivery CSV", default="data/mock/deliveries.csv", kind="file", primary=True),
    InputSpec("max_days", "Flag above N days", default=7, kind="number", pattern=r"(\d+)\s*days"),
])
def run(ctx):
    with ctx.step(0):                      # "Load deliveries"  (index = position in the Excel Steps cell)
        df = ctx.call("csv_reader", path=ctx.inputs["deliveries_path"])
    with ctx.step(1):                      # "calculate lead time"
        df["lead"] = ctx.call("calculator", op="percentage_difference", base=df["promised"], other=df["actual"])
    with ctx.step(2):                      # "flag slow suppliers"
        slow = df[df["lead"] > ctx.inputs["max_days"]]
    return {"summary": f"{len(slow)} slow suppliers", "data": {"slow": slow.to_dict("records")}}
```

* `InputSpec(required=True, question=...)` makes the engine ask the user before running.
* `InputSpec(pattern=...)` lets the agent pull the value out of the free-text request.
* `any_of=[["a", "b"]]` on `@workflow` requires at least one of several inputs.
* Need a new capability? Register a tool once in `app/tools/` with `@tool(name, description)`; any workflow can call it with `ctx.call(name, ...)`.
* Raise `NeedsInput(question)` to ask the user mid-run; return `{"status": "escalated", ...}` to escalate.

Modules in `app/workflows/` and `app/tools/` are auto-discovered. `tests/test_engine.py::test_adding_an_11th_workflow...` proves this end-to-end.

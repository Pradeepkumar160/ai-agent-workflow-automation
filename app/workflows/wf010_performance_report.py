"""WF010 Workflow Performance Report."""
import json

import pandas as pd

from app.config import mock
from app.core.registry import InputSpec, workflow


@workflow("WF010", inputs=[
    InputSpec("logs_path", "Execution log CSV", default=mock("execution_logs.csv"), kind="file", primary=True),
    InputSpec("failure_threshold_percent", "Flag failure rate above %", default=10, kind="number"),
    InputSpec("time_threshold_seconds", "Flag average run time above (seconds)", default=8, kind="number"),
    InputSpec("slow_step_seconds", "A step is slow above (seconds)", default=3, kind="number"),
])
def run(ctx):
    f_thr, t_thr = float(ctx.inputs["failure_threshold_percent"]), float(ctx.inputs["time_threshold_seconds"])
    s_thr = float(ctx.inputs["slow_step_seconds"])
    with ctx.step(0):  # Load execution logs
        df = ctx.call("csv_reader", path=ctx.inputs["logs_path"])
        ctx.call("data_validation", df=df, required_columns=["workflow_id", "status", "execution_time_seconds"])
        df["execution_time_seconds"] = pd.to_numeric(df["execution_time_seconds"], errors="coerce").fillna(0.0)
        df["status"] = df["status"].str.lower().str.strip()
        if "run_id" not in df.columns:
            df["run_id"] = range(len(df))
        if "step" not in df.columns:
            df["step"] = None
        if "error" not in df.columns:
            df["error"] = None
        ctx.note(f"{len(df)} log rows, {df['run_id'].nunique()} runs")

    with ctx.step(1):  # Calculate success/failure rate   (a run fails if any of its steps failed)
        runs = df.groupby(["workflow_id", "run_id"]).agg(
            failed=("status", lambda s: (s == "failure").any()), seconds=("execution_time_seconds", "sum")).reset_index()
        stats = []
        for wid, g in runs.groupby("workflow_id"):
            total, fails = len(g), int(g["failed"].sum())
            stats.append({"workflow_id": wid, "runs": total, "failures": fails,
                          "failure_rate": round(ctx.call("calculator", op="rate", count=fails, total=total), 2),
                          "success_rate": round(100 - ctx.call("calculator", op="rate", count=fails, total=total), 2)})

    with ctx.step(2):  # Calculate average execution time
        avg = runs.groupby("workflow_id")["seconds"].apply(lambda s: ctx.call("calculator", op="mean", values=s))
        for s in stats:
            s["avg_execution_time"] = round(float(avg[s["workflow_id"]]), 2)
            s["flagged"] = s["failure_rate"] > f_thr or s["avg_execution_time"] > t_thr
            s["flag_reasons"] = ([f"failure rate {s['failure_rate']}% > {f_thr:g}%"] if s["failure_rate"] > f_thr else []) + \
                                ([f"avg time {s['avg_execution_time']}s > {t_thr:g}s"] if s["avg_execution_time"] > t_thr else [])
        stats.sort(key=lambda s: (-s["failure_rate"], -s["avg_execution_time"]))

    with ctx.step(3):  # Identify frequent errors
        errs = df[(df["status"] == "failure") & df["error"].notna()]
        frequent = errs.groupby(["error"]).agg(count=("error", "size"), workflows=("workflow_id", lambda s: sorted(set(s)))) \
            .sort_values("count", ascending=False).reset_index()
        frequent_errors = frequent.to_dict("records")

    with ctx.step(4):  # Identify slow steps
        step_avg = df[df["step"].notna()].groupby(["workflow_id", "step"])["execution_time_seconds"].mean().reset_index()
        slow = [{"workflow_id": r.workflow_id, "step": r.step, "avg_seconds": round(float(r.execution_time_seconds), 2)}
                for r in step_avg.sort_values("execution_time_seconds", ascending=False).itertuples()
                if r.execution_time_seconds > s_thr]

    with ctx.step(5):  # Generate recommendations
        flagged = [s for s in stats if s["flagged"]]
        facts = {"flagged": flagged, "frequent_errors": {e["error"]: e["count"] for e in frequent_errors},
                 "slow_steps": slow, "failure_threshold": f_thr, "time_threshold": t_thr}
        gen = ctx.call("llm", task="recommendations", facts=facts,
                       system="You are an SRE. Give concise, specific, actionable recommendations based only on the data.",
                       prompt="Return JSON {\"recommendations\": [strings]} for this workflow-performance data:\n" + json.dumps(facts, default=str))
        recs = gen["content"]["recommendations"]
        path = ctx.call("reporting", name="wf010_performance_report", content={"workflows": stats,
                        "frequent_errors": frequent_errors, "slow_steps": slow, "recommendations": recs}, fmt="json")
    lines = [f"- {s['workflow_id']}: {s['failure_rate']}% failures ({s['failures']}/{s['runs']}), avg {s['avg_execution_time']}s"
             + (f"  FLAGGED ({'; '.join(s['flag_reasons'])})" if s["flagged"] else "") for s in stats]
    summary = (f"{len(flagged)} of {len(stats)} workflows flagged (failure rate > {f_thr:g}% or avg time > {t_thr:g}s).\n"
               + "\n".join(lines) + "\nTop errors: " + "; ".join(f"{e['error']} x{e['count']}" for e in frequent_errors[:3])
               + "\nSlow steps: " + "; ".join(f"{s['workflow_id']}.{s['step']} {s['avg_seconds']}s" for s in slow[:3])
               + "\nRecommendations:\n" + "\n".join(f"  * {r}" for r in recs) + f"\nReport: {path}")
    return {"summary": summary, "data": {"thresholds": {"failure_rate_percent": f_thr, "avg_time_seconds": t_thr},
            "workflows": stats, "frequent_errors": frequent_errors, "slow_steps": slow, "recommendations": recs}}

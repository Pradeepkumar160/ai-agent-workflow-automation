"""Command line interface.

  python -m app.cli "Which products need restocking?"
  python -m app.cli "Where is order ORD-1001?" --json
  python -m app.cli "Process this vendor file" --file data/mock/vendor_products.xlsx
  python -m app.cli --list            # workflows loaded from Excel
  python -m app.cli --demo            # run every Excel test question + examples/requests.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

from app.agent import WorkflowAgent
from app.config import OUTPUT_DIR, ROOT
from app.core import registry
from app.formatting import render


def run_demo(agent: WorkflowAgent, out_dir: Path) -> list[dict]:
    cases = []
    q = pd.read_excel(agent.catalog.excel_path, sheet_name="Test_Questions")
    for r in q.itertuples():
        cases.append({"label": f"Excel test question for {r.Workflow_ID}", "expected": r.Workflow_ID,
                      "request": r.Test_Request, "inputs": {}, "check": r.What_To_Check})
    extra = ROOT / "examples" / "requests.json"
    if extra.exists():
        for c in json.loads(extra.read_text(encoding="utf-8")):
            cases.append({"label": c["label"], "expected": c.get("expected"), "request": c["request"],
                          "inputs": c.get("inputs", {}), "check": c.get("check", "")})
    results, md = [], ["# Demo results\n", f"LLM mode: `{agent.llm.mode}`\n"]
    for i, c in enumerate(cases, 1):
        resp = agent.handle(c["request"], c["inputs"])
        got = resp.selection.workflow_id
        ok = c["expected"] is None or got == c["expected"]
        results.append({"case": i, "label": c["label"], "expected_workflow": c["expected"], "selected_workflow": got,
                        "routing_correct": ok, **resp.to_dict()})
        md += [f"\n## {i}. {c['label']}\n", f"*Checks:* {c['check']}\n" if c["check"] else "",
               "```text", render(resp), "```"]
        print(f"{i:>2}. {c['label'][:58]:<58} -> {got or '-':<6} {resp.result.status if resp.result else 'clarify':<12}"
              f"{'' if ok else '  ROUTING MISMATCH (expected ' + str(c['expected']) + ')'}")
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "demo_results.json").write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")
    (out_dir / "demo_report.md").write_text("\n".join(md), encoding="utf-8")
    bad = [r for r in results if not r["routing_correct"]]
    print(f"\n{len(results)} cases run, {len(results) - len(bad)} routed as expected. "
          f"Wrote {out_dir.relative_to(ROOT) if out_dir.is_relative_to(ROOT) else out_dir}/demo_results.json and demo_report.md")
    return results


def main(argv=None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    p = argparse.ArgumentParser(description="AI Agent Workflow Automation")
    p.add_argument("request", nargs="?", help="Natural-language request")
    p.add_argument("--input", "-i", action="append", default=[], metavar="KEY=VALUE", help="explicit workflow input")
    p.add_argument("--inputs-json", help="explicit inputs as a JSON object")
    p.add_argument("--file", help="data file to process (CSV/XLSX)")
    p.add_argument("--workflow", help="force a workflow id instead of routing (e.g. WF003)")
    p.add_argument("--json", action="store_true", help="print machine-readable JSON")
    p.add_argument("--list", action="store_true", help="list workflows loaded from the Excel file")
    p.add_argument("--demo", action="store_true", help="run all demo cases and write outputs/")
    a = p.parse_args(argv)

    agent = WorkflowAgent()
    if a.list:
        for w in agent.catalog.all():
            impl = "implemented" if registry.get_spec(w.workflow_id) else "NOT IMPLEMENTED"
            print(f"{w.workflow_id}  {w.workflow_name:<32} {impl}  | steps: {' > '.join(w.steps)}")
        return 0
    if a.demo:
        results = run_demo(agent, OUTPUT_DIR)
        return 0 if all(r["routing_correct"] for r in results) else 1
    if not a.request:
        p.error("provide a request, or use --list / --demo")
    inputs = json.loads(a.inputs_json) if a.inputs_json else {}
    for kv in a.input:
        k, _, v = kv.partition("=")
        inputs[k.strip()] = v.strip()
    request = a.request + (f" {a.file}" if a.file else "")
    resp = agent.handle(request, inputs, workflow_id=a.workflow)
    print(json.dumps(resp.to_dict(), indent=2, default=str) if a.json else render(resp))
    return 0 if resp.result and resp.result.status in ("success", "escalated") else 2


if __name__ == "__main__":
    raise SystemExit(main())

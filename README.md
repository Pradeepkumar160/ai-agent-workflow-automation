# AI Agent Workflow Automation

A reusable Python agent that turns the **10 business workflows in an Excel file** into executable, traceable workflows.
A user types a request; the agent **selects the workflow, executes its steps through tools, applies the decision rules and
error handling, and returns the result** along with the workflow chosen and every step executed.

```
User request
     |
     v
 WorkflowAgent ──► Router (LLM, or lexical fallback) ──► Selected workflow (+ confidence, alternatives)
     |                         ▲
     |                         └── Workflow catalog  ◄── data/AI_Agent_Workflow_Assessment.xlsx  (source of truth)
     v
 Input extraction (per-workflow InputSpec patterns / LLM) ─► defaults ─► required-input check ─► ask user if missing
     |
     v
 Generic WorkflowEngine ──► workflow plugin (app/workflows/wfNNN_*.py)
     |                           │  steps are labelled from the Excel "Steps" cell
     |                           └─► ctx.call("tool", ...) ──► Tool registry (csv_reader, calculator, llm, order_api, ...)
     v                                                        each call traced: args, outcome, retries, duration
 Conditions / decisions / errors  (needs_input · escalated · failed · retries · LLM fallback)
     |
     v
 RunResult: workflow, step trace, tool calls, status, summary, structured data, output files
```

## Quick start

```bash
python -m venv .venv
.venv\Scripts\Activate.ps1          # Windows PowerShell      (macOS/Linux: source .venv/bin/activate)
pip install -r requirements.txt
copy .env.example .env              # optional: add OPENAI_API_KEY    (macOS/Linux: cp)
```

```bash
python -m app.cli "Which products need restocking?"     # single request
python -m app.cli --demo                                # all 10 Excel test questions + edge cases -> outputs/
streamlit run streamlit_app.py                          # UI for the demo
pytest -q                                               # 60 tests
```

**LLM vs offline mode.** With `OPENAI_API_KEY` set (any OpenAI-compatible endpoint via `OPENAI_BASE_URL`) the LLM does workflow
routing, input extraction, product copy (WF004), campaign messaging (WF007), keyword intent (WF008) and recommendations (WF010).
Every LLM output is schema-checked; on a missing key, outage, or bad output the same step falls back to a deterministic
implementation and the trace says so (`offline fallback used (...)`). The app therefore always runs, and tests need no network.

## The 10 workflows

| ID | Workflow | Decision logic implemented (from Excel) | Tools used |
|---|---|---|---|
| WF001 | Inventory Restock Check | restock if `current_stock < minimum_stock`; reorder qty = 2 x min − stock (configurable) | csv_reader, data_validation, calculator |
| WF002 | Product Price Validation | match by normalised SKU; flag when \|vendor−internal\|/internal **> 10%** (threshold from request, e.g. "15%") | csv_reader, calculator |
| WF003 | Vendor File Processing | detect/normalise columns (aliases); rows missing SKU or name are invalid; writes cleaned + invalid-row CSVs | csv_reader / excel_parser, data_validation, reporting |
| WF004 | Product Description Generator | missing attributes are **marked, never invented**; length-validated SEO title/meta | llm, text_validation |
| WF005 | Customer Order Status | validate ID/email; **no order → ask for another identifier**; shipment/tracking only when available | order_api, shipment_lookup (simulated, with retries) |
| WF006 | Duplicate Product Detection | exact normalised SKU = **definite**; similar names + attributes = **possible**; grouped with confidence | csv_reader, pairwise_similarity |
| WF007 | Marketing Campaign Brief | **goal or dates missing → ask before generating**; objective, messaging, channels, timeline, checklist | product_data_reader, llm |
| WF008 | SEO Keyword Classification | dedupe; 4 intents (LLM output validated, repaired by rules); category mapping; priority; CSV export | csv_reader, llm, reporting |
| WF009 | Employee Task Assignment | rank by skill coverage + free capacity; ineligible if no capacity/skills; **escalate if nobody suitable** | csv_reader, ranking_logic |
| WF010 | Workflow Performance Report | **flag failure rate > 10% or avg time > threshold**; frequent errors, slow steps, recommendations | csv_reader, calculator, llm, reporting |

Mock data lives in `data/mock/` (inventory, products, vendor files, catalog, orders, shipments, keywords, employees, execution logs).
Outputs of a full run (human-readable `demo_report.md`, machine-readable `demo_results.json`, and exported CSV/JSON files) are in `outputs/`.

> **Note on two Excel test questions.** "Create a campaign brief for the new collection." (WF007) has no goal/dates and "Assign this urgent task…"
> (WF009) has no task description. The Excel decision logic says to request missing inputs, so the agent asks. The demo also runs fully-specified
> versions of both so the complete outputs are shown.

## Example

```
$ python -m app.cli "Which products need restocking?"
Selected Workflow: WF001 - Inventory Restock Check
Steps Executed:
  1. [OK] Load inventory ... tools: csv_reader, data_validation
  2. [OK] compare current stock with minimum threshold
  3. [OK] identify low-stock products
  4. [OK] calculate reorder quantity ... tools: calculator
  5. [OK] generate restock list
Status: SUCCESS
Result:
4 of 9 products need restocking:
- SKU-006 Laptop Stand: stock 0 < min 5 -> reorder 10 ...
```

## Design decisions (and why)

* **Plugins, not 10 chatbots.** The engine, router, extractor, CLI and UI contain no workflow-specific code. A workflow is one decorated function in
  its own file. Excel supplies names, triggers, steps and decision text; steps in the trace are labelled from the Excel cell, so docs and behaviour stay in sync.
* **Adding an 11th workflow = 1 Excel row + 1 file** (`docs/ADDING_A_WORKFLOW.md`; proven by a test). If an Excel row has no plugin yet the run returns `not_implemented` cleanly.
* **Tools are a registry** (`@tool`). Workflows call tools by name through `ctx.call`, which records arguments, result summary, duration and retry attempts. Transient tool failures are retried.
* **Routing is LLM-first with a deterministic fallback.** The LLM sees the Excel catalog and its answer is validated against it. The fallback is TF-IDF over all Excel columns
  with light stemming. Weak/ambiguous requests produce a clarification question instead of a guess.
* **Statuses are explicit:** `success`, `needs_input` (missing/invalid input, asks the user), `escalated` (WF009 decision), `failed` (data/tool error with trace), `not_implemented`.
* **No LangGraph/LangChain.** The control flow is a short linear pipeline with branching inside plugins; a small explicit engine is easier to test, explain and extend than a graph framework for this scope.
  The tool registry could be exposed to an OpenAI-style tool-calling loop or wrapped as LangGraph nodes without changing plugins.
* **Honest limits:** APIs (orders/shipments) are simulated over CSV files; the offline intent classifier and copy templates are heuristic (the LLM path is the quality path);
  reorder quantity "2 x minimum" is an assumption (Excel only says "suggested reorder quantity"), exposed as `reorder_multiplier`.

## Project layout

```
app/
  agent/        router.py (selection) · extract.py (inputs from text) · agent.py (orchestration)
  core/         engine.py (generic runner) · registry.py (@workflow plugins) · tools.py (@tool) · context.py (tracing)
  workflow/     loader.py / registry.py / schema.py - Excel -> WorkflowDefinition
  workflows/    wf001_... wf010_...  (one plugin per workflow, auto-discovered)
  tools/        reusable tools (data, calculator, text, api, ranking, reporting, llm)
  llm.py · llm_offline.py · cli.py · formatting.py · config.py
data/           AI_Agent_Workflow_Assessment.xlsx · mock/
examples/requests.json   extra demo requests (edge cases)      outputs/   results of the demo run
tests/          60 tests (routing, all workflows, decision boundaries, errors, retries, LLM fallback, 11th workflow, UI/CLI)
docs/           ADDING_A_WORKFLOW.md · LOOM_SCRIPT.md
```

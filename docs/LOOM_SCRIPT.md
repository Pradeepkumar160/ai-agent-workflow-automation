# Loom walkthrough checklist (~8-10 min)

1. **Problem + architecture (1 min)** - show the diagram in README; "Excel is the source of truth, plugins hold logic, engine/router are generic".
2. **Excel processing (1 min)** - open the workbook, run `python -m app.cli --list`; point out steps come straight from the Excel cells.
3. **Workflow selection (1.5 min)** - Streamlit UI -> pick an Excel test question; show selected workflow, confidence, alternatives, routing method (LLM vs lexical). Type a vague request ("hello there") -> clarification instead of guessing.
4. **Execution + tools (2 min)** - run "Which products need restocking?"; walk the step list and per-step tool calls; show the JSON trace expander.
5. **Conditions and errors (2 min)** - WF005 `ORD-9999` (ask for another identifier); WF007 without dates (asks for them); WF009 escalation; WF003 with a missing file (clean failure with trace); WF002 boundary (exactly 10% is not flagged).
6. **Run everything (1 min)** - `python -m app.cli --demo`, then `pytest -q` (60 tests).
7. **11th workflow (1.5 min)** - walk docs/ADDING_A_WORKFLOW.md: 1 Excel row + 1 plugin file; mention tests/test_engine.py proves it.
8. **Decisions (1 min)** - plugin registry vs 10 chatbots; LLM with validated fallback; why no LangGraph; trade-offs (mock data, heuristic offline classifier).

Tip: set `OPENAI_API_KEY` in `.env` before recording to show `LLM mode: llm:gpt-4o-mini` and LLM routing.

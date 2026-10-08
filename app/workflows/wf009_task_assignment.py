"""WF009 Employee Task Assignment."""
import re

from app.config import mock
from app.core.errors import NeedsInput
from app.core.registry import InputSpec, workflow

PRIORITY_RE = r"\b(urgent|critical|high|medium|normal|low)(?:[ -]priority)?\b"


@workflow("WF009", inputs=[
    InputSpec("task_description", "Task description", required=True,
              pattern=r"(?:task|ticket)\s*[:=]\s*([^;\n]+?)(?:;|\n|$)",
              question="What is the task? Please describe it (and optionally the skills needed)."),
    InputSpec("required_skills", "Required skills (list)", kind="list"),
    InputSpec("priority", "Priority", default="normal", pattern=PRIORITY_RE),
    InputSpec("deadline", "Deadline", pattern=r"(?:by|before|due(?: on)?)\s+([A-Za-z0-9 ,/-]+?)(?=[.;]|$)"),
    InputSpec("role_filter", "Role to consider (e.g. developer)", pattern=r"\b(developer|engineer|designer|analyst|qa)\b"),
    InputSpec("employees_path", "Employee data", default=mock("employees.csv"), kind="file", primary=True),
])
def run(ctx):
    inp = ctx.inputs
    with ctx.step(0):  # Understand task requirements
        emp = ctx.call("csv_reader", path=inp["employees_path"])
        ctx.call("data_validation", df=emp, required_columns=["employee_id", "name", "skills", "current_workload", "capacity"])
        emp = emp.fillna("")
        vocab = {s.strip().lower() for cell in emp["skills"] for s in str(cell).split(";") if s.strip()}
        req = inp.get("required_skills")
        if isinstance(req, str):
            req = [s for s in re.split(r"[;,]", req) if s.strip()]
        text = str(inp["task_description"]).lower()
        required = [s.strip().lower() for s in req] if req else sorted(s for s in vocab if re.search(rf"\b{re.escape(s)}\b", text))
        if not required:
            raise NeedsInput("I couldn't tell which skills this task needs. Please list the required skills. "
                             f"Skills on the team: {', '.join(sorted(vocab))}.", ["required_skills"])
        priority = str(inp["priority"]).lower()
        ctx.note(f"required skills: {required}; priority: {priority}")

    with ctx.step(1):  # Compare employee skills
        role = (inp.get("role_filter") or "").lower()
        pool = emp[emp["role"].str.lower().str.contains(role, na=False)] if role and "role" in emp.columns else emp
        if pool.empty:
            pool = emp
            ctx.note(f"no employee matches role '{role}', considering everyone")
        cands = []
        for r in pool.to_dict("records"):
            skills = {s.strip().lower() for s in str(r["skills"]).split(";") if s.strip()}
            matched = [s for s in required if s in skills]
            cands.append({"employee_id": r["employee_id"], "name": r["name"], "role": r.get("role", ""),
                          "matched_skills": matched, "skill_coverage": round(len(matched) / len(required), 3)})

    with ctx.step(2):  # Check current workload
        by_id = {r["employee_id"]: r for r in pool.to_dict("records")}
        for c in cands:
            row = by_id[c["employee_id"]]
            cap, load = float(row["capacity"]), float(row["current_workload"])
            c["free_capacity"] = max(cap - load, 0)
            c["availability"] = round(c["free_capacity"] / cap, 3) if cap else 0.0

    with ctx.step(3):  # Rank candidates   (urgent tasks weigh availability more)
        w_skill, w_avail = (0.5, 0.5) if priority in ("urgent", "critical") else (0.65, 0.35)
        for c in cands:
            c["score"] = round(w_skill * c["skill_coverage"] + w_avail * c["availability"], 4)
            c["eligible"] = c["free_capacity"] > 0 and c["skill_coverage"] >= 0.5
            c["note"] = ("eligible" if c["eligible"] else
                         "no free capacity" if c["free_capacity"] <= 0 else "insufficient skill match")
        ranked = ctx.call("ranking_logic", candidates=cands, key="score")

    with ctx.step(4):  # Select employee   (escalate if nobody is suitable)
        eligible = [c for c in ranked if c["eligible"]]
        chosen = eligible[0] if eligible else None

    with ctx.step(5):  # Generate assignment summary
        task = str(inp["task_description"])
        if not chosen:
            summary = (f"ESCALATE: no suitable employee for '{task}' (needs {', '.join(required)}). "
                       "Closest candidates: " + "; ".join(f"{c['name']} ({c['note']})" for c in ranked[:3]) +
                       ". Please escalate to the manager.")
            return {"status": "escalated", "summary": summary,
                    "data": {"assigned": False, "required_skills": required, "ranked_candidates": ranked}}
        reason = (f"{chosen['name']} covers {len(chosen['matched_skills'])}/{len(required)} required skills "
                  f"({', '.join(chosen['matched_skills'])}) and has {chosen['free_capacity']:g} free capacity "
                  f"slots ({chosen['availability']:.0%} available); score {chosen['score']}.")
        summary = (f"Recommended: {chosen['name']} ({chosen['employee_id']}).\nReason: {reason}\n"
                   f"Task: {task}\nPriority: {priority}\nDeadline: {inp.get('deadline') or 'Not specified'}\n"
                   f"Runners-up: " + (", ".join(f"{c['name']} ({c['score']})" for c in eligible[1:3]) or "none"))
    return {"summary": summary, "data": {"assigned": True, "employee": chosen["name"], "employee_id": chosen["employee_id"],
            "reason": reason, "priority": priority, "deadline": inp.get("deadline"), "task": task,
            "required_skills": required, "ranked_candidates": ranked}}

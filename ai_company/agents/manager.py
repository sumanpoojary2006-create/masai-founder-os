"""Manager agent that classifies tasks into departments."""

import json

try:
    from ai_company.llm import call_llm
    from ai_company.utils.prompts import manager_prompt
except ImportError:
    from llm import call_llm
    from utils.prompts import manager_prompt


class ManagerAgent:
    """Decides which worker agent should handle a task."""

    valid_departments = {"sales", "ops", "curriculum", "accounts", "tech"}
    heuristic_keywords = {
        "sales": {
            "lead": 2,
            "leads": 2,
            "admission": 2,
            "admissions": 2,
            "counseling": 2,
            "conversion": 2,
            "enroll": 1,
            "enrollment": 1,
            "outreach": 2,
            "follow-up": 2,
            "follow up": 2,
            "webinar": 2,
        },
        "ops": {
            "ops": 2,
            "operation": 2,
            "operations": 2,
            "batch": 2,
            "cohort": 2,
            "schedule": 1,
            "onboarding": 2,
            "attendance": 1,
            "mentor": 1,
            "handoff": 1,
            "process": 2,
            "escalation": 2,
        },
        "curriculum": {
            "curriculum": 3,
            "lesson": 2,
            "module": 2,
            "assignment": 2,
            "assessment": 3,
            "learning": 2,
            "syllabus": 3,
            "content": 1,
            "student feedback": 2,
            "pedagogy": 3,
            "coaching": 1,
        },
        "accounts": {
            "account": 2,
            "accounts": 2,
            "fee": 3,
            "fees": 3,
            "refund": 4,
            "payment": 4,
            "invoice": 4,
            "billing": 4,
            "collection": 3,
            "finance": 3,
            "reconcile": 3,
            "extension": 2,
            "emi": 3,
        },
        "tech": {
            "bug": 3,
            "dashboard": 2,
            "platform": 3,
            "app": 1,
            "website": 2,
            "login": 2,
            "slow": 2,
            "error": 2,
            "tech": 2,
            "feature": 2,
            "product": 2,
            "engineering": 3,
            "submission": 2,
            "api": 2,
        },
    }

    heuristic_priority = ["accounts", "tech", "curriculum", "sales", "ops"]

    def _score_departments(self, task: str) -> dict:
        """Compute keyword scores for each department."""
        lowered = task.lower()
        scores = {department: 0 for department in self.valid_departments}
        for department, keywords in self.heuristic_keywords.items():
            for keyword, weight in keywords.items():
                if keyword in lowered:
                    scores[department] += weight
        return scores

    def _strong_signal_department(self, task: str) -> str:
        """Return a deterministic department for obvious operational workflows."""
        lowered = task.lower()

        if "refund" in lowered or any(word in lowered for word in ("invoice", "billing", "emi", "payment")):
            return "accounts"

        if any(word in lowered for word in ("webinar", "lead", "leads", "admission", "admissions", "counselor", "counselling")):
            return "sales"

        if any(word in lowered for word in ("onboarding", "orientation", "cohort", "batch", "mentor coordination")):
            return "ops"

        if any(word in lowered for word in ("study plan", "learning resources", "curriculum", "module", "assessment", "syllabus")):
            return "curriculum"

        if any(word in lowered for word in ("bug", "dashboard", "platform", "login", "issue has been fixed", "deployed", "technical")):
            return "tech"

        return ""

    def _infer_department(self, task: str) -> str:
        """Use simple keywords when the LLM response is unavailable."""
        strong_match = self._strong_signal_department(task)
        if strong_match:
            return strong_match

        scores = self._score_departments(task)

        best_department = max(
            self.heuristic_priority,
            key=lambda department: (scores[department], -self.heuristic_priority.index(department)),
        )
        if scores[best_department] == 0:
            return "ops"
        return best_department

    def _fallback_reason(self, department: str) -> str:
        """Return a short explanation when JSON parsing fails."""
        fallback_map = {
            "sales": "This request is about admissions, conversion, outreach, or lead handling.",
            "ops": "This request is about execution, coordination, process design, or operations.",
            "curriculum": "This request is about course quality, content, assessments, or pedagogy.",
            "accounts": "This request is about fees, refunds, collections, invoicing, or reconciliation.",
            "tech": "This request is about the platform, bugs, tools, product, or engineering work.",
        }
        return fallback_map.get(department, "This task best fits the ops team.")

    def route(self, task: str) -> dict:
        """Return the selected department plus a short routing reason."""
        strong_match = self._strong_signal_department(task)
        if strong_match:
            return {
                "department": strong_match,
                "reason": self._fallback_reason(strong_match),
                "raw_decision": f"heuristic:{strong_match}",
            }

        prompt = manager_prompt(task)
        raw_decision = call_llm(prompt).strip()

        try:
            parsed = json.loads(raw_decision)
            department = str(parsed.get("department", "")).strip().lower()
            reason = str(parsed.get("reason", "")).strip()
        except json.JSONDecodeError:
            department = ""
            reason = ""

        if department not in self.valid_departments:
            lowered = raw_decision.lower()
            for candidate in self.valid_departments:
                if candidate in lowered:
                    department = candidate
                    break

        if department not in self.valid_departments:
            department = self._infer_department(task)

        scores = self._score_departments(task)
        heuristic_department = self._infer_department(task)
        top_score = scores.get(heuristic_department, 0)
        llm_score = scores.get(department, 0)
        if heuristic_department in self.valid_departments and top_score >= max(3, llm_score + 2):
            department = heuristic_department

        if not reason:
            reason = self._fallback_reason(department)

        return {
            "department": department,
            "reason": reason,
            "raw_decision": raw_decision,
        }

    def decide(self, task: str) -> str:
        """Return the best department for the given task."""
        return self.route(task)["department"]

"""Task routing logic for the simulator."""

from datetime import datetime

try:
    from ai_company.agents.accounts import AccountsAgent
    from ai_company.agents.curriculum import CurriculumAgent
    from ai_company.agents.manager import ManagerAgent
    from ai_company.agents.ops import OpsAgent
    from ai_company.agents.sales import SalesAgent
    from ai_company.agents.tech import TechAgent
    from ai_company.config import LOGGER
except ImportError:
    from agents.accounts import AccountsAgent
    from agents.curriculum import CurriculumAgent
    from agents.manager import ManagerAgent
    from agents.ops import OpsAgent
    from agents.sales import SalesAgent
    from agents.tech import TechAgent
    from config import LOGGER


class TaskRouter:
    """Routes tasks from the manager agent to worker agents."""

    def __init__(self) -> None:
        self.manager = ManagerAgent()
        self.workers = {
            "sales": SalesAgent(),
            "ops": OpsAgent(),
            "curriculum": CurriculumAgent(),
            "accounts": AccountsAgent(),
            "tech": TechAgent(),
        }
        self.department_profiles = {
            "sales": {
                "label": "Sales Team",
                "agent_title": "Sales Agent",
                "focus": "Admissions, conversion, outreach, and objection handling",
                "summary": "Prepared a sales-facing action plan to improve lead movement and conversions.",
            },
            "ops": {
                "label": "Ops Team",
                "agent_title": "Ops Agent",
                "focus": "Batch operations, student coordination, and execution design",
                "summary": "Turned the founder's request into an operational plan with clear owners and next steps.",
            },
            "curriculum": {
                "label": "Curriculum Team",
                "agent_title": "Curriculum Agent",
                "focus": "Learning design, assessments, and academic quality",
                "summary": "Analyzed the academic problem and recommended curriculum improvements.",
            },
            "accounts": {
                "label": "Accounts Team",
                "agent_title": "Accounts Agent",
                "focus": "Fees, refunds, invoices, collections, and financial communication",
                "summary": "Prepared a finance-aware response with payment, refund, or reconciliation guidance.",
            },
            "tech": {
                "label": "Tech Team",
                "agent_title": "Tech Agent",
                "focus": "Platform issues, product changes, internal tools, and engineering execution",
                "summary": "Translated the problem into a technical diagnosis and next implementation steps.",
            },
        }

    def handle_task(self, task: str) -> dict:
        """Send a task to the correct department and return the result."""
        routing = self.route_task(task)
        department = routing["department"]
        profile = self.department_profiles[department]

        LOGGER.info("Task routed to %s", department)
        response = self.execute_department_task(department, task)
        return {
            "task": task,
            "department": department,
            "department_label": profile["label"],
            "manager_reason": routing["reason"],
            "manager_raw_output": routing["raw_decision"],
            "response": response,
            "timestamp": datetime.utcnow().isoformat(timespec="seconds") + "Z",
            "workflow": [
                {
                    "stage": "founder",
                    "title": "Founder Desk",
                    "subtitle": "One-person company view",
                    "summary": "A Masai business request arrived and was handed to the manager agent.",
                },
                {
                    "stage": "manager",
                    "title": "Manager Agent",
                    "subtitle": "Cross-functional router",
                    "summary": f"Mapped the request to the {profile['label']}.",
                    "detail": routing["reason"],
                },
                {
                    "stage": "worker",
                    "title": profile["agent_title"],
                    "subtitle": profile["focus"],
                    "summary": profile["summary"],
                    "detail": response,
                },
            ],
        }

    def route_task(self, task: str, department_hint: str = "") -> dict:
        """Route a task to the best department, optionally honoring a valid hint."""
        if department_hint in self.workers:
            return {
                "department": department_hint,
                "reason": f"Founder manually assigned this task to the {self.department_profiles[department_hint]['label']}.",
                "raw_decision": department_hint,
            }
        return self.manager.route(task)

    def execute_department_task(
        self,
        department: str,
        task: str,
        priority: str = "normal",
        queue_depth: int = 0,
    ) -> str:
        """Run one task through a chosen department worker."""
        worker = self.workers.get(department, self.workers["ops"])
        workload_note = (
            f"Priority: {priority.title()}\n"
            f"Current department queue depth: {queue_depth}\n"
            f"Founder request:\n{task}"
        )
        return worker.process(workload_note)

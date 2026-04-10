"""Real-time company orchestration for Masai Founder OS."""

from __future__ import annotations

from collections import deque
from datetime import datetime
from threading import Condition, Lock, Thread
from time import perf_counter, sleep
from typing import Deque, Dict, List
from uuid import uuid4

try:
    from ai_company.config import APP_NAME, LOGGER, WORKFLOW_STEP_DELAY_SECONDS
    from ai_company.core.communications import EmailService
    from ai_company.core.database import Database
    from ai_company.core.memory import MemoryStore
    from ai_company.core.playbooks import OperationalPlaybooks
    from ai_company.core.router import TaskRouter
except ImportError:
    from config import APP_NAME, LOGGER, WORKFLOW_STEP_DELAY_SECONDS
    from core.communications import EmailService
    from core.database import Database
    from core.memory import MemoryStore
    from core.playbooks import OperationalPlaybooks
    from core.router import TaskRouter


PRIORITY_RANK = {
    "critical": 4,
    "high": 3,
    "normal": 2,
    "low": 1,
}

STATUS_ORDER = [
    "triage",
    "queued",
    "in_progress",
    "ceo_review",
    "completed",
    "failed",
]


def utc_now() -> str:
    """Return the current UTC timestamp."""
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"


class CompanyRuntime:
    """Manage live task intake, routing, execution, and workload tracking."""

    def __init__(self) -> None:
        self.router = TaskRouter()
        self.db = Database()
        self.db.init_schema()
        self.db.seed_if_empty()
        self.db.apply_demo_contact_overrides()
        self.db.clear_demo_request_data()
        self.email_service = EmailService()
        self.playbooks = OperationalPlaybooks(self.db, self.email_service)
        self.memory = MemoryStore()
        self._lock = Lock()
        self._condition = Condition(self._lock)
        self._task_counter = 0
        self.tasks: Dict[str, dict] = {}
        self.activity: Deque[dict] = deque(maxlen=300)
        self.departments = self._build_departments()
        self._load_persisted_tasks()
        self._start_department_workers()
        self._recover_open_tasks()

    def _build_departments(self) -> Dict[str, dict]:
        """Create workload settings for each department."""
        catalog = {
            "sales": {
                "capacity": 2,
                "label": "Sales Team",
                "focus": "Admissions, lead follow-up, and conversion",
                "sla_minutes": 20,
            },
            "ops": {
                "capacity": 2,
                "label": "Ops Team",
                "focus": "Cohort operations, execution, and coordination",
                "sla_minutes": 25,
            },
            "curriculum": {
                "capacity": 2,
                "label": "Curriculum Team",
                "focus": "Learning design, outcomes, and content quality",
                "sla_minutes": 40,
            },
            "accounts": {
                "capacity": 1,
                "label": "Accounts Team",
                "focus": "Fees, refunds, invoicing, and reconciliation",
                "sla_minutes": 15,
            },
            "tech": {
                "capacity": 2,
                "label": "Tech Team",
                "focus": "Platform issues, product requests, and engineering",
                "sla_minutes": 35,
            },
        }

        for department, profile in catalog.items():
            profile["queue"] = deque()
            profile["active_task_ids"] = set()
            profile["completed"] = 0
            profile["failed"] = 0
            profile["threads"] = []
            profile["cycle_seconds_total"] = 0.0
        return catalog

    def _load_persisted_tasks(self) -> None:
        """Load historical tasks and events from SQLite."""
        persisted = self.db.list_tasks()
        for task in persisted:
            task["events"] = self.db.list_task_events(task["id"])
            task["queue_position"] = task.get("queue_position")
            self.tasks[task["id"]] = task
            self._task_counter = max(self._task_counter, int(task["sequence"]))
            for event in task["events"]:
                self.activity.appendleft(
                    {
                        "task_id": task["id"],
                        "task_title": task["title"],
                        "department": task.get("department", ""),
                        **event,
                    }
                )

    def _recover_open_tasks(self) -> None:
        """Requeue open work after a restart so operations can continue."""
        open_statuses = {"triage", "queued", "in_progress", "ceo_review"}
        for task in sorted(self.tasks.values(), key=lambda item: item["sequence"]):
            if task["status"] not in open_statuses:
                continue
            if task.get("department"):
                task["status"] = "queued"
                task["assignee"] = "Recovered Queue"
                self.departments[task["department"]]["queue"].append(task["id"])
                self._sort_queue_locked(task["department"])
                self.db.save_task(task)
            else:
                Thread(target=self._triage_task, args=(task["id"], ""), daemon=True).start()

    def _start_department_workers(self) -> None:
        """Start background workers for each department queue."""
        for department, profile in self.departments.items():
            for worker_number in range(1, profile["capacity"] + 1):
                thread = Thread(
                    target=self._department_worker_loop,
                    args=(department, worker_number),
                    daemon=True,
                    name=f"{department}-worker-{worker_number}",
                )
                profile["threads"].append(thread)
                thread.start()

    def _record_event_locked(self, task_id: str, actor: str, stage: str, message: str) -> None:
        """Append a task-scoped event and a global activity entry."""
        task = self.tasks[task_id]
        event = {
            "timestamp": utc_now(),
            "actor": actor,
            "stage": stage,
            "message": message,
        }
        task["events"].append(event)
        task["updated_at"] = event["timestamp"]
        self.db.save_task_event(task_id, event)
        self.activity.appendleft(
            {
                "task_id": task_id,
                "task_title": task["title"],
                "department": task.get("department", ""),
                **event,
            }
        )

    def _sort_queue_locked(self, department: str) -> None:
        """Keep higher-priority tasks at the front of the queue."""
        profile = self.departments[department]
        ordered = sorted(
            profile["queue"],
            key=lambda task_id: (
                -PRIORITY_RANK.get(self.tasks[task_id]["priority"], 0),
                self.tasks[task_id]["sequence"],
            ),
        )
        profile["queue"] = deque(ordered)
        self._refresh_queue_positions_locked(department)

    def _refresh_queue_positions_locked(self, department: str) -> None:
        """Update queue position metadata for tasks waiting in one department."""
        for position, task_id in enumerate(self.departments[department]["queue"], start=1):
            self.tasks[task_id]["queue_position"] = position

    def _mark_failed_locked(self, task_id: str, error_message: str) -> None:
        """Mark a task as failed with a friendly status transition."""
        task = self.tasks[task_id]
        department = task.get("department")
        task["status"] = "failed"
        task["error"] = error_message
        task["queue_position"] = None
        task["completed_at"] = utc_now()
        task["cycle_seconds"] = 0.0
        task["data_effect"] = ""
        self._record_event_locked(task_id, "System", "failed", error_message)
        if department:
            self.departments[department]["failed"] += 1

    def _process_department_task(self, department: str, worker_number: int, task_id: str) -> None:
        """Run the department work for a queued task."""
        profile = self.departments[department]
        task = self.tasks[task_id]
        worker_name = f"{profile['label']} Worker {worker_number}"

        with self._condition:
            task["status"] = "in_progress"
            task["assignee"] = worker_name
            task["started_at"] = utc_now()
            task["queue_position"] = None
            self._record_event_locked(
                task_id,
                worker_name,
                "in_progress",
                f"Started working from the {profile['label']} queue.",
            )
            self.db.save_task(task)

        sleep(WORKFLOW_STEP_DELAY_SECONDS)
        start_time = perf_counter()
        response = self.router.execute_department_task(
            department=department,
            task=task["request"],
            priority=task["priority"],
            queue_depth=len(profile["queue"]),
        )

        failure_markers = (
            "openrouter api key not found",
            "openrouter rejected the api key",
            "configured openrouter model endpoint was not found",
            "openrouter rate-limited the request",
            "llm request failed",
            "invalid json response",
            "unexpected error while calling the language model",
            "401 client error",
            "404 client error",
        )
        if any(marker in response.lower() for marker in failure_markers):
            if self.playbooks.supports(department, task["request"]):
                response = (
                    "The practical automation completed using the deterministic workflow because the "
                    "language model response was unavailable."
                )
            else:
                with self._condition:
                    self._mark_failed_locked(task_id, response)
                    self.db.save_task(task)
                return

        cycle_seconds = perf_counter() - start_time
        playbook_result = self.playbooks.execute(department, task["request"], response, task_id)
        data_effect = str(playbook_result.get("summary", "No database action was applied."))
        with self._condition:
            task["status"] = "ceo_review"
            task["result"] = response
            task["cycle_seconds"] = round(cycle_seconds, 1)
            task["data_effect"] = data_effect
            self._record_event_locked(
                task_id,
                worker_name,
                "ceo_review",
                "Department output prepared and returned to the CEO for final review.",
            )
            self._record_event_locked(
                task_id,
                profile["label"],
                "data_update",
                data_effect,
            )
            for event in playbook_result.get("events", []):
                self._record_event_locked(
                    task_id,
                    str(event.get("actor", profile["label"])),
                    str(event.get("stage", "automation")),
                    str(event.get("message", "")),
                )
            self.db.save_task(task)

        sleep(WORKFLOW_STEP_DELAY_SECONDS / 2)
        with self._condition:
            task["status"] = "completed"
            task["completed_at"] = utc_now()
            task["queue_position"] = None
            self._record_event_locked(
                task_id,
                "CEO Agent",
                "completed",
                "Approved the department output and closed the task.",
            )
            profile["completed"] += 1
            profile["cycle_seconds_total"] += cycle_seconds
            entry = self.memory.add_entry(
                task=task["request"],
                response=response,
                department=department,
                route_reason=task.get("ceo_reason", ""),
            )
            self.db.save_memory_entry(entry)
            self.db.save_task(task)

    def _department_worker_loop(self, department: str, worker_number: int) -> None:
        """Continuously process queued work for one department."""
        while True:
            task_id = ""
            with self._condition:
                profile = self.departments[department]
                while not profile["queue"]:
                    self._condition.wait(timeout=0.5)
                task_id = profile["queue"].popleft()
                profile["active_task_ids"].add(task_id)
                self._refresh_queue_positions_locked(department)

            try:
                self._process_department_task(department, worker_number, task_id)
            finally:
                with self._condition:
                    self.departments[department]["active_task_ids"].discard(task_id)
                    self._condition.notify_all()

    def _triage_task(self, task_id: str, department_hint: str = "") -> None:
        """Run CEO routing asynchronously, then hand off to the department queue."""
        with self._condition:
            self._record_event_locked(task_id, "CEO Agent", "triage", "Reviewing the new task and selecting the best department.")

        sleep(WORKFLOW_STEP_DELAY_SECONDS)
        task = self.tasks[task_id]
        routing = self.router.route_task(task["request"], department_hint=department_hint)
        department = routing["department"]

        with self._condition:
            task["department"] = department
            task["department_label"] = self.departments[department]["label"]
            task["ceo_reason"] = routing["reason"]
            task["status"] = "queued"
            self.departments[department]["queue"].append(task_id)
            self._sort_queue_locked(department)
            self._record_event_locked(
                task_id,
                "CEO Agent",
                "queued",
                f"Assigned to the {self.departments[department]['label']} with priority {task['priority']}.",
            )
            self.db.save_task(task)
            self._condition.notify_all()

    def submit_task(self, title: str, request: str, priority: str = "normal", department_hint: str = "") -> dict:
        """Create a new live task and start asynchronous triage."""
        priority = priority if priority in PRIORITY_RANK else "normal"
        title = title.strip() or request.strip().split(".")[0][:80] or "New task"

        with self._condition:
            self._task_counter += 1
            task_id = uuid4().hex[:8]
            task = {
                "id": task_id,
                "sequence": self._task_counter,
                "title": title,
                "request": request.strip(),
                "priority": priority,
                "status": "triage",
                "department": "",
                "department_label": "CEO Triage",
                "ceo_reason": "",
                "result": "",
                "error": "",
                "assignee": "CEO Agent",
                "queue_position": None,
                "created_at": utc_now(),
                "updated_at": utc_now(),
                "started_at": "",
                "completed_at": "",
                "cycle_seconds": 0.0,
                "data_effect": "",
                "events": [],
            }
            self.tasks[task_id] = task
            self._record_event_locked(
                task_id,
                "Founder",
                "submitted",
                "Submitted a new company task to the CEO inbox.",
            )
            self.db.save_task(task)

        Thread(target=self._triage_task, args=(task_id, department_hint), daemon=True).start()
        return self.get_task(task_id)

    def update_priority(self, task_id: str, priority: str) -> dict:
        """Change the priority of a queued task and reorder the backlog."""
        if priority not in PRIORITY_RANK:
            raise ValueError("Invalid priority.")

        with self._condition:
            task = self.tasks.get(task_id)
            if not task:
                raise KeyError("Task not found.")
            task["priority"] = priority
            department = task.get("department")
            if department and task["status"] == "queued":
                self._sort_queue_locked(department)
            self._record_event_locked(
                task_id,
                "CEO Agent",
                "priority",
                f"Priority changed to {priority}.",
            )
            self.db.save_task(task)
            return self._serialize_task_locked(task)

    def retry_task(self, task_id: str) -> dict:
        """Retry a failed task by sending it back through CEO triage."""
        with self._condition:
            task = self.tasks.get(task_id)
            if not task:
                raise KeyError("Task not found.")
            if task["status"] != "failed":
                raise ValueError("Only failed tasks can be retried.")
            task["status"] = "triage"
            task["error"] = ""
            task["result"] = ""
            task["completed_at"] = ""
            task["started_at"] = ""
            task["department"] = ""
            task["department_label"] = "CEO Triage"
            task["ceo_reason"] = ""
            task["queue_position"] = None
            task["assignee"] = "CEO Agent"
            task["cycle_seconds"] = 0.0
            task["data_effect"] = ""
            self._record_event_locked(
                task_id,
                "CEO Agent",
                "retry",
                "Retry requested. Sending the task back through CEO triage.",
            )
            self.db.save_task(task)

        Thread(target=self._triage_task, args=(task_id, ""), daemon=True).start()
        return self.get_task(task_id)

    def _serialize_task_locked(self, task: dict) -> dict:
        """Create a JSON-safe view of a task."""
        return {
            "id": task["id"],
            "title": task["title"],
            "request": task["request"],
            "priority": task["priority"],
            "status": task["status"],
            "department": task["department"],
            "department_label": task["department_label"],
            "ceo_reason": task["ceo_reason"],
            "result": task["result"],
            "error": task["error"],
            "assignee": task["assignee"],
            "queue_position": task["queue_position"],
            "created_at": task["created_at"],
            "updated_at": task["updated_at"],
            "started_at": task["started_at"],
            "completed_at": task["completed_at"],
            "cycle_seconds": task["cycle_seconds"],
            "data_effect": task.get("data_effect", ""),
            "events": list(task["events"]),
        }

    def get_task(self, task_id: str) -> dict:
        """Return one task snapshot."""
        with self._condition:
            task = self.tasks.get(task_id)
            if not task:
                raise KeyError("Task not found.")
            return self._serialize_task_locked(task)

    def _department_snapshot_locked(self) -> List[dict]:
        """Summarize current workload by department."""
        snapshot = []
        for department, profile in self.departments.items():
            completed = profile["completed"]
            avg_cycle = 0.0
            if completed:
                avg_cycle = round(profile["cycle_seconds_total"] / completed, 1)
            snapshot.append(
                {
                    "id": department,
                    "label": profile["label"],
                    "focus": profile["focus"],
                    "capacity": profile["capacity"],
                    "active_count": len(profile["active_task_ids"]),
                    "queued_count": len(profile["queue"]),
                    "completed_count": profile["completed"],
                    "failed_count": profile["failed"],
                    "utilization": round(len(profile["active_task_ids"]) / profile["capacity"], 2),
                    "backlog_pressure": round(len(profile["queue"]) / max(profile["capacity"], 1), 2),
                    "avg_cycle_seconds": avg_cycle,
                    "active_task_ids": list(profile["active_task_ids"]),
                }
            )
        return snapshot

    def get_state(self) -> dict:
        """Return the full real-time company snapshot for the frontend."""
        with self._condition:
            tasks = [self._serialize_task_locked(task) for task in self.tasks.values()]
            tasks.sort(
                key=lambda task: (
                    STATUS_ORDER.index(task["status"]) if task["status"] in STATUS_ORDER else 99,
                    -PRIORITY_RANK.get(task["priority"], 0),
                    task["created_at"],
                )
            )
            departments = self._department_snapshot_locked()
            open_tasks = [task for task in tasks if task["status"] not in {"completed", "failed"}]
            completed_tasks = [task for task in tasks if task["status"] == "completed"]
            failed_tasks = [task for task in tasks if task["status"] == "failed"]
            avg_completion = 0.0
            if completed_tasks:
                durations = [task["cycle_seconds"] for task in completed_tasks if task["cycle_seconds"]]
                if durations:
                    avg_completion = round(sum(durations) / len(durations), 1)

            return {
                "company": {
                    "name": APP_NAME,
                    "ceo_name": "CEO Agent",
                    "tagline": "Real-time workload orchestration for a Masai-style company.",
                },
                "summary": {
                    "total_tasks": len(tasks),
                    "open_tasks": len(open_tasks),
                    "completed_tasks": len(completed_tasks),
                    "failed_tasks": len(failed_tasks),
                    "active_departments": sum(1 for department in departments if department["active_count"]),
                    "backlog_tasks": sum(department["queued_count"] for department in departments),
                    "avg_cycle_seconds": avg_completion,
                },
                "departments": departments,
                "tasks": tasks,
                "activity": list(self.activity),
                "memory": self.db.get_memory_entries(20),
                "records": self.db.get_data_snapshot(),
            }

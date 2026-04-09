"""Simple in-memory storage for tasks and responses."""

from datetime import datetime
from threading import Lock
from typing import Dict, List


class MemoryStore:
    """Stores simulator history in a Python list."""

    def __init__(self) -> None:
        self.history: List[Dict[str, str]] = []
        self._lock = Lock()

    def add_entry(
        self,
        task: str,
        response: str,
        department: str = "",
        route_reason: str = "",
    ) -> Dict[str, str]:
        """Save a task, response, and timestamp."""
        entry = {
            "task": task,
            "response": response,
            "timestamp": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        }
        if department:
            entry["department"] = department
        if route_reason:
            entry["route_reason"] = route_reason

        with self._lock:
            self.history.append(entry)
        return entry

    def get_history(self) -> List[Dict[str, str]]:
        """Return the full conversation history."""
        with self._lock:
            return list(self.history)

"""Persistence layer for Masai Founder OS.

Supports:
- SQLite for local development
- Postgres via DATABASE_URL for free cloud deployments
"""

from __future__ import annotations

import re
import sqlite3
import ssl
from datetime import datetime, timedelta
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

try:
    from ai_company.config import DATABASE_PATH, DATABASE_URL
except ImportError:
    from config import DATABASE_PATH, DATABASE_URL


def utc_now() -> str:
    """Return the current UTC timestamp."""
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"


class Database:
    """Database wrapper for company records and task history."""

    def __init__(self, path: Optional[str] = None, url: Optional[str] = None) -> None:
        self.url = (url or DATABASE_URL or "").strip()
        self.path = Path(path or DATABASE_PATH)
        self._lock = Lock()
        self.backend = "postgres" if self.url else "sqlite"
        self._conn = self._connect()
        if self.backend == "sqlite":
            self._conn.row_factory = sqlite3.Row

    def _connect(self):
        if self.backend == "postgres":
            import pg8000.dbapi

            parsed = urlparse(self.url)
            ssl_context = None
            if parsed.hostname not in {"localhost", "127.0.0.1"}:
                ssl_context = ssl.create_default_context()
            connection = pg8000.dbapi.connect(
                user=parsed.username or "",
                password=parsed.password or "",
                host=parsed.hostname or "localhost",
                port=parsed.port or 5432,
                database=(parsed.path or "/").lstrip("/"),
                ssl_context=ssl_context,
            )
            try:
                connection.autocommit = True
            except Exception:
                pass
            return connection
        return sqlite3.connect(self.path, check_same_thread=False)

    def _adapt_query(self, query: str) -> str:
        if self.backend == "postgres":
            return query.replace("?", "%s")
        return query

    def _fetch_rows(self, cursor) -> List[Dict[str, Any]]:
        if self.backend == "sqlite":
            return [dict(row) for row in cursor.fetchall()]
        columns = [column[0] for column in cursor.description] if cursor.description else []
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def _execute(self, query: str, params: tuple = ()):
        with self._lock:
            cursor = self._conn.cursor()
            try:
                cursor.execute(self._adapt_query(query), params)
                self._conn.commit()
                return cursor
            except Exception:
                self._conn.rollback()
                raise

    def _executemany(self, query: str, rows: List[tuple]) -> None:
        with self._lock:
            cursor = self._conn.cursor()
            try:
                cursor.executemany(self._adapt_query(query), rows)
                self._conn.commit()
            except Exception:
                self._conn.rollback()
                raise

    def _fetchall(self, query: str, params: tuple = ()) -> List[Dict[str, Any]]:
        with self._lock:
            cursor = self._conn.cursor()
            try:
                cursor.execute(self._adapt_query(query), params)
                return self._fetch_rows(cursor)
            except Exception:
                self._conn.rollback()
                raise

    def _fetchone(self, query: str, params: tuple = ()) -> Optional[Dict[str, Any]]:
        rows = self._fetchall(query, params)
        return rows[0] if rows else None

    def init_schema(self) -> None:
        """Create all required tables if they do not exist."""
        if self.backend == "postgres":
            statements = [
                """
                CREATE TABLE IF NOT EXISTS leads (
                id BIGSERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                email TEXT NOT NULL,
                program TEXT NOT NULL,
                source TEXT NOT NULL,
                city TEXT NOT NULL,
                status TEXT NOT NULL,
                owner TEXT NOT NULL,
                score INTEGER NOT NULL,
                last_contacted_at TEXT,
                notes TEXT DEFAULT ''
            )
                """,
                """
                CREATE TABLE IF NOT EXISTS cohorts (
                id BIGSERIAL PRIMARY KEY,
                code TEXT NOT NULL,
                program TEXT NOT NULL,
                city TEXT NOT NULL,
                start_date TEXT NOT NULL,
                status TEXT NOT NULL,
                capacity INTEGER NOT NULL,
                enrolled_count INTEGER NOT NULL,
                readiness_pct INTEGER NOT NULL,
                notes TEXT DEFAULT ''
            )
                """,
                """
                CREATE TABLE IF NOT EXISTS students (
                id BIGSERIAL PRIMARY KEY,
                student_code TEXT DEFAULT '',
                name TEXT NOT NULL,
                email TEXT NOT NULL,
                program TEXT NOT NULL,
                cohort_code TEXT NOT NULL,
                city TEXT NOT NULL,
                status TEXT NOT NULL,
                attendance_pct INTEGER NOT NULL,
                fees_due INTEGER NOT NULL,
                risk_level TEXT NOT NULL,
                notes TEXT DEFAULT ''
            )
                """,
                """
                CREATE TABLE IF NOT EXISTS payments (
                id BIGSERIAL PRIMARY KEY,
                student_email TEXT NOT NULL,
                amount_due INTEGER NOT NULL,
                amount_paid INTEGER NOT NULL,
                status TEXT NOT NULL,
                due_date TEXT NOT NULL,
                last_action_at TEXT,
                notes TEXT DEFAULT ''
            )
                """,
                """
                CREATE TABLE IF NOT EXISTS curriculum_modules (
                id BIGSERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                program TEXT NOT NULL,
                quality_score INTEGER NOT NULL,
                completion_pct INTEGER NOT NULL,
                review_status TEXT NOT NULL,
                last_reviewed_at TEXT,
                notes TEXT DEFAULT ''
            )
                """,
                """
                CREATE TABLE IF NOT EXISTS tech_incidents (
                id BIGSERIAL PRIMARY KEY,
                title TEXT NOT NULL,
                product_area TEXT NOT NULL,
                severity TEXT NOT NULL,
                status TEXT NOT NULL,
                owner TEXT NOT NULL,
                impacted_users INTEGER NOT NULL,
                opened_at TEXT NOT NULL,
                last_update_at TEXT NOT NULL,
                notes TEXT DEFAULT ''
            )
                """,
                """
                CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY,
                sequence INTEGER NOT NULL,
                title TEXT NOT NULL,
                request TEXT NOT NULL,
                priority TEXT NOT NULL,
                status TEXT NOT NULL,
                department TEXT,
                department_label TEXT,
                ceo_reason TEXT,
                result TEXT,
                error TEXT,
                assignee TEXT,
                queue_position INTEGER,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                started_at TEXT,
                completed_at TEXT,
                cycle_seconds DOUBLE PRECISION DEFAULT 0,
                data_effect TEXT DEFAULT ''
            )
                """,
                """
                CREATE TABLE IF NOT EXISTS task_events (
                id BIGSERIAL PRIMARY KEY,
                task_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                actor TEXT NOT NULL,
                stage TEXT NOT NULL,
                message TEXT NOT NULL
            )
                """,
                """
                CREATE TABLE IF NOT EXISTS memory_entries (
                id BIGSERIAL PRIMARY KEY,
                task TEXT NOT NULL,
                response TEXT NOT NULL,
                department TEXT,
                route_reason TEXT,
                timestamp TEXT NOT NULL
            )
                """,
                """
                CREATE TABLE IF NOT EXISTS email_outbox (
                id BIGSERIAL PRIMARY KEY,
                task_id TEXT,
                department TEXT NOT NULL,
                recipient_name TEXT NOT NULL,
                recipient_email TEXT NOT NULL,
                subject TEXT NOT NULL,
                body TEXT NOT NULL,
                status TEXT NOT NULL,
                delivery_note TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                sent_at TEXT DEFAULT ''
            )
                """,
                """
                CREATE TABLE IF NOT EXISTS refund_ledger (
                id BIGSERIAL PRIMARY KEY,
                payment_id BIGINT NOT NULL,
                student_email TEXT NOT NULL,
                amount INTEGER NOT NULL,
                currency TEXT NOT NULL,
                status TEXT NOT NULL,
                reason TEXT NOT NULL,
                note TEXT DEFAULT '',
                created_at TEXT NOT NULL
            )
                """,
            ]
            with self._lock:
                cursor = self._conn.cursor()
                try:
                    for statement in statements:
                        cursor.execute(statement)
                    cursor.execute("ALTER TABLE payments ADD COLUMN IF NOT EXISTS refunded_amount INTEGER DEFAULT 0")
                    cursor.execute("ALTER TABLE students ADD COLUMN IF NOT EXISTS student_code TEXT DEFAULT ''")
                    self._conn.commit()
                except Exception:
                    self._conn.rollback()
                    raise
            return

        schema = """
        CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            program TEXT NOT NULL,
            source TEXT NOT NULL,
            city TEXT NOT NULL,
            status TEXT NOT NULL,
            owner TEXT NOT NULL,
            score INTEGER NOT NULL,
            last_contacted_at TEXT,
            notes TEXT DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS cohorts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT NOT NULL,
            program TEXT NOT NULL,
            city TEXT NOT NULL,
            start_date TEXT NOT NULL,
            status TEXT NOT NULL,
            capacity INTEGER NOT NULL,
            enrolled_count INTEGER NOT NULL,
            readiness_pct INTEGER NOT NULL,
            notes TEXT DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_code TEXT DEFAULT '',
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            program TEXT NOT NULL,
            cohort_code TEXT NOT NULL,
            city TEXT NOT NULL,
            status TEXT NOT NULL,
            attendance_pct INTEGER NOT NULL,
            fees_due INTEGER NOT NULL,
            risk_level TEXT NOT NULL,
            notes TEXT DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_email TEXT NOT NULL,
            amount_due INTEGER NOT NULL,
            amount_paid INTEGER NOT NULL,
            status TEXT NOT NULL,
            due_date TEXT NOT NULL,
            last_action_at TEXT,
            notes TEXT DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS curriculum_modules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            program TEXT NOT NULL,
            quality_score INTEGER NOT NULL,
            completion_pct INTEGER NOT NULL,
            review_status TEXT NOT NULL,
            last_reviewed_at TEXT,
            notes TEXT DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS tech_incidents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            product_area TEXT NOT NULL,
            severity TEXT NOT NULL,
            status TEXT NOT NULL,
            owner TEXT NOT NULL,
            impacted_users INTEGER NOT NULL,
            opened_at TEXT NOT NULL,
            last_update_at TEXT NOT NULL,
            notes TEXT DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS tasks (
            id TEXT PRIMARY KEY,
            sequence INTEGER NOT NULL,
            title TEXT NOT NULL,
            request TEXT NOT NULL,
            priority TEXT NOT NULL,
            status TEXT NOT NULL,
            department TEXT,
            department_label TEXT,
            ceo_reason TEXT,
            result TEXT,
            error TEXT,
            assignee TEXT,
            queue_position INTEGER,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            started_at TEXT,
            completed_at TEXT,
            cycle_seconds REAL DEFAULT 0,
            data_effect TEXT DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS task_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            actor TEXT NOT NULL,
            stage TEXT NOT NULL,
            message TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS memory_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task TEXT NOT NULL,
            response TEXT NOT NULL,
            department TEXT,
            route_reason TEXT,
            timestamp TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS email_outbox (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id TEXT,
            department TEXT NOT NULL,
            recipient_name TEXT NOT NULL,
            recipient_email TEXT NOT NULL,
            subject TEXT NOT NULL,
            body TEXT NOT NULL,
            status TEXT NOT NULL,
            delivery_note TEXT DEFAULT '',
            created_at TEXT NOT NULL,
            sent_at TEXT DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS refund_ledger (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            payment_id INTEGER NOT NULL,
            student_email TEXT NOT NULL,
            amount INTEGER NOT NULL,
            currency TEXT NOT NULL,
            status TEXT NOT NULL,
            reason TEXT NOT NULL,
            note TEXT DEFAULT '',
            created_at TEXT NOT NULL
        );
        """
        with self._lock:
            self._conn.executescript(schema)
            try:
                self._conn.execute("ALTER TABLE payments ADD COLUMN refunded_amount INTEGER DEFAULT 0")
            except sqlite3.OperationalError:
                pass
            try:
                self._conn.execute("ALTER TABLE students ADD COLUMN student_code TEXT DEFAULT ''")
            except sqlite3.OperationalError:
                pass
            self._conn.commit()

    def seed_if_empty(self) -> None:
        """Seed realistic company data once."""
        existing = self._fetchone("SELECT COUNT(*) AS count FROM leads")
        if existing and existing["count"] > 0:
            return

        now = datetime.utcnow()
        lead_rows = [
            ("Aarav Shah", "suman.poojary2006@gmail.com", "Full Stack Web Development", "Weekend Webinar", "Bangalore", "new", "AI SDR 1", 82, None, "Asked about ISA and placement outcomes."),
            ("Diya Menon", "diya@sample.com", "Data Analytics", "Organic", "Mumbai", "counseled", "AI SDR 2", 74, utc_now(), "Interested in weekend-friendly learning schedule."),
            ("Rohan Gupta", "rohan@sample.com", "Backend Development", "Referral", "Delhi", "follow_up_due", "AI SDR 1", 68, (now - timedelta(days=2)).isoformat(timespec="seconds") + "Z", "Needs clarity on financing options."),
            ("Sneha Iyer", "sneha@sample.com", "Product Design", "Campus Event", "Chennai", "application_started", "AI SDR 3", 88, (now - timedelta(days=1)).isoformat(timespec="seconds") + "Z", "High intent lead, paused after counselor call."),
            ("Kabir Jain", "rahulajay34@gmail.com", "Full Stack Web Development", "Weekend Webinar", "Bangalore", "new", "AI SDR 2", 79, None, "Looking for cohort starting this month."),
        ]
        self._executemany(
            """
            INSERT INTO leads (name, email, program, source, city, status, owner, score, last_contacted_at, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            lead_rows,
        )

        cohort_rows = [
            ("FSW-BLR-APR", "Full Stack Web Development", "Bangalore", "2026-04-22", "preparing", 120, 93, 71, "Mentor allocation pending."),
            ("DA-MUM-APR", "Data Analytics", "Mumbai", "2026-04-28", "preparing", 90, 66, 64, "Assessment proctoring checklist incomplete."),
            ("BE-DEL-MAY", "Backend Development", "Delhi", "2026-05-05", "open_for_enrollment", 80, 34, 42, "Marketing requested stronger city outreach."),
        ]
        self._executemany(
            """
            INSERT INTO cohorts (code, program, city, start_date, status, capacity, enrolled_count, readiness_pct, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            cohort_rows,
        )

        student_rows = [
            ("s101", "Rahul", "rahulajay34@gmail.com", "Full Stack Web Development", "FSW-BLR-APR", "Bangalore", "active", 62, 25000, "high", "Attendance dropped after sprint 2."),
            ("s102", "Suman", "suman.poojary2006@gmail.com", "Data Analytics", "DA-MUM-APR", "Mumbai", "refund_requested", 0, 0, "medium", "Requested refund after financial-plan reconsideration."),
            ("s103", "Huzaifa", "huzaifasheikh7860123@gmail.com", "Product Design", "PD-BLR-MAY", "Bangalore", "active", 74, 0, "low", "Recently completed onboarding and payment confirmation."),
            ("s104", "Krishnan", "krishnan.parameswaran0111@gmail.com", "Full Stack Web Development", "FSW-BLR-APR", "Bangalore", "active", 84, 0, "low", "Recently completed onboarding and is ready for mentor allocation."),
            ("s105", "Amit Singh", "singh25nov@gmail.com", "Backend Development", "BE-DEL-MAY", "Delhi", "onboarding", 0, 30000, "medium", "Requested flexible payment structure."),
        ]
        self._executemany(
            """
            INSERT INTO students (student_code, name, email, program, cohort_code, city, status, attendance_pct, fees_due, risk_level, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            student_rows,
        )

        payment_rows = [
            ("rahulajay34@gmail.com", 25000, 95000, "overdue", "2026-04-03", (now - timedelta(days=4)).isoformat(timespec="seconds") + "Z", "Needs escalation.", 0),
            ("suman.poojary2006@gmail.com", 0, 45000, "refund_review", "2026-04-12", utc_now(), "Refund request awaiting accounts review.", 0),
            ("huzaifasheikh7860123@gmail.com", 0, 120000, "paid", "2026-04-10", utc_now(), "Full fee received and enrollment confirmed.", 0),
            ("krishnan.parameswaran0111@gmail.com", 0, 120000, "paid", "2026-04-10", utc_now(), "All installments cleared.", 0),
            ("singh25nov@gmail.com", 30000, 60000, "partial", "2026-04-14", (now - timedelta(days=1)).isoformat(timespec="seconds") + "Z", "Awaiting employer reimbursement.", 0),
        ]
        self._executemany(
            """
            INSERT INTO payments (student_email, amount_due, amount_paid, status, due_date, last_action_at, notes, refunded_amount)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            payment_rows,
        )

        module_rows = [
            ("JavaScript Foundations", "Full Stack Web Development", 71, 82, "stable", (now - timedelta(days=14)).isoformat(timespec="seconds") + "Z", "Cohort feedback mentions pacing issues."),
            ("SQL for Analytics", "Data Analytics", 78, 88, "stable", (now - timedelta(days=10)).isoformat(timespec="seconds") + "Z", "Needs more case studies."),
            ("Backend APIs", "Backend Development", 69, 73, "review_needed", (now - timedelta(days=20)).isoformat(timespec="seconds") + "Z", "Assessments too difficult for current cohort."),
            ("System Design Basics", "Backend Development", 74, 61, "stable", (now - timedelta(days=8)).isoformat(timespec="seconds") + "Z", "Drop in assessment accuracy last week."),
        ]
        self._executemany(
            """
            INSERT INTO curriculum_modules (name, program, quality_score, completion_pct, review_status, last_reviewed_at, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            module_rows,
        )

        incident_rows = [
            ("Student dashboard loading slowly during assignment submissions", "Student Dashboard", "high", "open", "AI Tech Lead", 420, (now - timedelta(hours=8)).isoformat(timespec="seconds") + "Z", utc_now(), "Spike observed after assignment upload release."),
            ("Mentor session attendance sync lag", "Ops Integrations", "medium", "monitoring", "AI Tech Lead", 130, (now - timedelta(days=1)).isoformat(timespec="seconds") + "Z", utc_now(), "Webhook delay reduced but not eliminated."),
            ("Payment receipt email not triggered for some learners", "Finance Automation", "medium", "open", "AI Tech Lead", 45, (now - timedelta(hours=5)).isoformat(timespec="seconds") + "Z", utc_now(), "Accounts requested manual audit."),
        ]
        self._executemany(
            """
            INSERT INTO tech_incidents (title, product_area, severity, status, owner, impacted_users, opened_at, last_update_at, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            incident_rows,
        )

    def apply_demo_contact_overrides(self) -> None:
        """Keep the demo roster stable so tasks can target learners by student code."""
        lead_overrides = [
            ("Aarav Shah", "suman.poojary2006@gmail.com", "new"),
            ("Kabir Jain", "rahulajay34@gmail.com", "new"),
        ]
        for name, email, status in lead_overrides:
            self._execute(
                "UPDATE leads SET email = ?, status = ?, last_contacted_at = NULL WHERE name = ?",
                (email, status, name),
            )

        student_directory = [
            {
                "student_code": "s101",
                "name": "Rahul",
                "email": "rahulajay34@gmail.com",
                "aliases": ("Rahul S", "Rahul", "Rahul Ajay"),
                "emails": ("rahul@masai.com", "rahulajay34@gmail.com"),
                "status": "active",
                "fees_due": 25000,
                "risk_level": "high",
                "payment": {"amount_due": 25000, "amount_paid": 95000, "status": "overdue", "note": "Needs escalation."},
            },
            {
                "student_code": "s102",
                "name": "Suman",
                "email": "suman.poojary2006@gmail.com",
                "aliases": ("Karan Patel", "Suman", "Suman Poojary"),
                "emails": ("karan@masai.com", "suman.poojary2006@gmail.com"),
                "status": "refund_requested",
                "fees_due": 0,
                "risk_level": "medium",
                "payment": {"amount_due": 0, "amount_paid": 45000, "status": "refund_review", "note": "Refund request awaiting accounts review."},
            },
            {
                "student_code": "s103",
                "name": "Huzaifa",
                "email": "huzaifasheikh7860123@gmail.com",
                "aliases": ("Ananya Das", "Huzaifa", "Huzaifa Sheikh"),
                "emails": ("ananya@masai.com", "huzaifasheikh7860123@gmail.com"),
                "status": "active",
                "fees_due": 0,
                "risk_level": "low",
                "payment": {"amount_due": 0, "amount_paid": 120000, "status": "paid", "note": "Full fee received and enrollment confirmed."},
            },
            {
                "student_code": "s104",
                "name": "Krishnan",
                "email": "krishnan.parameswaran0111@gmail.com",
                "aliases": ("Nikita Rao", "Krishnan", "Krishnan Parameswaran"),
                "emails": ("nikita@masai.com", "krishnan.parameswaran0111@gmail.com"),
                "status": "active",
                "fees_due": 0,
                "risk_level": "low",
                "payment": {"amount_due": 0, "amount_paid": 120000, "status": "paid", "note": "All installments cleared."},
            },
            {
                "student_code": "s105",
                "name": "Amit Singh",
                "email": "singh25nov@gmail.com",
                "aliases": ("Meera Nair", "Amit Singh"),
                "emails": ("meera@masai.com", "singh25nov@gmail.com"),
                "status": "onboarding",
                "fees_due": 30000,
                "risk_level": "medium",
                "payment": {"amount_due": 30000, "amount_paid": 60000, "status": "partial", "note": "Awaiting employer reimbursement."},
            },
        ]

        for student in student_directory:
            alias_placeholders = ",".join("?" for _ in student["aliases"])
            email_placeholders = ",".join("?" for _ in student["emails"])
            row = self._fetchone(
                f"""
                SELECT id
                FROM students
                WHERE student_code = ?
                   OR name IN ({alias_placeholders})
                   OR email IN ({email_placeholders})
                ORDER BY id ASC
                LIMIT 1
                """,
                (student["student_code"], *student["aliases"], *student["emails"]),
            )
            if not row:
                continue

            self._execute(
                """
                UPDATE students
                SET student_code = ?, name = ?, email = ?, status = ?, fees_due = ?, risk_level = ?
                WHERE id = ?
                """,
                (
                    student["student_code"],
                    student["name"],
                    student["email"],
                    student["status"],
                    student["fees_due"],
                    student["risk_level"],
                    row["id"],
                ),
            )

            payment = student["payment"]
            self._execute(
                f"""
                UPDATE payments
                SET student_email = ?, amount_due = ?, amount_paid = ?, status = ?, notes = ?
                WHERE student_email IN ({email_placeholders})
                """,
                (
                    student["email"],
                    payment["amount_due"],
                    payment["amount_paid"],
                    payment["status"],
                    payment["note"],
                    *student["emails"],
                ),
            )

    def clear_demo_request_data(self) -> None:
        """Reset request-driven history so the demo starts from a clean slate."""
        for table in ("task_events", "tasks", "memory_entries", "email_outbox", "refund_ledger"):
            self._execute(f"DELETE FROM {table}")

    def save_task(self, task: Dict[str, Any]) -> None:
        """Insert or update one task."""
        self._execute(
            """
            INSERT INTO tasks (
                id, sequence, title, request, priority, status, department, department_label,
                ceo_reason, result, error, assignee, queue_position, created_at, updated_at,
                started_at, completed_at, cycle_seconds, data_effect
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                sequence=excluded.sequence,
                title=excluded.title,
                request=excluded.request,
                priority=excluded.priority,
                status=excluded.status,
                department=excluded.department,
                department_label=excluded.department_label,
                ceo_reason=excluded.ceo_reason,
                result=excluded.result,
                error=excluded.error,
                assignee=excluded.assignee,
                queue_position=excluded.queue_position,
                created_at=excluded.created_at,
                updated_at=excluded.updated_at,
                started_at=excluded.started_at,
                completed_at=excluded.completed_at,
                cycle_seconds=excluded.cycle_seconds,
                data_effect=excluded.data_effect
            """,
            (
                task["id"],
                task["sequence"],
                task["title"],
                task["request"],
                task["priority"],
                task["status"],
                task["department"],
                task["department_label"],
                task["ceo_reason"],
                task["result"],
                task["error"],
                task["assignee"],
                task["queue_position"],
                task["created_at"],
                task["updated_at"],
                task["started_at"],
                task["completed_at"],
                task["cycle_seconds"],
                task.get("data_effect", ""),
            ),
        )

    def save_task_event(self, task_id: str, event: Dict[str, Any]) -> None:
        self._execute(
            """
            INSERT INTO task_events (task_id, timestamp, actor, stage, message)
            VALUES (?, ?, ?, ?, ?)
            """,
            (task_id, event["timestamp"], event["actor"], event["stage"], event["message"]),
        )

    def save_memory_entry(self, entry: Dict[str, Any]) -> None:
        self._execute(
            """
            INSERT INTO memory_entries (task, response, department, route_reason, timestamp)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                entry["task"],
                entry["response"],
                entry.get("department", ""),
                entry.get("route_reason", ""),
                entry["timestamp"],
            ),
        )

    def get_memory_entries(self, limit: int = 20) -> List[Dict[str, Any]]:
        return self._fetchall(
            """
            SELECT task, response, department, route_reason, timestamp
            FROM memory_entries
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        )

    def list_tasks(self) -> List[Dict[str, Any]]:
        return self._fetchall("SELECT * FROM tasks ORDER BY sequence ASC")

    def list_task_events(self, task_id: str) -> List[Dict[str, Any]]:
        return self._fetchall(
            """
            SELECT timestamp, actor, stage, message
            FROM task_events
            WHERE task_id = ?
            ORDER BY id ASC
            """,
            (task_id,),
        )

    def get_data_snapshot(self) -> Dict[str, List[Dict[str, Any]]]:
        return {
            "leads": self._fetchall(
                """
                SELECT name, city, source, status, score, owner, last_contacted_at
                FROM leads
                ORDER BY score DESC, id ASC
                LIMIT 8
                """
            ),
            "cohorts": self._fetchall(
                """
                SELECT code, program, city, start_date, status, readiness_pct, enrolled_count, capacity
                FROM cohorts
                ORDER BY start_date ASC
                LIMIT 6
                """
            ),
            "students": self._fetchall(
                """
                SELECT student_code, name, program, cohort_code, status, attendance_pct, fees_due, risk_level
                FROM students
                ORDER BY
                  CASE risk_level WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END,
                  fees_due DESC
                LIMIT 8
                """
            ),
            "payments": self._fetchall(
                """
                SELECT
                    students.student_code,
                    payments.student_email,
                    payments.amount_due,
                    payments.amount_paid,
                    payments.refunded_amount,
                    payments.status,
                    payments.due_date,
                    payments.last_action_at
                FROM payments
                LEFT JOIN students ON students.email = payments.student_email
                ORDER BY payments.amount_due DESC, payments.due_date ASC
                LIMIT 8
                """
            ),
            "modules": self._fetchall(
                """
                SELECT name, program, quality_score, completion_pct, review_status, last_reviewed_at
                FROM curriculum_modules
                ORDER BY quality_score ASC, completion_pct ASC
                LIMIT 8
                """
            ),
            "incidents": self._fetchall(
                """
                SELECT title, product_area, severity, status, owner, impacted_users, last_update_at
                FROM tech_incidents
                ORDER BY
                  CASE severity WHEN 'critical' THEN 1 WHEN 'high' THEN 2 WHEN 'medium' THEN 3 ELSE 4 END,
                  last_update_at DESC
                LIMIT 8
                """
            ),
            "emails": self._fetchall(
                """
                SELECT recipient_email, subject, status, department, created_at, sent_at
                FROM email_outbox
                ORDER BY id DESC
                LIMIT 8
                """
            ),
            "refunds": self._fetchall(
                """
                SELECT
                    students.student_code,
                    refund_ledger.student_email,
                    refund_ledger.amount,
                    refund_ledger.currency,
                    refund_ledger.status,
                    refund_ledger.created_at
                FROM refund_ledger
                LEFT JOIN students ON students.email = refund_ledger.student_email
                ORDER BY refund_ledger.id DESC
                LIMIT 8
                """
            ),
        }

    def _append_note(self, existing: str, addition: str) -> str:
        prefix = f"[{utc_now()}] {addition}"
        return f"{existing}\n{prefix}".strip() if existing else prefix

    def find_webinar_leads(self, city: str = "", limit: int = 5) -> List[Dict[str, Any]]:
        return self._fetchall(
            """
            SELECT id, name, email, city, program, status, source, notes, score
            FROM leads
            WHERE lower(source) LIKE '%webinar%'
              AND (? = '' OR city = ?)
              AND status IN ('new', 'follow_up_due', 'counseled', 'application_started')
            ORDER BY score DESC, id ASC
            LIMIT ?
            """,
            (city, city, limit),
        )

    def mark_lead_follow_up(self, lead_id: int, note: str, status: str) -> None:
        lead = self._fetchone("SELECT notes FROM leads WHERE id = ?", (lead_id,))
        existing_notes = lead["notes"] if lead else ""
        self._execute(
            """
            UPDATE leads
            SET status = ?, last_contacted_at = ?, notes = ?
            WHERE id = ?
            """,
            (status, utc_now(), self._append_note(existing_notes, note), lead_id),
        )

    def add_email_outbox_entry(
        self,
        task_id: str,
        department: str,
        recipient_name: str,
        recipient_email: str,
        subject: str,
        body: str,
        status: str,
        delivery_note: str,
        sent_at: str = "",
    ) -> None:
        self._execute(
            """
            INSERT INTO email_outbox (
                task_id, department, recipient_name, recipient_email, subject, body,
                status, delivery_note, created_at, sent_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (task_id, department, recipient_name, recipient_email, subject, body, status, delivery_note, utc_now(), sent_at),
        )

    def find_refund_candidate(self, task_request: str) -> Optional[Dict[str, Any]]:
        lowered = task_request.lower()
        code_match = re.search(r"\b(s\d{3})\b", lowered)
        rows = self._fetchall(
            """
            SELECT
                students.id AS student_id,
                students.student_code,
                students.name,
                students.email,
                students.program,
                students.status AS student_status,
                payments.id AS payment_id,
                payments.amount_due,
                payments.amount_paid,
                payments.refunded_amount,
                payments.status AS payment_status
            FROM students
            JOIN payments ON payments.student_email = students.email
            ORDER BY
                CASE students.status WHEN 'refund_requested' THEN 1 ELSE 2 END,
                CASE payments.status WHEN 'refund_review' THEN 1 WHEN 'partial' THEN 2 ELSE 3 END,
                payments.amount_paid DESC
            """
        )
        if code_match:
            requested_code = code_match.group(1)
            for row in rows:
                if (row.get("student_code") or "").lower() == requested_code:
                    return row

        for row in rows:
            if row["email"].lower() in lowered or row["name"].lower() in lowered:
                return row
        return rows[0] if rows else None

    def apply_refund(self, payment_id: int, student_email: str, student_id: int, amount: int, note: str) -> None:
        payment = self._fetchone("SELECT amount_paid, refunded_amount, notes FROM payments WHERE id = ?", (payment_id,))
        if not payment:
            return
        updated_paid = max(0, int(payment["amount_paid"]) - amount)
        updated_refunded = int(payment.get("refunded_amount") or 0) + amount
        self._execute(
            """
            UPDATE payments
            SET amount_paid = ?, refunded_amount = ?, status = ?, last_action_at = ?, notes = ?
            WHERE id = ?
            """,
            (updated_paid, updated_refunded, "refund_initiated", utc_now(), self._append_note(payment.get("notes", ""), note), payment_id),
        )
        student = self._fetchone("SELECT notes FROM students WHERE id = ?", (student_id,))
        student_notes = student["notes"] if student else ""
        self._execute(
            """
            UPDATE students
            SET status = ?, notes = ?
            WHERE id = ?
            """,
            ("refund_initiated", self._append_note(student_notes, f"Refund of INR {amount:,} initiated."), student_id),
        )

    def add_refund_ledger_entry(
        self,
        payment_id: int,
        student_email: str,
        amount: int,
        status: str,
        reason: str,
        note: str,
    ) -> None:
        self._execute(
            """
            INSERT INTO refund_ledger (payment_id, student_email, amount, currency, status, reason, note, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (payment_id, student_email, amount, "INR", status, reason, note, utc_now()),
        )

    def apply_department_action(self, department: str, task_request: str, ai_response: str) -> str:
        lowered = task_request.lower()

        if department == "sales":
            lead = self._fetchone(
                """
                SELECT * FROM leads
                ORDER BY
                  CASE status
                    WHEN 'follow_up_due' THEN 1
                    WHEN 'new' THEN 2
                    WHEN 'counseled' THEN 3
                    ELSE 4
                  END,
                  score DESC
                LIMIT 1
                """
            )
            if not lead:
                return "No lead record was available to update."
            new_status = "follow_up_scheduled"
            if "application" in lowered or "apply" in lowered:
                new_status = "application_review"
            note = self._append_note(lead["notes"], f"Sales action: {ai_response[:140]}")
            self._execute(
                """
                UPDATE leads
                SET status = ?, last_contacted_at = ?, notes = ?
                WHERE id = ?
                """,
                (new_status, utc_now(), note, lead["id"]),
            )
            return f"Updated lead {lead['name']} ({lead['city']}) to {new_status} and logged a new sales follow-up."

        if department == "ops":
            city = "Bangalore" if "bangalore" in lowered else None
            cohort = self._fetchone(
                """
                SELECT * FROM cohorts
                WHERE (? IS NULL OR city = ?)
                ORDER BY readiness_pct ASC, start_date ASC
                LIMIT 1
                """,
                (city, city),
            )
            if not cohort:
                return "No cohort record was available to update."
            readiness = min(100, cohort["readiness_pct"] + 8)
            status = "onboarding_in_progress" if readiness >= 75 else cohort["status"]
            note = self._append_note(cohort["notes"], f"Ops action: {ai_response[:140]}")
            self._execute(
                """
                UPDATE cohorts
                SET readiness_pct = ?, status = ?, notes = ?
                WHERE id = ?
                """,
                (readiness, status, note, cohort["id"]),
            )
            return f"Moved cohort {cohort['code']} to {readiness}% readiness and updated the ops plan."

        if department == "curriculum":
            module_name = "JavaScript Foundations" if "javascript" in lowered else None
            module = self._fetchone(
                """
                SELECT * FROM curriculum_modules
                WHERE (? IS NULL OR name = ?)
                ORDER BY quality_score ASC, completion_pct ASC
                LIMIT 1
                """,
                (module_name, module_name),
            )
            if not module:
                return "No curriculum module record was available to update."
            score = min(100, module["quality_score"] + 3)
            note = self._append_note(module["notes"], f"Curriculum action: {ai_response[:140]}")
            self._execute(
                """
                UPDATE curriculum_modules
                SET review_status = ?, quality_score = ?, last_reviewed_at = ?, notes = ?
                WHERE id = ?
                """,
                ("revision_in_progress", score, utc_now(), note, module["id"]),
            )
            return f"Opened curriculum revision on {module['name']} and refreshed its review status."

        if department == "accounts":
            payment = self._fetchone(
                """
                SELECT * FROM payments
                ORDER BY
                  CASE status
                    WHEN 'refund_review' THEN 1
                    WHEN 'overdue' THEN 2
                    WHEN 'partial' THEN 3
                    ELSE 4
                  END,
                  amount_due DESC
                LIMIT 1
                """
            )
            if not payment:
                return "No payment record was available to update."
            if "refund" in lowered:
                new_status = "refund_initiated"
                note_label = "Refund action"
            else:
                new_status = "collection_followup"
                note_label = "Collections action"
            note = self._append_note(payment["notes"], f"{note_label}: {ai_response[:140]}")
            self._execute(
                """
                UPDATE payments
                SET status = ?, last_action_at = ?, notes = ?
                WHERE id = ?
                """,
                (new_status, utc_now(), note, payment["id"]),
            )
            return f"Updated payment record for {payment['student_email']} to {new_status}."

        if department == "tech":
            incident = self._fetchone(
                """
                SELECT * FROM tech_incidents
                ORDER BY
                  CASE severity
                    WHEN 'critical' THEN 1
                    WHEN 'high' THEN 2
                    WHEN 'medium' THEN 3
                    ELSE 4
                  END,
                  last_update_at DESC
                LIMIT 1
                """
            )
            if not incident:
                return "No incident record was available to update."
            note = self._append_note(incident["notes"], f"Tech action: {ai_response[:140]}")
            self._execute(
                """
                UPDATE tech_incidents
                SET status = ?, owner = ?, last_update_at = ?, notes = ?
                WHERE id = ?
                """,
                ("investigating", "AI Tech Lead", utc_now(), note, incident["id"]),
            )
            return f"Moved incident '{incident['title']}' into investigating and refreshed the technical owner."

        return "No database action was applied."

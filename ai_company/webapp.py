"""HTTP server for the Masai real-time AI company dashboard."""

import json
import mimetypes
import os
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

try:
    from ai_company.config import LOGGER
    from ai_company.core.company import CompanyRuntime
except ImportError:
    from config import LOGGER
    from core.company import CompanyRuntime


BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "web"
HOST = os.getenv("AI_COMPANY_HOST", "127.0.0.1")
PORT = int(os.getenv("AI_COMPANY_PORT", "8000"))

company = CompanyRuntime()


class CompanyRequestHandler(BaseHTTPRequestHandler):
    """Serve the dashboard UI and the live JSON API."""

    server_version = "MasaiFounderOS/2.0"

    def log_message(self, format: str, *args) -> None:
        """Route request logs through the app logger."""
        LOGGER.info("%s - %s", self.address_string(), format % args)

    def _send_json(self, payload: dict, status: int = HTTPStatus.OK) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self._send_common_headers("application/json; charset=utf-8", len(body))
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, file_path: Path) -> None:
        if not file_path.exists() or not file_path.is_file():
            self.send_error(HTTPStatus.NOT_FOUND, "File not found.")
            return

        data = file_path.read_bytes()
        content_type, _ = mimetypes.guess_type(file_path.name)
        self.send_response(HTTPStatus.OK)
        self._send_common_headers(content_type or "application/octet-stream", len(data))
        self.end_headers()
        self.wfile.write(data)

    def _send_common_headers(self, content_type: str, content_length: int) -> None:
        """Send headers shared by static files and JSON responses."""
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(content_length))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def do_OPTIONS(self) -> None:
        """Handle CORS preflight requests for a separately hosted frontend."""
        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _read_json_body(self) -> dict:
        content_length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(content_length) if content_length else b"{}"
        try:
            return json.loads(raw_body.decode("utf-8"))
        except json.JSONDecodeError:
            return {}

    def do_GET(self) -> None:
        """Serve the dashboard shell and live state endpoints."""
        path = urlparse(self.path).path
        page_map = {
            "/": "index.html",
            "/index.html": "index.html",
            "/dashboard": "dashboard.html",
            "/dashboard.html": "dashboard.html",
            "/teams": "teams.html",
            "/teams.html": "teams.html",
            "/workflow": "workflow.html",
            "/workflow.html": "workflow.html",
        }
        asset_map = {
            "/assets/styles.css": "styles.css",
            "/assets/app.js": "app.js",
            "/assets/overview.js": "overview.js",
            "/assets/vercel-config.js": "vercel-config.js",
        }

        if path in page_map:
            self._send_file(STATIC_DIR / page_map[path])
            return
        if path in asset_map:
            self._send_file(STATIC_DIR / asset_map[path])
            return
        if path == "/api/state":
            self._send_json(company.get_state())
            return
        if path == "/health":
            self._send_json({"status": "ok"})
            return

        self.send_error(HTTPStatus.NOT_FOUND, "Route not found.")

    def do_POST(self) -> None:
        """Handle live task mutations."""
        path = urlparse(self.path).path
        payload = self._read_json_body()

        if path == "/api/tasks":
            title = str(payload.get("title", "")).strip()
            request = str(payload.get("request", "")).strip()
            priority = str(payload.get("priority", "normal")).strip().lower()
            department_hint = str(payload.get("department_hint", "")).strip().lower()
            if not request:
                self._send_json(
                    {"error": "Please enter a founder request before submitting."},
                    status=HTTPStatus.BAD_REQUEST,
                )
                return

            task = company.submit_task(
                title=title,
                request=request,
                priority=priority,
                department_hint=department_hint,
            )
            self._send_json({"task": task, "state": company.get_state()}, status=HTTPStatus.CREATED)
            return

        if path.startswith("/api/tasks/") and path.endswith("/priority"):
            task_id = path.split("/")[3]
            priority = str(payload.get("priority", "")).strip().lower()
            try:
                task = company.update_priority(task_id, priority)
            except (KeyError, ValueError) as exc:
                self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
                return
            self._send_json({"task": task, "state": company.get_state()})
            return

        if path.startswith("/api/tasks/") and path.endswith("/retry"):
            task_id = path.split("/")[3]
            try:
                task = company.retry_task(task_id)
            except (KeyError, ValueError) as exc:
                self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
                return
            self._send_json({"task": task, "state": company.get_state()})
            return

        self.send_error(HTTPStatus.NOT_FOUND, "Route not found.")


def run_server() -> None:
    """Start the local threaded web server."""
    server = ThreadingHTTPServer((HOST, PORT), CompanyRequestHandler)
    LOGGER.info("Starting real-time dashboard at http://%s:%s", HOST, PORT)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        LOGGER.info("Shutting down dashboard")
    finally:
        server.server_close()


if __name__ == "__main__":
    run_server()

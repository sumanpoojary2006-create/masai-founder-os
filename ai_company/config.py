"""Configuration values used across the project."""

import logging
import os
from pathlib import Path


def _load_env_files() -> None:
    """Load simple KEY=VALUE pairs from local env files if present."""
    search_roots = [
        Path(__file__).resolve().parent,
        Path(__file__).resolve().parent.parent,
        Path.cwd(),
    ]
    candidate_names = (".env.local", ".env")
    seen = set()

    for root in search_roots:
        for name in candidate_names:
            env_path = (root / name).resolve()
            if env_path in seen or not env_path.exists() or not env_path.is_file():
                continue
            seen.add(env_path)
            for raw_line in env_path.read_text(encoding="utf-8").splitlines():
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip("'").strip('"')
                if key and key not in os.environ:
                    os.environ[key] = value


_load_env_files()


APP_NAME = "Masai Founder OS"
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_MODEL = "openrouter/free"
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
DATABASE_URL = os.getenv("DATABASE_URL", "") or os.getenv("RENDER_POSTGRES_INTERNAL_URL", "")
DATABASE_PATH = os.getenv("AI_COMPANY_DB_PATH", "masai_founder_os.db")

REQUEST_TIMEOUT = 45
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 2
WORKFLOW_STEP_DELAY_SECONDS = float(os.getenv("AI_COMPANY_WORKFLOW_DELAY", "0.35"))

EXIT_COMMANDS = {"exit", "quit", "q"}


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
LOGGER = logging.getLogger(APP_NAME)

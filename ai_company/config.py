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
EMAIL_PROVIDER = os.getenv("EMAIL_PROVIDER", "")
BREVO_API_KEY = os.getenv("BREVO_API_KEY", "")
BREVO_API_URL = os.getenv("BREVO_API_URL", "https://api.brevo.com/v3/smtp/email")
BREVO_FROM_EMAIL = os.getenv("BREVO_FROM_EMAIL", "")
BREVO_FROM_NAME = os.getenv("BREVO_FROM_NAME", APP_NAME)
RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
RESEND_API_URL = os.getenv("RESEND_API_URL", "https://api.resend.com/emails")
RESEND_FROM_EMAIL = os.getenv("RESEND_FROM_EMAIL", "")
RESEND_FROM_NAME = os.getenv("RESEND_FROM_NAME", APP_NAME)
SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM_EMAIL = os.getenv("SMTP_FROM_EMAIL", "")
SMTP_FROM_NAME = os.getenv("SMTP_FROM_NAME", APP_NAME)
SMTP_USE_TLS = os.getenv("SMTP_USE_TLS", "true").lower() in {"1", "true", "yes", "on"}
SMTP_USE_SSL = os.getenv("SMTP_USE_SSL", "false").lower() in {"1", "true", "yes", "on"}

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

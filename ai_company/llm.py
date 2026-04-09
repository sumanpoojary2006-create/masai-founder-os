"""Lightweight OpenRouter client built with requests."""

import os
import time
from typing import Any, Dict

import requests

try:
    from ai_company.config import (
        LOGGER,
        MAX_RETRIES,
        OPENROUTER_API_URL,
        OPENROUTER_MODEL,
        REQUEST_TIMEOUT,
        RETRY_DELAY_SECONDS,
    )
except ImportError:
    from config import (
        LOGGER,
        MAX_RETRIES,
        OPENROUTER_API_URL,
        OPENROUTER_MODEL,
        REQUEST_TIMEOUT,
        RETRY_DELAY_SECONDS,
    )


def _extract_text(data: Dict[str, Any]) -> str:
    """Safely pull assistant text from an OpenRouter response."""
    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        return "I could not parse the model response."

    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(item.get("text", ""))
        return "\n".join(part for part in parts if part).strip() or "No text returned."

    return str(content).strip() or "No text returned."


def call_llm(prompt: str) -> str:
    """Send a prompt to OpenRouter and return only the text output."""
    api_key = os.getenv("OPENROUTER_API_KEY", "")

    if not api_key:
        return (
            "OpenRouter API key not found. Set the OPENROUTER_API_KEY "
            "environment variable and try again."
        )

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://colab.research.google.com/",
        "X-Title": "AI Company Simulator",
    }
    payload = {
        "model": OPENROUTER_MODEL,
        "messages": [
            {
                "role": "user",
                "content": prompt,
            }
        ],
        "temperature": 0.3,
    }

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            LOGGER.info("Calling OpenRouter (attempt %s/%s)", attempt, MAX_RETRIES)
            response = requests.post(
                OPENROUTER_API_URL,
                headers=headers,
                json=payload,
                timeout=REQUEST_TIMEOUT,
            )
            response.raise_for_status()
            data = response.json()
            return _extract_text(data)
        except requests.exceptions.RequestException as exc:
            LOGGER.warning("OpenRouter request failed: %s", exc)
            status_code = getattr(getattr(exc, "response", None), "status_code", None)
            if status_code == 401:
                return (
                    "OpenRouter rejected the API key. Update OPENROUTER_API_KEY "
                    "and restart the dashboard."
                )
            if status_code == 404:
                return (
                    "The configured OpenRouter model endpoint was not found. "
                    "Check the selected model and try again."
                )
            if status_code == 429:
                return (
                    "OpenRouter rate-limited the request. Wait a moment and retry."
                )
            if attempt == MAX_RETRIES:
                return f"LLM request failed after {MAX_RETRIES} attempts: {exc}"
            time.sleep(RETRY_DELAY_SECONDS)
        except ValueError as exc:
            LOGGER.warning("Invalid JSON from OpenRouter: %s", exc)
            return f"LLM returned an invalid JSON response: {exc}"

    return "Unexpected error while calling the language model."

"""Accounts worker agent."""

try:
    from ai_company.llm import call_llm
    from ai_company.utils.prompts import accounts_prompt
except ImportError:
    from llm import call_llm
    from utils.prompts import accounts_prompt


class AccountsAgent:
    """Handles payment, refund, and finance communication tasks."""

    name = "accounts"

    def process(self, task: str) -> str:
        """Generate an accounts-focused response."""
        return call_llm(accounts_prompt(task))

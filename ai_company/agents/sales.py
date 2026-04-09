"""Sales worker agent."""

try:
    from ai_company.llm import call_llm
    from ai_company.utils.prompts import sales_prompt
except ImportError:
    from llm import call_llm
    from utils.prompts import sales_prompt


class SalesAgent:
    """Handles admissions, conversion, and outreach tasks."""

    name = "sales"

    def process(self, task: str) -> str:
        """Generate a sales-focused response."""
        return call_llm(sales_prompt(task))

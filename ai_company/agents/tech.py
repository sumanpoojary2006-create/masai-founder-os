"""Tech worker agent."""

try:
    from ai_company.llm import call_llm
    from ai_company.utils.prompts import tech_prompt
except ImportError:
    from llm import call_llm
    from utils.prompts import tech_prompt


class TechAgent:
    """Handles product, platform, and engineering tasks."""

    name = "tech"

    def process(self, task: str) -> str:
        """Generate a tech-focused response."""
        return call_llm(tech_prompt(task))

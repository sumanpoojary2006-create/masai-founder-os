"""Operations worker agent."""

try:
    from ai_company.llm import call_llm
    from ai_company.utils.prompts import ops_prompt
except ImportError:
    from llm import call_llm
    from utils.prompts import ops_prompt


class OpsAgent:
    """Handles student operations and process design tasks."""

    name = "ops"

    def process(self, task: str) -> str:
        """Generate an operations-focused response."""
        return call_llm(ops_prompt(task))

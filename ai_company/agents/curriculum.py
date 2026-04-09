"""Curriculum worker agent."""

try:
    from ai_company.llm import call_llm
    from ai_company.utils.prompts import curriculum_prompt
except ImportError:
    from llm import call_llm
    from utils.prompts import curriculum_prompt


class CurriculumAgent:
    """Handles course design and learning-quality tasks."""

    name = "curriculum"

    def process(self, task: str) -> str:
        """Generate a curriculum-focused response."""
        return call_llm(curriculum_prompt(task))

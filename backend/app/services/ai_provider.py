from typing import Protocol
from app.models import Condition, Task


class AIResponseProvider(Protocol):
    def generate_response(
        self, condition: Condition, task: Task, participant_message: str
    ) -> str:
        ...


class ControlledMockProvider:
    """
    Deterministic response provider for controlled between-subjects experiments.
    Delivers the condition's fixed answer template, optionally paired with the
    predefined explanation template, avoiding live-LLM confounding variance.
    """

    def generate_response(
        self, condition: Condition, task: Task, participant_message: str
    ) -> str:
        answer = condition.ai_answer_template.strip()
        explanation = (condition.ai_explanation_template or "").strip()
        if explanation:
            return f"{answer}\n\n{explanation}"
        return answer


def get_ai_provider() -> AIResponseProvider:
    return ControlledMockProvider()
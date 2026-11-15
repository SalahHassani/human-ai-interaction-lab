import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT_DIR / "backend"))

from sqlalchemy import select  # noqa: E402
from app.core.database import SessionLocal  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.models import (  # noqa: E402
    Condition,
    Experiment,
    ExperimentStatus,
    Task,
    TaskType,
    User,
    UserRole,
)

DEFAULT_QUESTIONS = [
    {
        "id": "trust_rating",
        "label": "I trust the AI system's recommendation.",
        "type": "likert",
        "min": 1,
        "max": 7,
        "required": True,
    },
    {
        "id": "confidence_rating",
        "label": "I feel confident in my final decision.",
        "type": "likert",
        "min": 1,
        "max": 7,
        "required": True,
    },
    {
        "id": "usefulness_rating",
        "label": "The AI response was useful for completing this task.",
        "type": "likert",
        "min": 1,
        "max": 7,
        "required": True,
    },
    {
        "id": "satisfaction_rating",
        "label": "Overall, I am satisfied with the AI assistance.",
        "type": "likert",
        "min": 1,
        "max": 7,
        "required": True,
    },
    {
        "id": "rationale_text",
        "label": "Briefly explain why you agreed or disagreed with the AI (optional).",
        "type": "text",
        "required": False,
    },
]


def seed() -> None:
    db = SessionLocal()
    try:
        email = "researcher@hailab.org"
        researcher = db.scalar(select(User).where(User.email == email))
        if researcher is None:
            researcher = User(
                email=email,
                full_name="Dr. Maya Lin (Demo Researcher)",
                password_hash=hash_password("Researcher123!"),
                role=UserRole.RESEARCHER,
                is_active=True,
            )
            db.add(researcher)
            db.flush()
            print(f"Created demo researcher: {email} / Researcher123!")
        else:
            print(f"Demo researcher already exists: {email}")

        existing_exp = db.scalar(
            select(Experiment).where(
                Experiment.owner_id == researcher.id,
                Experiment.title == "AI Explanations and User Trust",
            )
        )
        if existing_exp is None:
            exp = Experiment(
                owner_id=researcher.id,
                title="AI Explanations and User Trust",
                description="Controlled two-condition demonstration comparing answer-only vs. answer-plus-explanation AI responses on decision trust and confidence.",
                participant_information=(
                    "You are invited to participate in a simulated Human-AI Interaction study. "
                    "You will review a short clinical triage scenario, interact with an AI decision-support assistant, "
                    "and rate your trust, confidence, usefulness, and satisfaction. All data is pseudonymous."
                ),
                consent_statement="I have read the study information above and voluntarily consent to participate in this demonstration study.",
                status=ExperimentStatus.DRAFT,
            )
            db.add(exp)
            db.flush()

            cond_a = Condition(
                experiment_id=exp.id,
                name="Condition A: Answer Only",
                description="Participant receives a concise AI recommendation without supporting rationale.",
                ai_answer_template="Recommendation: Escalate Patient #402 to Urgent Cardiology Review (Priority Level 2).",
                ai_explanation_template=None,
                condition_order=1,
            )
            cond_b = Condition(
                experiment_id=exp.id,
                name="Condition B: Answer + Explanation",
                description="Participant receives the exact same AI recommendation accompanied by a structured feature-based explanation.",
                ai_answer_template="Recommendation: Escalate Patient #402 to Urgent Cardiology Review (Priority Level 2).",
                ai_explanation_template=(
                    "Explanation: Three risk indicators triggered Priority Level 2: "
                    "(1) exertional chest tightness lasting >15 minutes, "
                    "(2) borderline troponin elevation (0.06 ng/mL), and "
                    "(3) family history of premature coronary artery disease. "
                    "Together these raise 24-hour acute coronary syndrome risk above the 15% escalation threshold."
                ),
                condition_order=2,
            )
            db.add_all([cond_a, cond_b])
            db.flush()

            for cond in (cond_a, cond_b):
                task = Task(
                    condition_id=cond.id,
                    title="Triage Assessment Task",
                    instructions="Review the scenario below, ask the AI assistant for its assessment, and complete the post-task rating scales.",
                    scenario_prompt=(
                        "Scenario: Patient #402 (54-year-old) presents with intermittent chest tightness after climbing stairs, "
                        "normal resting ECG, troponin 0.06 ng/mL, and a family history of heart disease. "
                        "Ask the AI assistant for its triage recommendation."
                    ),
                    task_order=1,
                    task_type=TaskType.AI_INTERACTION,
                    questions_json=DEFAULT_QUESTIONS,
                )
                db.add(task)

            db.commit()
            print("Seeded demo experiment: 'AI Explanations and User Trust' (Draft with Condition A & B)")
        else:
            print("Demo experiment already exists.")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
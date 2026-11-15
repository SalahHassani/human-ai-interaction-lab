import enum


class UserRole(str, enum.Enum):
    RESEARCHER = "researcher"
    ADMIN = "admin"


class ExperimentStatus(str, enum.Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    PAUSED = "paused"
    CLOSED = "closed"
    ARCHIVED = "archived"


class TaskType(str, enum.Enum):
    AI_INTERACTION = "ai_interaction"
    QUESTIONNAIRE = "questionnaire"
    DECISION = "decision"


class MessageRole(str, enum.Enum):
    PARTICIPANT = "participant"
    ASSISTANT = "assistant"
    SYSTEM = "system"

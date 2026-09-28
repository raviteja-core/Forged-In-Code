from enum import Enum


class Language(str, Enum):
    PYTHON = "python"
    CPP = "cpp"
    JAVA = "java"
    RUST = "rust"


class SubmissionStatus(str, Enum):
    CREATED = "CREATED"
    QUEUED = "QUEUED"
    SCHEDULED = "SCHEDULED"
    STARTING = "STARTING"
    COMPILING = "COMPILING"
    RUNNING = "RUNNING"
    JUDGING = "JUDGING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class Verdict(str, Enum):
    ACCEPTED = "ACCEPTED"
    WRONG_ANSWER = "WRONG_ANSWER"
    COMPILE_ERROR = "COMPILE_ERROR"
    RUNTIME_ERROR = "RUNTIME_ERROR"
    TIME_LIMIT = "TIME_LIMIT"
    MEMORY_LIMIT = "MEMORY_LIMIT"
    OUTPUT_LIMIT = "OUTPUT_LIMIT"
    CANCELED = "CANCELED"
    SANDBOX_ERROR = "SANDBOX_ERROR"
    INFRASTRUCTURE_FAILURE = "INFRASTRUCTURE_FAILURE"

    @property
    def is_terminal(self) -> bool:
        return True

    @property
    def is_infrastructure_failure(self) -> bool:
        return self in (Verdict.INFRASTRUCTURE_FAILURE, Verdict.SANDBOX_ERROR)


class FailureType(str, Enum):
    USER_CODE = "USER_CODE"
    INFRASTRUCTURE = "INFRASTRUCTURE"
    TIMEOUT = "TIMEOUT"
    SANDBOX_ERROR = "SANDBOX_ERROR"


class ProblemDifficulty(str, Enum):
    EASY = "EASY"
    MEDIUM = "MEDIUM"
    HARD = "HARD"


class ProblemStatus(str, Enum):
    DRAFT = "DRAFT"
    PUBLISHED = "PUBLISHED"
    ARCHIVED = "ARCHIVED"

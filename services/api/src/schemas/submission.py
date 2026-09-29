from datetime import datetime
from uuid import UUID

from forgerun_contracts.enums import Language, SubmissionStatus, Verdict
from pydantic import BaseModel, Field


class CreateSubmissionRequest(BaseModel):
    problem_id: UUID
    language: Language
    source_code: str
    client_request_id: UUID


class CreateSubmissionResponse(BaseModel):
    submission_id: UUID
    attempt_id: UUID
    status: SubmissionStatus
    created_at: datetime


class SingleTestResultResponse(BaseModel):
    test_index: int
    verdict: Verdict
    execution_ms: int
    memory_bytes: int
    stdout_excerpt: str | None = None
    stderr_excerpt: str | None = None


class SubmissionDetailResponse(BaseModel):
    submission_id: UUID
    user_id: UUID
    problem_id: UUID
    language: Language
    status: SubmissionStatus
    verdict: Verdict | None = None
    execution_ms: int | None = None
    cpu_ms: int | None = None
    peak_memory_bytes: int | None = None
    test_results: list[SingleTestResultResponse] = Field(default_factory=list)
    created_at: datetime

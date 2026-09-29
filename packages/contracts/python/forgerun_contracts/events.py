from datetime import datetime, timezone
from typing import Any, Generic, TypeVar
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from forgerun_contracts.enums import FailureType, Language, Verdict

PayloadT = TypeVar("PayloadT", bound=BaseModel)


class EventEnvelope(BaseModel, Generic[PayloadT]):
    """Standardized event envelope used across all Kafka topics."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    event_id: UUID = Field(default_factory=uuid4, description="Unique event identifier")
    event_type: str = Field(..., description="Canonical event name (e.g. submission.created)")
    schema_version: int = Field(default=1, description="Schema revision number")
    occurred_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp when event occurred (UTC)",
    )
    correlation_id: UUID = Field(..., description="Trace/flow correlation identifier")
    causation_id: UUID | None = Field(None, description="Event ID that triggered this event")
    producer: str = Field(..., description="Service emitting the event")
    payload: PayloadT = Field(..., description="Event payload data")


class SubmissionCreatedPayload(BaseModel):
    """Payload for forge.submission.created.v1"""

    model_config = ConfigDict(frozen=True, extra="forbid")

    submission_id: UUID
    attempt_id: UUID
    user_id: UUID
    problem_version_id: UUID
    language: Language
    base_priority: int = Field(default=50, ge=1, le=100)


class ExecutionScheduledPayload(BaseModel):
    """Payload for forge.execution.scheduled.v1"""

    model_config = ConfigDict(frozen=True, extra="forbid")

    attempt_id: UUID
    submission_id: UUID
    user_id: UUID
    priority: int = Field(..., description="Calculated effective priority")
    scheduled_at: datetime
    scheduler_partition: int


class ExecutionStartedPayload(BaseModel):
    """Payload for forge.execution.started.v1"""

    model_config = ConfigDict(frozen=True, extra="forbid")

    attempt_id: UUID
    submission_id: UUID
    pod_name: str
    node_name: str
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ExecutionCompletedPayload(BaseModel):
    """Payload for forge.execution.completed.v1"""

    model_config = ConfigDict(frozen=True, extra="forbid")

    attempt_id: UUID
    submission_id: UUID
    verdict: Verdict
    execution_ms: int = Field(ge=0)
    cpu_ms: int = Field(ge=0)
    peak_memory_bytes: int = Field(ge=0)
    tests_passed: int = Field(ge=0)
    tests_total: int = Field(ge=0)
    artifact_uri: str | None = None


class ExecutionFailedPayload(BaseModel):
    """Payload for forge.execution.failed.v1"""

    model_config = ConfigDict(frozen=True, extra="forbid")

    attempt_id: UUID
    submission_id: UUID
    failure_type: FailureType
    error_message: str
    retryable: bool
    details: dict[str, Any] | None = None


# Type aliases for full event envelopes
SubmissionCreatedEvent = EventEnvelope[SubmissionCreatedPayload]
ExecutionScheduledEvent = EventEnvelope[ExecutionScheduledPayload]
ExecutionStartedEvent = EventEnvelope[ExecutionStartedPayload]
ExecutionCompletedEvent = EventEnvelope[ExecutionCompletedPayload]
ExecutionFailedEvent = EventEnvelope[ExecutionFailedPayload]

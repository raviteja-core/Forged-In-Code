from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import CITEXT, JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from services.api.src.db.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    email: Mapped[str] = mapped_column(CITEXT, unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="user")
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    submissions: Mapped[list["Submission"]] = relationship(
        "Submission", back_populates="user", cascade="all, delete-orphan"
    )


class Problem(Base):
    __tablename__ = "problems"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    slug: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    difficulty: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="PUBLISHED")
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    versions: Mapped[list["ProblemVersion"]] = relationship(
        "ProblemVersion", back_populates="problem", cascade="all, delete-orphan"
    )


class ProblemVersion(Base):
    __tablename__ = "problem_versions"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    problem_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("problems.id", ondelete="CASCADE"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    runtime_manifest: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    published_at: Mapped[datetime] = mapped_column(
        nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    problem: Mapped["Problem"] = relationship("Problem", back_populates="versions")
    submissions: Mapped[list["Submission"]] = relationship(
        "Submission", back_populates="problem_version"
    )

    __table_args__ = (
        UniqueConstraint("problem_id", "version", name="uq_problem_version"),
    )


class Submission(Base):
    __tablename__ = "submissions"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    problem_version_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("problem_versions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    language: Mapped[str] = mapped_column(String(32), nullable=False)
    source_code: Mapped[str] = mapped_column(Text, nullable=False)
    source_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    client_request_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    user: Mapped["User"] = relationship("User", back_populates="submissions")
    problem_version: Mapped["ProblemVersion"] = relationship(
        "ProblemVersion", back_populates="submissions"
    )
    attempts: Mapped[list["SubmissionAttempt"]] = relationship(
        "SubmissionAttempt", back_populates="submission", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint(
            "user_id", "client_request_id", name="uq_submission_user_client_request"
        ),
        Index("ix_submissions_user_created_desc", "user_id", created_at.desc()),
    )


class SubmissionAttempt(Base):
    __tablename__ = "submission_attempts"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    submission_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("submissions.id", ondelete="CASCADE"), nullable=False
    )
    attempt_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="QUEUED")
    verdict: Mapped[str | None] = mapped_column(String(32), nullable=True)
    scheduled_at: Mapped[datetime | None] = mapped_column(nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(nullable=True)
    execution_ms: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    cpu_ms: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    peak_memory_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    pod_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    submission: Mapped["Submission"] = relationship("Submission", back_populates="attempts")
    test_results: Mapped[list["TestResult"]] = relationship(
        "TestResult", back_populates="attempt", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("submission_id", "attempt_no", name="uq_submission_attempt_no"),
        Index("ix_submission_attempts_status_scheduled", "status", "scheduled_at"),
    )


class TestResult(Base):
    __tablename__ = "test_results"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    attempt_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("submission_attempts.id", ondelete="CASCADE"),
        nullable=False,
    )
    test_index: Mapped[int] = mapped_column(Integer, nullable=False)
    verdict: Mapped[str] = mapped_column(String(32), nullable=False)
    execution_ms: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    memory_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    stdout_excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)
    stderr_excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)

    attempt: Mapped["SubmissionAttempt"] = relationship(
        "SubmissionAttempt", back_populates="test_results"
    )

    __table_args__ = (
        UniqueConstraint("attempt_id", "test_index", name="uq_test_result_attempt_index"),
    )


class OutboxEvent(Base):
    __tablename__ = "outbox_events"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    aggregate_type: Mapped[str] = mapped_column(String(64), nullable=False)
    aggregate_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    event_type: Mapped[str] = mapped_column(String(128), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    published_at: Mapped[datetime | None] = mapped_column(nullable=True)

    __table_args__ = (
        Index("ix_outbox_events_published_created", "published_at", "created_at"),
    )


class IdempotencyKey(Base):
    __tablename__ = "idempotency_keys"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    key: Mapped[str] = mapped_column(String(256), nullable=False)
    response_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    resource_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    __table_args__ = (
        UniqueConstraint("user_id", "key", name="uq_idempotency_key_user"),
    )

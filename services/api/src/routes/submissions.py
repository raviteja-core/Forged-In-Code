import asyncio
import hashlib
import json
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, status
from fastapi.responses import StreamingResponse
from forgerun_contracts.enums import Language, SubmissionStatus, Verdict
from forgerun_contracts.events import SubmissionCreatedPayload
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from services.api.src.db.models import (
    OutboxEvent,
    ProblemVersion,
    Submission,
    SubmissionAttempt,
)
from services.api.src.db.seed import DEFAULT_USER_ID
from services.api.src.db.session import get_async_db
from services.api.src.schemas.submission import (
    CreateSubmissionRequest,
    CreateSubmissionResponse,
    SingleTestResultResponse,
    SubmissionDetailResponse,
)

router = APIRouter(prefix="/submissions", tags=["submissions"])


@router.post("", response_model=CreateSubmissionResponse, status_code=status.HTTP_201_CREATED)
async def create_submission(
    request: CreateSubmissionRequest,
    db: AsyncSession = Depends(get_async_db),
    x_user_id: UUID = Header(default=DEFAULT_USER_ID),
):
    """Transactionally ingests code submission, initial attempt, and outbox event with idempotency."""
    user_id = x_user_id

    # 1. Idempotency Check: (user_id, client_request_id)
    existing_stmt = (
        select(Submission)
        .where(
            Submission.user_id == user_id,
            Submission.client_request_id == request.client_request_id,
        )
        .options(selectinload(Submission.attempts))
    )
    res = await db.execute(existing_stmt)
    existing = res.scalar_one_or_none()
    if existing:
        latest_attempt = sorted(existing.attempts, key=lambda a: a.attempt_no, reverse=True)[0]
        return CreateSubmissionResponse(
            submission_id=existing.id,
            attempt_id=latest_attempt.id,
            status=SubmissionStatus(latest_attempt.status),
            created_at=existing.created_at,
        )

    # 2. Validate problem version exists
    pv_res = await db.execute(
        select(ProblemVersion)
        .where(ProblemVersion.problem_id == request.problem_id)
        .order_by(ProblemVersion.version.desc())
        .limit(1)
    )
    problem_version = pv_res.scalar_one_or_none()
    if not problem_version:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Problem {request.problem_id} does not exist or has no versions",
        )

    submission_id = uuid4()
    attempt_id = uuid4()
    source_sha256 = hashlib.sha256(request.source_code.encode("utf-8")).hexdigest()

    # 3. Transactional Outbox insertion
    submission = Submission(
        id=submission_id,
        user_id=user_id,
        problem_version_id=problem_version.id,
        language=request.language.value,
        source_code=request.source_code,
        source_sha256=source_sha256,
        client_request_id=request.client_request_id,
    )
    db.add(submission)

    attempt = SubmissionAttempt(
        id=attempt_id,
        submission_id=submission_id,
        attempt_no=1,
        status=SubmissionStatus.QUEUED.value,
    )
    db.add(attempt)

    payload = SubmissionCreatedPayload(
        submission_id=submission_id,
        attempt_id=attempt_id,
        user_id=user_id,
        problem_version_id=problem_version.id,
        language=request.language,
        base_priority=50,
    )
    outbox_event = OutboxEvent(
        id=uuid4(),
        aggregate_type="submission",
        aggregate_id=submission_id,
        event_type="submission.created",
        payload=payload.model_dump(mode="json"),
    )
    db.add(outbox_event)

    await db.commit()

    return CreateSubmissionResponse(
        submission_id=submission.id,
        attempt_id=attempt.id,
        status=SubmissionStatus.QUEUED,
        created_at=submission.created_at,
    )


@router.get("/{submission_id}", response_model=SubmissionDetailResponse)
async def get_submission(
    submission_id: UUID,
    db: AsyncSession = Depends(get_async_db),
):
    """Retrieves current submission status and attempt verdicts."""
    stmt = (
        select(Submission)
        .where(Submission.id == submission_id)
        .options(
            selectinload(Submission.attempts).selectinload(SubmissionAttempt.test_results),
            selectinload(Submission.problem_version),
        )
    )
    res = await db.execute(stmt)
    submission = res.scalar_one_or_none()
    if not submission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Submission {submission_id} not found",
        )

    latest_attempt = sorted(submission.attempts, key=lambda a: a.attempt_no, reverse=True)[0]
    test_results = [
        SingleTestResultResponse(
            test_index=tr.test_index,
            verdict=Verdict(tr.verdict),
            execution_ms=tr.execution_ms,
            memory_bytes=tr.memory_bytes,
            stdout_excerpt=tr.stdout_excerpt,
            stderr_excerpt=tr.stderr_excerpt,
        )
        for tr in sorted(latest_attempt.test_results, key=lambda r: r.test_index)
    ]

    return SubmissionDetailResponse(
        submission_id=submission.id,
        user_id=submission.user_id,
        problem_id=submission.problem_version.problem_id,
        language=Language(submission.language),
        status=SubmissionStatus(latest_attempt.status),
        verdict=Verdict(latest_attempt.verdict) if latest_attempt.verdict else None,
        execution_ms=latest_attempt.execution_ms,
        cpu_ms=latest_attempt.cpu_ms,
        peak_memory_bytes=latest_attempt.peak_memory_bytes,
        test_results=test_results,
        created_at=submission.created_at,
    )


@router.get("/{submission_id}/events")
async def stream_submission_events(
    submission_id: UUID,
    db: AsyncSession = Depends(get_async_db),
):
    """Streams submission execution lifecycle events via Server-Sent Events (SSE)."""

    async def event_generator():
        last_status = None
        for _ in range(60):  # poll up to 60 times with 500ms intervals
            stmt = (
                select(SubmissionAttempt)
                .where(SubmissionAttempt.submission_id == submission_id)
                .order_by(SubmissionAttempt.attempt_no.desc())
            )
            res = await db.execute(stmt)
            attempt = res.scalar_one_or_none()
            if attempt:
                if attempt.status != last_status:
                    last_status = attempt.status
                    data = json.dumps(
                        {
                            "submission_id": str(submission_id),
                            "attempt_id": str(attempt.id),
                            "status": attempt.status,
                            "verdict": attempt.verdict,
                        }
                    )
                    yield f"event: status\ndata: {data}\n\n"

                if (
                    attempt.status
                    in (SubmissionStatus.COMPLETED.value, SubmissionStatus.FAILED.value)
                    or attempt.verdict
                ):
                    break

            await asyncio.sleep(0.5)

    return StreamingResponse(event_generator(), media_type="text/event-stream")

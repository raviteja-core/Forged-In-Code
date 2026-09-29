import asyncio
import json
from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from controller import ExecutionController
from forgerun_contracts.config import get_settings
from forgerun_contracts.events import (
    EventEnvelope,
    ExecutionScheduledPayload,
)
from httpx import ASGITransport, AsyncClient
from publisher import OutboxPublisher
from sqlalchemy import func, select

from services.api.src.db.models import Submission, SubmissionAttempt
from services.api.src.db.seed import DEFAULT_PROBLEM_ID, DEFAULT_USER_ID, seed_initial_data
from services.api.src.db.session import AsyncSessionLocal
from services.api.src.main import app


async def run_pipeline_step(sub_id: str, attempt_id: str):
    """Executes the pipeline synchronously: Outbox -> Kafka -> Controller -> Collector -> DB."""
    settings = get_settings()

    # 1. Prepare Consumer and Producer
    consumer = AIOKafkaConsumer(
        settings.KAFKA_TOPIC_SUBMISSION_CREATED,
        bootstrap_servers=settings.KAFKA_BROKERS,
        auto_offset_reset="earliest",
        group_id=f"test-scheduler-{uuid4()}",
    )
    producer = AIOKafkaProducer(
        bootstrap_servers=settings.KAFKA_BROKERS,
    )
    await consumer.start()
    await producer.start()

    # 2. Outbox Publisher: read from outbox_events and publish to Kafka
    publisher = OutboxPublisher()
    await publisher.start()
    try:
        await publisher.publish_batch()
    finally:
        await publisher.stop()

    # 3. Scheduler simulation / dispatch:
    scheduled_found = False
    try:
        for _ in range(100):
            try:
                msg = await asyncio.wait_for(consumer.getone(), timeout=2.0)
            except asyncio.TimeoutError:
                break
            data = json.loads(msg.value.decode("utf-8"))
            if data["payload"]["attempt_id"] == attempt_id:
                # Forward to execution.scheduled topic with priority
                scheduled_payload = ExecutionScheduledPayload(
                    attempt_id=UUID(attempt_id),
                    submission_id=UUID(sub_id),
                    user_id=UUID(data["payload"]["user_id"]),
                    priority=50,
                    scheduled_at=datetime.now(timezone.utc),
                    scheduler_partition=0,
                )
                scheduled_envelope = EventEnvelope[ExecutionScheduledPayload](
                    event_id=uuid4(),
                    event_type="execution.scheduled",
                    schema_version=1,
                    occurred_at=datetime.now(timezone.utc),
                    correlation_id=uuid4(),
                    producer="forgerun-scheduler",
                    payload=scheduled_payload,
                )
                await producer.send_and_wait(
                    settings.KAFKA_TOPIC_EXECUTION_SCHEDULED,
                    key=attempt_id.encode("utf-8"),
                    value=scheduled_envelope.model_dump_json().encode("utf-8"),
                )
                scheduled_found = True
                break
    finally:
        await consumer.stop()
        await producer.stop()

    assert scheduled_found, f"Attempt {attempt_id} was not picked up from Kafka submission.created"

    # 3. Execution Controller: consume scheduled attempt, execute runner, finalize via Result Collector
    controller = ExecutionController()
    await controller.start()
    try:
        success = await controller.process_one_event(timeout_sec=5.0)
        assert success, "Execution Controller failed to process scheduled attempt"
    finally:
        await controller.stop()


@pytest.mark.asyncio
async def test_acceptance_1_correct_solution_accepted():
    async with AsyncSessionLocal() as session:
        await seed_initial_data(session)

    correct_source = """
import sys
lines = sys.stdin.read().split()
if lines:
    nums = [int(x) for x in lines[:-1]]
    target = int(lines[-1])
    for i in range(len(nums)):
        for j in range(i+1, len(nums)):
            if nums[i] + nums[j] == target:
                print(f"{i} {j}")
                sys.exit(0)
"""

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. User submits correct code
        resp = await client.post(
            "/api/v1/submissions",
            json={
                "problem_id": str(DEFAULT_PROBLEM_ID),
                "language": "python",
                "source_code": correct_source,
                "client_request_id": str(uuid4()),
            },
        )
        assert resp.status_code == 201
        sub_id = resp.json()["submission_id"]
        attempt_id = resp.json()["attempt_id"]

        # 2. Run execution pipeline
        await run_pipeline_step(sub_id, attempt_id)

        # 3. Verify verdict is ACCEPTED
        resp_detail = await client.get(f"/api/v1/submissions/{sub_id}")
        assert resp_detail.status_code == 200
        detail = resp_detail.json()
        assert detail["status"] == "COMPLETED"
        assert detail["verdict"] == "ACCEPTED"
        assert len(detail["test_results"]) == 3


@pytest.mark.asyncio
async def test_acceptance_2_wrong_solution_wrong_answer():
    async with AsyncSessionLocal() as session:
        await seed_initial_data(session)

    wrong_source = "print('999 999')"

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/submissions",
            json={
                "problem_id": str(DEFAULT_PROBLEM_ID),
                "language": "python",
                "source_code": wrong_source,
                "client_request_id": str(uuid4()),
            },
        )
        assert resp.status_code == 201
        sub_id = resp.json()["submission_id"]
        attempt_id = resp.json()["attempt_id"]

        await run_pipeline_step(sub_id, attempt_id)

        resp_detail = await client.get(f"/api/v1/submissions/{sub_id}")
        assert resp_detail.status_code == 200
        detail = resp_detail.json()
        assert detail["status"] == "COMPLETED"
        assert detail["verdict"] == "WRONG_ANSWER"


@pytest.mark.asyncio
async def test_acceptance_3_infinite_loop_time_limit():
    async with AsyncSessionLocal() as session:
        await seed_initial_data(session)

    loop_source = "while True:\n    pass"

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/submissions",
            json={
                "problem_id": str(DEFAULT_PROBLEM_ID),
                "language": "python",
                "source_code": loop_source,
                "client_request_id": str(uuid4()),
            },
        )
        assert resp.status_code == 201
        sub_id = resp.json()["submission_id"]
        attempt_id = resp.json()["attempt_id"]

        await run_pipeline_step(sub_id, attempt_id)

        resp_detail = await client.get(f"/api/v1/submissions/{sub_id}")
        assert resp_detail.status_code == 200
        detail = resp_detail.json()
        assert detail["status"] == "COMPLETED"
        assert detail["verdict"] == "TIME_LIMIT"


@pytest.mark.asyncio
async def test_acceptance_4_excessive_output_output_limit():
    async with AsyncSessionLocal() as session:
        await seed_initial_data(session)

    bomb_source = "print('Z' * 300000)"

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/submissions",
            json={
                "problem_id": str(DEFAULT_PROBLEM_ID),
                "language": "python",
                "source_code": bomb_source,
                "client_request_id": str(uuid4()),
            },
        )
        assert resp.status_code == 201
        sub_id = resp.json()["submission_id"]
        attempt_id = resp.json()["attempt_id"]

        await run_pipeline_step(sub_id, attempt_id)

        resp_detail = await client.get(f"/api/v1/submissions/{sub_id}")
        assert resp_detail.status_code == 200
        detail = resp_detail.json()
        assert detail["status"] == "COMPLETED"
        assert detail["verdict"] == "OUTPUT_LIMIT"


@pytest.mark.asyncio
async def test_acceptance_5_duplicate_client_request_id_idempotency():
    async with AsyncSessionLocal() as session:
        await seed_initial_data(session)

    client_req_id = str(uuid4())
    req_body = {
        "problem_id": str(DEFAULT_PROBLEM_ID),
        "language": "python",
        "source_code": "print('1 2')",
        "client_request_id": client_req_id,
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # First request
        resp1 = await client.post("/api/v1/submissions", json=req_body)
        assert resp1.status_code == 201
        sub1_id = resp1.json()["submission_id"]

        # Second request with duplicate client_request_id
        resp2 = await client.post("/api/v1/submissions", json=req_body)
        assert resp2.status_code in (200, 201)
        sub2_id = resp2.json()["submission_id"]

        # MUST match the original submission_id
        assert sub1_id == sub2_id

        # Verify in PostgreSQL that exactly ONE row exists
        async with AsyncSessionLocal() as session:
            count = await session.scalar(
                select(func.count(Submission.id)).where(
                    Submission.client_request_id == client_req_id
                )
            )
            assert count == 1, "Duplicate submission rows created in database"


@pytest.mark.asyncio
async def test_acceptance_6_duplicate_kafka_event_no_second_attempt():
    async with AsyncSessionLocal() as session:
        await seed_initial_data(session)

    # 1. Create submission
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/submissions",
            json={
                "problem_id": str(DEFAULT_PROBLEM_ID),
                "language": "python",
                "source_code": "print('hello')",
                "client_request_id": str(uuid4()),
            },
        )
        sub_id = resp.json()["submission_id"]
        attempt_id = resp.json()["attempt_id"]

        # Run pipeline to complete attempt
        await run_pipeline_step(sub_id, attempt_id)

    # 2. Simulate duplicate delivery of the exact same Kafka scheduled event
    settings = get_settings()
    producer = AIOKafkaProducer(bootstrap_servers=settings.KAFKA_BROKERS)
    await producer.start()
    try:
        dup_payload = ExecutionScheduledPayload(
            attempt_id=UUID(attempt_id),
            submission_id=UUID(sub_id),
            user_id=DEFAULT_USER_ID,
            priority=50,
            scheduled_at=datetime.now(timezone.utc),
            scheduler_partition=0,
        )
        duplicate_event = EventEnvelope[ExecutionScheduledPayload](
            event_id=uuid4(),
            event_type="execution.scheduled",
            schema_version=1,
            occurred_at=datetime.now(timezone.utc),
            correlation_id=uuid4(),
            producer="scheduler-retransmit",
            payload=dup_payload,
        )
        await producer.send_and_wait(
            settings.KAFKA_TOPIC_EXECUTION_SCHEDULED,
            key=attempt_id.encode("utf-8"),
            value=duplicate_event.model_dump_json().encode("utf-8"),
        )
    finally:
        await producer.stop()

    # 3. Execution controller processes duplicate event
    controller = ExecutionController()
    await controller.start()
    try:
        # Should process successfully without error, but idempotent finalizer does not create attempt #2
        await controller.process_one_event(timeout_sec=3.0)
    finally:
        await controller.stop()

    # 4. Verify in PostgreSQL that attempt count remains 1 and verdict is preserved
    async with AsyncSessionLocal() as session:
        attempts_count = await session.scalar(
            select(func.count(SubmissionAttempt.id)).where(
                SubmissionAttempt.submission_id == sub_id
            )
        )
        assert attempts_count == 1, "Duplicate attempt row was created!"

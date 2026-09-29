import asyncio
import json
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from aiokafka import AIOKafkaConsumer
from forgerun_contracts.config import get_settings
from forgerun_contracts.enums import Language
from forgerun_contracts.events import SubmissionCreatedPayload
from publisher import OutboxPublisher
from sqlalchemy import select

from services.api.src.db.models import OutboxEvent
from services.api.src.db.session import AsyncSessionLocal


@pytest.mark.asyncio
async def test_outbox_publisher_publishes_to_kafka():
    settings = get_settings()
    submission_id = uuid4()
    attempt_id = uuid4()
    user_id = uuid4()
    problem_version_id = uuid4()

    payload = SubmissionCreatedPayload(
        submission_id=submission_id,
        attempt_id=attempt_id,
        user_id=user_id,
        problem_version_id=problem_version_id,
        language=Language.PYTHON,
        base_priority=50,
    )

    event_id = uuid4()
    async with AsyncSessionLocal() as session:
        outbox_event = OutboxEvent(
            id=event_id,
            aggregate_type="submission",
            aggregate_id=submission_id,
            event_type="submission.created",
            payload=payload.model_dump(mode="json"),
            created_at=datetime.now(timezone.utc),
        )
        session.add(outbox_event)
        await session.commit()

    # Initialize consumer to listen on the topic
    consumer = AIOKafkaConsumer(
        settings.KAFKA_TOPIC_SUBMISSION_CREATED,
        bootstrap_servers=settings.KAFKA_BROKERS,
        auto_offset_reset="earliest",
        group_id=f"test-outbox-{uuid4()}",
    )
    await consumer.start()

    publisher = OutboxPublisher()
    await publisher.start()
    try:
        count = await publisher.publish_batch()
        assert count >= 1

        # Verify PostgreSQL row marked as published
        async with AsyncSessionLocal() as session:
            res = await session.execute(select(OutboxEvent).where(OutboxEvent.id == event_id))
            ev = res.scalar_one()
            assert ev.published_at is not None

        # Verify event received from Kafka
        found = False
        for _ in range(100):
            try:
                msg = await asyncio.wait_for(consumer.getone(), timeout=2.0)
            except asyncio.TimeoutError:
                break
            data = json.loads(msg.value.decode("utf-8"))
            if data.get("event_type") == "submission.created":
                if data["payload"]["submission_id"] == str(submission_id):
                    assert data["payload"]["attempt_id"] == str(attempt_id)
                    found = True
                    break
        assert found, "Target submission_id was not received from Kafka"
    finally:
        await publisher.stop()
        await consumer.stop()

import asyncio
import logging
from datetime import datetime, timezone

from aiokafka import AIOKafkaProducer
from forgerun_contracts.config import get_settings
from forgerun_contracts.events import EventEnvelope, SubmissionCreatedPayload
from sqlalchemy import select, update

from services.api.src.db.models import OutboxEvent
from services.api.src.db.session import AsyncSessionLocal

logger = logging.getLogger("forgerun.outbox")
logging.basicConfig(level=logging.INFO)


class OutboxPublisher:
    def __init__(self, kafka_brokers: str | None = None):
        self.settings = get_settings()
        self.kafka_brokers = kafka_brokers or self.settings.KAFKA_BROKERS
        self.producer: AIOKafkaProducer | None = None
        self._running = False

    async def start(self) -> None:
        logger.info("Starting Outbox Publisher with Kafka brokers: %s", self.kafka_brokers)
        self.producer = AIOKafkaProducer(
            bootstrap_servers=self.kafka_brokers,
            acks="all",
            enable_idempotence=True,
        )
        await self.producer.start()
        self._running = True

    async def stop(self) -> None:
        self._running = False
        if self.producer:
            await self.producer.stop()
            logger.info("Outbox Publisher stopped.")

    async def publish_batch(self, batch_size: int = 50) -> int:
        """Pulls unpublished outbox events and publishes them to Kafka with at-least-once guarantee."""
        if not self.producer:
            raise RuntimeError("Producer not started")

        async with AsyncSessionLocal() as session:
            # Query pending events using FOR UPDATE SKIP LOCKED to support multi-replica publisher scaling
            stmt = (
                select(OutboxEvent)
                .where(OutboxEvent.published_at.is_(None))
                .order_by(OutboxEvent.created_at.asc())
                .limit(batch_size)
                .with_for_update(skip_locked=True)
            )
            res = await session.execute(stmt)
            events = res.scalars().all()

            if not events:
                return 0

            published_ids = []
            for event in events:
                try:
                    topic = self.settings.KAFKA_TOPIC_SUBMISSION_CREATED
                    payload_data = event.payload
                    user_id_str = str(payload_data.get("user_id", ""))
                    key_bytes = user_id_str.encode("utf-8") if user_id_str else None

                    # Wrap in standard envelope
                    envelope = EventEnvelope[SubmissionCreatedPayload](
                        event_id=event.id,
                        event_type=event.event_type,
                        schema_version=1,
                        occurred_at=event.created_at,
                        correlation_id=event.id,
                        causation_id=None,
                        producer="outbox-publisher",
                        payload=SubmissionCreatedPayload.model_validate(payload_data),
                    )

                    value_bytes = envelope.model_dump_json().encode("utf-8")
                    await self.producer.send_and_wait(
                        topic=topic,
                        key=key_bytes,
                        value=value_bytes,
                    )
                    published_ids.append(event.id)
                except Exception as e:
                    logger.error("Failed to publish event %s: %s", event.id, e)
                    break

            if published_ids:
                now_utc = datetime.now(timezone.utc)
                update_stmt = (
                    update(OutboxEvent)
                    .where(OutboxEvent.id.in_(published_ids))
                    .values(published_at=now_utc)
                )
                await session.execute(update_stmt)
                await session.commit()
                logger.info("Successfully published %d outbox events to Kafka", len(published_ids))

            return len(published_ids)

    async def run_forever(self, poll_interval_ms: int = 200) -> None:
        await self.start()
        try:
            while self._running:
                count = await self.publish_batch()
                if count == 0:
                    await asyncio.sleep(poll_interval_ms / 1000.0)
        finally:
            await self.stop()

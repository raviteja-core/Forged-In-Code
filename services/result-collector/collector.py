import logging
from datetime import datetime, timezone
from uuid import UUID, uuid4

from aiokafka import AIOKafkaProducer
from forgerun_contracts.config import get_settings
from forgerun_contracts.events import EventEnvelope, ExecutionCompletedPayload
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert

from runner.core.models import RunnerResult
from services.api.src.db.models import SubmissionAttempt, TestResult
from services.api.src.db.session import AsyncSessionLocal

logger = logging.getLogger("forgerun.result-collector")


class ResultCollector:
    def __init__(self, kafka_brokers: str | None = None):
        self.settings = get_settings()
        self.kafka_brokers = kafka_brokers or self.settings.KAFKA_BROKERS
        self.producer: AIOKafkaProducer | None = None

    async def start(self) -> None:
        self.producer = AIOKafkaProducer(
            bootstrap_servers=self.kafka_brokers,
            acks="all",
            enable_idempotence=True,
        )
        await self.producer.start()

    async def stop(self) -> None:
        if self.producer:
            await self.producer.stop()

    async def finalize_attempt(
        self,
        attempt_id: UUID,
        submission_id: UUID,
        result: RunnerResult,
    ) -> bool:
        """Idempotently finalizes the attempt in PostgreSQL and emits execution.completed to Kafka."""
        now_utc = datetime.now(timezone.utc)

        async with AsyncSessionLocal() as session:
            # 1. Fetch current attempt to verify it's not already in terminal state
            stmt = select(SubmissionAttempt).where(SubmissionAttempt.id == attempt_id)
            res = await session.execute(stmt)
            attempt = res.scalar_one_or_none()

            if not attempt:
                logger.error("Attempt %s not found in database", attempt_id)
                return False

            if attempt.status == "COMPLETED" and attempt.verdict is not None:
                logger.info("Attempt %s already finalized (idempotent no-op)", attempt_id)
                return True

            # 2. Update submission_attempt
            upd = (
                update(SubmissionAttempt)
                .where(SubmissionAttempt.id == attempt_id)
                .values(
                    status="COMPLETED",
                    verdict=result.verdict.value,
                    execution_ms=result.execution_ms,
                    cpu_ms=result.cpu_ms,
                    peak_memory_bytes=result.peak_memory_bytes,
                    finished_at=now_utc,
                )
            )
            await session.execute(upd)

            # 3. Insert test results idempotently (ON CONFLICT DO NOTHING)
            for tr in result.test_results:
                ins = (
                    insert(TestResult)
                    .values(
                        id=uuid4(),
                        attempt_id=attempt_id,
                        test_index=tr.test_index,
                        verdict=tr.verdict.value,
                        execution_ms=tr.execution_ms,
                        memory_bytes=tr.memory_bytes,
                        stdout_excerpt=tr.stdout_excerpt,
                        stderr_excerpt=tr.stderr_excerpt,
                    )
                    .on_conflict_do_nothing(constraint="uq_test_result_attempt_index")
                )
                await session.execute(ins)

            await session.commit()
            logger.info(
                "Attempt %s finalized with verdict %s (%d/%d passed)",
                attempt_id,
                result.verdict.value,
                result.tests_passed,
                result.tests_total,
            )

        # 4. Emit execution.completed to Kafka
        if self.producer:
            payload = ExecutionCompletedPayload(
                attempt_id=attempt_id,
                submission_id=submission_id,
                verdict=result.verdict,
                execution_ms=result.execution_ms,
                cpu_ms=result.cpu_ms,
                peak_memory_bytes=result.peak_memory_bytes,
                tests_passed=result.tests_passed,
                tests_total=result.tests_total,
                artifact_uri=None,
            )
            envelope = EventEnvelope[ExecutionCompletedPayload](
                event_id=uuid4(),
                event_type="execution.completed",
                schema_version=1,
                occurred_at=now_utc,
                correlation_id=submission_id,
                causation_id=None,
                producer="result-collector",
                payload=payload,
            )
            topic = self.settings.KAFKA_TOPIC_EXECUTION_COMPLETED
            await self.producer.send_and_wait(
                topic=topic,
                key=str(attempt_id).encode("utf-8"),
                value=envelope.model_dump_json().encode("utf-8"),
            )

        return True

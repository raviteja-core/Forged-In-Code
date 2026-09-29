import asyncio
import json
import logging
from datetime import datetime, timezone
from uuid import UUID

from aiokafka import AIOKafkaConsumer
from collector import ResultCollector
from forgerun_contracts.config import get_settings
from forgerun_contracts.events import ExecutionScheduledEvent
from sqlalchemy import select, update
from sqlalchemy.orm import selectinload

from runner.adapters.python_adapter import execute_python_submission
from runner.core.models import ExecutionLimits, TestCase
from services.api.src.db.models import Submission, SubmissionAttempt
from services.api.src.db.session import AsyncSessionLocal

logger = logging.getLogger("forgerun.execution-controller")


class ExecutionController:
    def __init__(self, kafka_brokers: str | None = None):
        self.settings = get_settings()
        self.kafka_brokers = kafka_brokers or self.settings.KAFKA_BROKERS
        self.consumer: AIOKafkaConsumer | None = None
        self.result_collector = ResultCollector(self.kafka_brokers)
        self._running = False

    async def start(self) -> None:
        logger.info("Starting Execution Controller...")
        await self.result_collector.start()

        self.consumer = AIOKafkaConsumer(
            self.settings.KAFKA_TOPIC_EXECUTION_SCHEDULED,
            bootstrap_servers=self.kafka_brokers,
            group_id="forgerun-execution-controller",
            enable_auto_commit=False,
            auto_offset_reset="earliest",
        )
        await self.consumer.start()
        self._running = True

    async def stop(self) -> None:
        self._running = False
        if self.consumer:
            await self.consumer.stop()
        await self.result_collector.stop()

    async def process_attempt(self, attempt_id: UUID, submission_id: UUID) -> bool:
        """Loads submission and tests, marks attempt RUNNING, executes runner, and finalizes."""
        now_utc = datetime.now(timezone.utc)

        # 1. Fetch submission details and problem manifest
        async with AsyncSessionLocal() as session:
            stmt = (
                select(Submission)
                .where(Submission.id == submission_id)
                .options(selectinload(Submission.problem_version))
            )
            res = await session.execute(stmt)
            submission = res.scalar_one_or_none()
            if not submission:
                logger.error("Submission %s not found for attempt %s", submission_id, attempt_id)
                return False

            # Mark attempt as RUNNING
            upd = (
                update(SubmissionAttempt)
                .where(SubmissionAttempt.id == attempt_id)
                .values(status="RUNNING", started_at=now_utc)
            )
            await session.execute(upd)
            await session.commit()

            manifest = submission.problem_version.runtime_manifest
            raw_tests = manifest.get("test_cases", [])
            test_cases = [
                TestCase(input=t["input"], expected_output=t["expected_output"]) for t in raw_tests
            ]
            limits = ExecutionLimits(
                time_limit_ms=manifest.get("time_limit_ms", self.settings.DEFAULT_TIME_LIMIT_MS),
                memory_limit_mb=manifest.get(
                    "memory_limit_mb", self.settings.DEFAULT_MEMORY_LIMIT_MB
                ),
                max_output_bytes=manifest.get("max_output_bytes", self.settings.MAX_OUTPUT_BYTES),
            )
            source_code = submission.source_code

        # 2. Execute via language runner adapter in thread pool to avoid blocking asyncio event loop
        loop = asyncio.get_running_loop()
        runner_result = await loop.run_in_executor(
            None,
            execute_python_submission,
            source_code,
            test_cases,
            limits,
        )

        # 3. Finalize attempt via Result Collector
        await self.result_collector.finalize_attempt(
            attempt_id=attempt_id,
            submission_id=submission_id,
            result=runner_result,
        )

        return True

    async def process_one_event(self, timeout_sec: float = 3.0) -> bool:
        """Processes one scheduled execution event from Kafka."""
        if not self.consumer:
            raise RuntimeError("Consumer not started")

        try:
            msg = await asyncio.wait_for(self.consumer.getone(), timeout=timeout_sec)
        except asyncio.TimeoutError:
            return False

        try:
            data = json.loads(msg.value.decode("utf-8"))
            event = ExecutionScheduledEvent.model_validate(data)
            attempt_id = event.payload.attempt_id
            submission_id = event.payload.submission_id

            logger.info("Executing scheduled attempt %s (submission %s)", attempt_id, submission_id)
            success = await self.process_attempt(attempt_id, submission_id)
            if success:
                await self.consumer.commit()
            return success
        except Exception as e:
            logger.error("Failed to process scheduled event: %s", e)
            return False

    async def run_forever(self) -> None:
        await self.start()
        try:
            while self._running:
                await self.process_one_event(timeout_sec=1.0)
        finally:
            await self.stop()

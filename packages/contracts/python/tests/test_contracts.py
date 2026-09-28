import json
from uuid import uuid4

import pytest
from forgerun_contracts.config import Settings
from forgerun_contracts.enums import Language, Verdict
from forgerun_contracts.events import (
    EventEnvelope,
    SubmissionCreatedPayload,
)
from pydantic import ValidationError


def test_submission_created_event_roundtrip():
    payload = SubmissionCreatedPayload(
        submission_id=uuid4(),
        attempt_id=uuid4(),
        user_id=uuid4(),
        problem_version_id=uuid4(),
        language=Language.PYTHON,
        base_priority=50,
    )
    event = EventEnvelope(
        event_type="submission.created",
        correlation_id=uuid4(),
        producer="api-service",
        payload=payload,
    )

    json_str = event.model_dump_json()
    data = json.loads(json_str)

    assert data["event_type"] == "submission.created"
    assert data["schema_version"] == 1
    assert data["payload"]["language"] == "python"
    assert data["payload"]["base_priority"] == 50

    reconstructed = EventEnvelope[SubmissionCreatedPayload].model_validate_json(json_str)
    assert reconstructed.event_id == event.event_id
    assert reconstructed.payload.submission_id == payload.submission_id


def test_verdict_properties():
    assert Verdict.ACCEPTED == "ACCEPTED"
    assert Verdict.ACCEPTED.is_terminal
    assert not Verdict.ACCEPTED.is_infrastructure_failure
    assert Verdict.INFRASTRUCTURE_FAILURE.is_infrastructure_failure
    assert Verdict.SANDBOX_ERROR.is_infrastructure_failure


def test_invalid_settings_jwt_secret():
    with pytest.raises(ValidationError):
        # Secret too short (< 32 chars)
        Settings(JWT_SECRET="short-secret")


def test_valid_settings_defaults():
    settings = Settings(
        JWT_SECRET="0123456789abcdef0123456789abcdef0123456789abcdef",
    )
    assert settings.DEFAULT_TIME_LIMIT_MS == 2000
    assert settings.SANDBOX_RUNTIME_CLASS in ("runc", "runsc")
    assert settings.KAFKA_TOPIC_SUBMISSION_CREATED == "forge.submission.created.v1"

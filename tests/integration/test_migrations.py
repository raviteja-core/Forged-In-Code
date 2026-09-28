from sqlalchemy import inspect

from services.api.src.db.session import sync_engine


def test_schema_tables_exist():
    """Verify that all tables required by Section 8 of the spec exist after migrations."""
    inspector = inspect(sync_engine)
    table_names = set(inspector.get_table_names())

    expected_tables = {
        "users",
        "problems",
        "problem_versions",
        "submissions",
        "submission_attempts",
        "test_results",
        "outbox_events",
        "idempotency_keys",
    }

    assert expected_tables.issubset(table_names), f"Missing tables: {expected_tables - table_names}"


def test_required_indexes_exist():
    """Verify indexes on critical access patterns."""
    inspector = inspect(sync_engine)

    # Submissions indexes
    sub_indexes = {idx["name"] for idx in inspector.get_indexes("submissions")}
    assert "ix_submissions_user_created_desc" in sub_indexes

    # Submission attempts indexes
    attempt_indexes = {idx["name"] for idx in inspector.get_indexes("submission_attempts")}
    assert "ix_submission_attempts_status_scheduled" in attempt_indexes

    # Outbox events indexes
    outbox_indexes = {idx["name"] for idx in inspector.get_indexes("outbox_events")}
    assert "ix_outbox_events_published_created" in outbox_indexes

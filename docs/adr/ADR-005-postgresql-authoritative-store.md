# ADR-005: PostgreSQL as Authoritative State Store and Outbox Source

**Status:** Accepted  
**Date:** 2026-09-28  
**Deciders:** ForgeRun Engineering Team  

## Context
A code judging platform manages critical relational entities: users, problems, immutable problem versions, code submissions, execution attempts, individual test case results, and outbox events.
The system requires ACID guarantees to prevent inconsistencies such as:
1. Submissions recorded without corresponding execution attempt records.
2. Duplicate submissions created from identical client request IDs under network retries.
3. Verdict updates overwriting newer attempts out of order.
4. Loss of events between domain persistence and message bus publishing.

## Decision
PostgreSQL is designated as the sole authoritative source of truth for all persistent domain state in ForgeRun.
We enforce:
- UUID v4 primary keys for all tables.
- Foreign keys with referential integrity.
- Unique constraints on `(user_id, client_request_id)` for submission idempotency, `(submission_id, attempt_no)` for attempt ordering, and `(attempt_id, test_index)` for test results.
- Transactional Outbox pattern via `outbox_events` table within the same transaction that records submissions.
- Strict migration management using Alembic.
- Redis is strictly used as an ephemeral cache, rate limiter, and real-time counter—never as an authoritative store.

## Alternatives Considered
- **NoSQL / Document Store (MongoDB, DynamoDB):** Lacks native multi-table relational integrity, clean transactional outbox semantics, and flexible SQL indexing needed for multi-tenant analytics and audit queries.
- **Redis as primary store:** Fast in-memory operations, but lacks transactional durability guarantees under crash scenarios, persistence snapshots are asynchronous (RDB/AOF can lose data), and complex query capabilities are severely limited.
- **SQLite:** Suitable for embedded tools, but lacks multi-connection concurrent write scaling, distributed server architecture, and advanced enterprise indexing.

## Consequences
- **Positive:**
  - Complete ACID transaction semantics ensure zero orphan or half-created submissions.
  - Robust relational indexing (`(user_id, created_at DESC)`, `(status, scheduled_at)`).
  - Standardized tooling for backups, point-in-time recovery, and schema migrations.
- **Negative / Trade-offs:**
  - Requires connection pooling (Hikari / asyncpg / PgBouncer) under high concurrent load.
  - Requires deliberate index tuning to avoid write penalty on high-frequency tables.

## Security Impact
- Row-level security capabilities and principle of least privilege for database roles.
- Credentials stored securely in environment variables / AWS Secrets Manager.

## Operational Impact
- Regular vacuuming and index maintenance.
- Monitoring connection pool utilization and query execution plans via `EXPLAIN ANALYZE`.

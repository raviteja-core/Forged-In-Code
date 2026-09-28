# ADR-006: At-Least-Once Delivery Semantics with Idempotent Consumers

**Status:** Accepted  
**Date:** 2026-09-28  
**Deciders:** ForgeRun Engineering Team  

## Context
In distributed systems, achieving true end-to-end "exactly-once" delivery across multiple heterogeneous boundaries (HTTP client -> API -> DB Outbox -> Kafka -> Scheduler -> Execution Controller -> Kubernetes API -> Sandbox Job -> Result Collector -> DB) is mathematically impossible without two-phase commit protocols across all participating stores, which introduce severe availability and performance bottlenecks.
Network interruptions, pod restarts, consumer rebalances, and broker leader elections inevitably lead to duplicate message deliveries.

## Decision
ForgeRun adopts an **at-least-once messaging model coupled with strictly idempotent consumers** across all event pipelines:
1. Every event carries immutable identifiers: `event_id`, `correlation_id`, `submission_id`, and `attempt_id`.
2. The custom Rust scheduler suppresses duplicate `submission_id` enqueues using in-memory state backed by Redis deduplication keys.
3. The execution controller derives Kubernetes Job names deterministically from `attempt_id` (`forge-attempt-<attempt_id>`). If a duplicate `execution.scheduled` event is processed, Kubernetes returns an HTTP 409 Conflict (`AlreadyExists`), which the controller treats as a no-op success.
4. The result collector performs idempotent SQL updates: terminal state transitions cannot revert, and updates match on `(attempt_id, status)` guards.
5. Kafka consumer offsets are committed only after the consumer has successfully processed the event or safely recorded its state.

## Alternatives Considered
- **Claiming End-to-End Exactly-Once Processing:** Unrealistic and fragile. Kafka's transactional producer only guarantees exactly-once processing within Kafka-to-Kafka topologies (Kafka Streams), not when interacting with external systems like Kubernetes API or PostgreSQL.
- **At-Most-Once Delivery (auto-commit offsets before processing):** Dropped messages would lead to silent loss of user submissions without retry, which violates core system requirements.

## Consequences
- **Positive:**
  - High resilience: services can crash, restart, or rebalance at any time without data corruption or state duplication.
  - Clear architectural clarity: avoids illusory claims of exactly-once delivery.
- **Negative / Trade-offs:**
  - Every consumer must implement idempotency checks and deterministic key generation.
  - State machine must enforce forward-only terminal transitions (e.g. terminal states cannot transition back to `RUNNING`).

## Security Impact
- Prevents resource exhaustion attacks where malicious duplicate messages spawn unbounded parallel execution containers.

## Operational Impact
- Simplifies operational recovery: operators can safely replay Kafka topics from earlier offsets to recover from service outages.

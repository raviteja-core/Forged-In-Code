# ADR-001: Event-Driven Architecture with Transactional Outbox

**Status:** Accepted  
**Date:** 2026-09-28  
**Deciders:** ForgeRun Engineering Team  

## Context
Code execution and judging is fundamentally an asynchronous, long-running, and bursty workload. Compiling and running code against multiple test suites takes from hundreds of milliseconds to tens of seconds. Synchronous HTTP execution would block client connections, exhaust web server worker pools under load, provide no durable buffering during worker outages, and tie API availability directly to execution node health.

Furthermore, if the API server directly calls an external message broker after writing to the database, any crash or network partition between the DB commit and broker publish results in lost submissions (dual-write problem).

## Decision
ForgeRun adopts an event-driven architecture decoupled across service boundaries using an asynchronous message broker (Kafka). 
To eliminate the dual-write problem, the API commits submission records and corresponding outbox events within a single ACID transaction in PostgreSQL. A dedicated, lightweight `outbox-publisher` reads unpublished events from `outbox_events` and publishes them to Kafka with at-least-once delivery.

## Alternatives Considered
- **Direct Synchronous API Execution:** Execute code synchronously in the API worker or via synchronous gRPC calls to workers. Rejected because compile/execution times block HTTP worker threads, burst traffic causes massive timeouts, and worker restarts drop submissions permanently.
- **Dual-write API to DB + Kafka directly:** Write to DB and publish to Kafka in the API route handler. Rejected because if the process dies or Kafka is partitioned between the DB commit and Kafka ack, state becomes inconsistent and the submission is orphaned.
- **In-memory job queues (Celery/BullMQ):** Rejected because they lack durable partitioned replay semantics, consumer group scaling across multiple downstream services, and multi-tenant partitioning guarantees.

## Consequences
- **Positive:**
  - Complete decoupling between user submission ingestion and code execution.
  - Resilience against execution plane outages; pending submissions accumulate safely in the outbox/Kafka.
  - Guaranteed zero-loss submission ingestion via atomic database outbox.
- **Negative / Trade-offs:**
  - End-to-end latency increases slightly (polling/notifying outbox publisher + Kafka hop).
  - Requires status streaming (SSE/polling) to notify clients when jobs complete.
  - Consumers must handle duplicate events.

## Security Impact
- Ingestion API does not require direct network access or credentials to execution runners or Kubernetes clusters.
- Minimizes the blast radius of any API compromise.

## Operational Impact
- Requires monitoring of the outbox table backlog and publication lag.
- Clean database indexing (`published_at, created_at`) is mandatory to avoid table scan overhead on the outbox.

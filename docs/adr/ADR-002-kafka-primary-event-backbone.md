# ADR-002: Apache Kafka / Redpanda as Primary Event Backbone

**Status:** Accepted  
**Date:** 2026-09-28  
**Deciders:** ForgeRun Engineering Team  

## Context
The platform requires an event backbone for dispatching submission events, scheduling attempts, and routing results between API, custom scheduler, execution controller, and telemetry collectors. The event store must support high throughput, partition-based ordering, consumer group rebalancing, event replay for failure recovery, and horizontal scalability.

## Decision
We select Apache Kafka (with Redpanda as a fully compatible, lightweight drop-in for local development and integration testing) as the primary event backbone.
Topics are organized with explicit schema versioning (e.g., `forge.submission.created.v1`, `forge.execution.scheduled.v1`). Partitions are keyed on `user_id` or `attempt_id` to guarantee ordering where required.

## Alternatives Considered
- **Redis Streams / PubSub:** Redis PubSub is non-durable. Redis Streams supports consumer groups, but lacks native high-performance partitioned log storage, broker-enforced retention policies, and robust ecosystem tooling for consumer rebalancing and audit replay under heavy distributed workloads.
- **RabbitMQ:** RabbitMQ queues delete messages upon consumer acknowledgement, making replay during incident triage or scheduler crash recovery difficult. Partitioning and consumer group scaling are also less ergonomic than Kafka's log abstraction.
- **AWS SQS:** Lacks native event replay, strict partitioned ordering across high cardinality keys without FIFO queue performance bottlenecks, and cannot be run natively in local Docker Compose environments without heavy mocks.

## Consequences
- **Positive:**
  - True append-only, partitioned durable log with deterministic offsets.
  - Ability to replay events from any offset during service recovery or algorithm tuning.
  - Native consumer group model enabling independent scaling of schedulers and execution controllers.
- **Negative / Trade-offs:**
  - Operational overhead of Kafka/Redpanda broker management.
  - Consumers must explicitly manage offsets and handle at-least-once delivery duplicates.

## Security Impact
- Topic-level ACLs and TLS encryption in transit prevent unauthorized service snooping.
- User code execution pods have no network reachability to the Kafka broker.

## Operational Impact
- Requires Prometheus JMX/native exporter to monitor consumer lag, partition distribution, and under-replicated partitions.
- Local development uses Redpanda container (single binary, KRaft compatible, zero ZooKeeper overhead).

# Architecture Decision Records (ADRs)

This directory documents the foundational architectural decisions for the ForgeRun platform. Every major architectural decision must be recorded here with context, decision, alternatives, consequences, security impact, and operational impact.

## Index of Records

| ADR | Title | Status | Date |
| --- | ----- | ------ | ---- |
| [ADR-001](ADR-001-event-driven-architecture.md) | Event-Driven Architecture with Transactional Outbox | Accepted | 2026-09-28 |
| [ADR-002](ADR-002-kafka-primary-event-backbone.md) | Apache Kafka / Redpanda as Primary Event Backbone | Accepted | 2026-09-28 |
| [ADR-003](ADR-003-per-attempt-kubernetes-jobs.md) | Per-Attempt Ephemeral Kubernetes Jobs for Sandbox Execution | Accepted | 2026-09-28 |
| [ADR-004](ADR-004-gvisor-container-sandbox.md) | gVisor RuntimeClass for Hostile Untrusted Code Execution | Accepted | 2026-09-28 |
| [ADR-005](ADR-005-postgresql-authoritative-store.md) | PostgreSQL as Authoritative State Store and Outbox Source | Accepted | 2026-09-28 |
| [ADR-006](ADR-006-at-least-once-idempotent-consumers.md) | At-Least-Once Delivery Semantics with Idempotent Consumers | Accepted | 2026-09-28 |
| [ADR-007](ADR-007-scheduler-fairness-algorithm.md) | Partition-Aware Priority Queue with Aging and Per-Tenant Fairness | Accepted | 2026-09-28 |
| [ADR-008](ADR-008-dedicated-runner-node-group.md) | Dedicated Runner Node Group with Taints and Tolerations | Accepted | 2026-09-28 |
| [ADR-009](ADR-009-managed-aws-services.md) | Managed AWS Services (RDS, ElastiCache, EKS) with Terraform IaC | Accepted | 2026-09-28 |
| [ADR-010](ADR-010-sse-status-streaming.md) | Server-Sent Events (SSE) for Real-Time Execution Status Updates | Accepted | 2026-09-28 |

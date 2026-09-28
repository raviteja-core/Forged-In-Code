# ADR-007: Scheduler Fairness Algorithm: Partition-Aware Heap with Aging

**Status:** Accepted  
**Date:** 2026-09-28  
**Deciders:** ForgeRun Engineering Team  

## Context
In an online code judging platform, aggressive users or bot accounts can submit hundreds of submissions within seconds. If a standard FIFO (First-In, First-Out) queue is used, a single tenant can monopolize all runner capacity, causing complete starvation for other users.
Conversely, strict round-robin can penalize small users when queues are bursty, and static priority systems allow high-priority queues to starve lower-priority submissions indefinitely.

## Decision
We implement a custom scheduler in Rust utilizing:
1. **Per-Partition Isolation:** Scheduler instances consume specific Kafka partitions keyed on `user_id`.
2. **Per-Tenant Subqueues:** Submissions from each tenant (`user_id`) are maintained in separate FIFO queues.
3. **Heap-Backed Priority Selection:** An active heap stores candidate queues ordered by effective priority.
4. **Effective Priority with Aging Bonus:**
   $$\text{effective\_priority} = \text{base\_priority} + \min\left(\text{MAX\_AGING\_BONUS}, \left\lfloor \frac{\text{wait\_seconds}}{\text{AGING\_INTERVAL}} \right\rfloor \times \text{AGING\_STEP}\right)$$
   To avoid $O(N)$ re-indexing of all queue elements every second, effective priority is computed lazily upon candidate inspection and insertion.
5. **Deterministic Tie-Breaking:** Tie-breaking uses submission creation timestamp and a strictly monotonic sequence counter.
6. **Concurrency Quotas:** Enforced using Redis atomic counters (`quota:user:{user_id}` and `quota:global`). If a user exceeds their concurrent execution limit, their submissions remain queued until active jobs finish.

## Alternatives Considered
- **Simple Global FIFO Queue:** Trivial to implement, but vulnerable to complete tenant starvation and resource monopolization.
- **Deficit Round Robin (DRR):** Well-suited for packet networks, but less flexible for dynamic submission priority levels and SLA-based aging bonuses.
- **External Workflow Orchestrators (Temporal / Airflow):** Overkill for sub-second code scheduling; introduces massive latency and dependencies.

## Consequences
- **Positive:**
  - Guaranteed starvation resistance: low-priority tasks gradually age up and are scheduled.
  - Per-tenant fairness prevents single-user denial of service on cluster capacity.
  - Predictable $O(\log N)$ enqueue/dequeue performance implemented with zero-allocation data structures in Rust.
- **Negative / Trade-offs:**
  - Additional scheduler code complexity requiring comprehensive unit tests, property tests, and Criterion benchmarks.
  - Requires atomic quota tracking in Redis.

## Security Impact
- Protects cluster compute capacity against denial-of-service and "noisy neighbor" attacks.

## Operational Impact
- Metrics emitted: `queue_depth_by_tenant`, `scheduling_latency_ms`, `effective_priority_distribution`, `fairness_inversions_count`.

# Scheduler Criterion Benchmark Report

**Date:** 2026-09-29  
**Target:** `forgerun-scheduler` (`services/scheduler`)  
**Benchmarking Harness:** Criterion.rs 0.5.1  
**Hardware Environment:**
- **CPU:** Intel(R) Core(TM) i7-9850H CPU @ 2.60GHz (12 vCPUs)
- **OS:** Ubuntu Linux (x86_64)
- **Rust Toolchain:** rustc 1.85+ (stable), Cargo release profile (`[profile.bench] opt-level = 3`)

---

## 1. Executive Summary

The ForgeRun custom scheduler is implemented in Rust to provide starvation-resistant, tenant-fair task scheduling over Kafka partitions. Benchmark results demonstrate:
- **Enqueue Throughput:** **~10.05 million tasks/sec** (99.45 µs per 1,000 tasks across 100 tenants).
- **Dequeue Throughput:** **~489,800 tasks/sec** (10.207 ms for 5,000 tasks with lazy aging calculations and heap maintenance).
- **Duplicate Suppression:** **26.14 nanoseconds** per duplicate Kafka event (~38.2 million suppressions/sec).
- **Fairness Under Tenant Overload (Spam Resistance):** **21.19 µs** per scheduling cycle under a 200-task denial-of-service burst, correctly prioritizing starved normal users without priority inversion.

---

## 2. Benchmark Results Table

| Benchmark Target | Workload Description | Measured Mean Latency | Effective Throughput | Outliers Detected |
|---|---|---|---|---|
| `scheduler_enqueue/tenants/10` | 1,000 tasks across 10 tenants | 110.39 µs | **9.05 M ops/sec** | 9.0% |
| `scheduler_enqueue/tenants/100` | 1,000 tasks across 100 tenants | 99.45 µs | **10.05 M ops/sec** | 2.0% |
| `scheduler_enqueue/tenants/500` | 1,000 tasks across 500 tenants | 140.04 µs | **7.14 M ops/sec** | 2.0% |
| `scheduler_dequeue/tasks/100` | 100 tasks across 50 tenants | 243.79 µs | **410.2 K ops/sec** | 2.0% |
| `scheduler_dequeue/tasks/1000` | 1,000 tasks across 50 tenants | 2.218 ms | **450.8 K ops/sec** | 11.0% |
| `scheduler_dequeue/tasks/5000` | 5,000 tasks across 50 tenants | 10.207 ms | **489.8 K ops/sec** | 6.0% |
| `scheduler_duplicate_suppression` | Instant deduplication check | 26.14 ns | **38.2 M ops/sec** | 4.0% |
| `scheduler_fairness_under_spam` | 200 spam jobs vs 10 normal users | 21.19 µs | **47.1 K fair cycles/sec** | 14.0% |

---

## 3. Algorithmic Analysis

### 3.1 Lazy Aging Calculation ($O(M)$ vs $O(N)$)
Traditional priority queues with time-decaying aging require re-scoring all $N$ elements every tick ($O(N)$), which collapses under 100,000 submissions. 

ForgeRun stores submissions in per-tenant FIFO queues (`VecDeque<QueuedTask>`) and exposes only the *head* of each active tenant queue to the candidate heap.
- With $N = 10,000$ queued tasks across $M = 50$ active tenants, the candidate heap contains at most 50 elements.
- Re-scoring is performed lazily only on candidate heads during `try_schedule_next()`.
- Unscheduled tasks behind the tenant head remain in $O(1)$ sequential FIFO memory, resulting in sub-millisecond dequeue latencies.

### 3.2 Tenant Concurrency Quotas
When a tenant exceeds their concurrency limit (`per_user_max_concurrency`), their candidate is skipped in $O(1)$ and deferred until a running job completes (`on_attempt_completed`). This prevents "noisy neighbor" tenants from starving legitimate submissions, as verified in `test_per_user_concurrency_quota_prevents_tenant_monopolization`.

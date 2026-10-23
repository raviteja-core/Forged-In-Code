# ForgeRun Project Trajectory & Master AI Reference Document

> **Purpose:** This document is the canonical reference manual and project trajectory history for ForgeRun. Any AI assistant or engineer starting a new session can read this single document to understand the original architecture, exact historical implementation progress across all phases, key design patterns, file locations, and the precise next steps without needing to re-scan the entire codebase.

---

## 1. Project Overview & Non-Negotiable Architecture Rules

**ForgeRun** is a distributed online code execution and judging platform designed as an industry-grade distributed systems project.

### Canonical Specification
- Canonical design document: [`ForgeRun_AI_Reference_Architecture.md`](file:///home/faith/folder/forgerun/ForgeRun_AI_Reference_Architecture.md)
- Root workspace: `/home/faith/folder/forgerun`
- Technology Stack: Python (FastAPI, SQLAlchemy, Alembic, aiokafka), Rust (Custom Scheduler, Tokio, rdkafka), PostgreSQL 16, Redpanda/Kafka, Redis 7.2, Kubernetes & gVisor.

### Non-Negotiable Design Rules
1. **Real Kafka Event Backbone**: Do not replace Kafka with in-process channels or lightweight queues.
2. **Real PostgreSQL**: Do not replace PostgreSQL with SQLite. Uses Alembic for migrations and asyncpg connection pooling (`poolclass=NullPool` for clean multi-loop test compatibility).
3. **Real Custom Rust Scheduler**: Algorithmic showcase. Uses per-tenant FIFO subqueues, $O(M)$ lazy wait-time priority aging, deterministic tie-breaking, and concurrency quotas.
4. **At-Least-Once Delivery with Idempotent Consumers**: Never claim "exactly-once" messaging. All consumers and database updates must be strictly idempotent (`client_request_id` unique constraints, `uq_test_result_attempt_index` with `ON CONFLICT DO NOTHING`, attempt deduplication sets).
5. **No Code Execution in API or Controller**: The control plane delegates all untrusted code compilation and execution to isolated runner sandboxes.
6. **No Fake/Invented Benchmarks**: All performance numbers reported in documentation and resumes are measured via Criterion and real cluster tests.
7. **Commit Messages Rule**: Use plain, descriptive sentences (e.g. `Implement Phase 4 security hardening...`) and NEVER use conventional commit prefixes like `feat(runner):`.

---

## 2. Core Execution Flow (End-to-End Pipeline)

```text
Browser / Client (HTTP POST /api/v1/submissions)
    │
    ▼
FastAPI API Gateway (`services/api/src/routes/submissions.py`)
    │ (Checks idempotency key; writes submission + outbox event in single ACID transaction)
    ▼
PostgreSQL Database (`outbox_events` table)
    │
    ▼ (Async polling daemon: `services/outbox-publisher/publisher.py`)
Kafka Topic: `forge.submission.created.v1`
    │
    ▼
Rust Scheduler Engine (`services/scheduler/src/engine.rs`)
    │ (Per-tenant FIFO queues -> Max-Heap with lazy wait-time aging -> Quota tracker)
    ▼
Kafka Topic: `forge.execution.scheduled.v1`
    │
    ▼
Execution Controller (`services/execution-controller/controller.py`)
    │ (Marks attempt RUNNING; dispatches to multi-language sandbox runner)
    ▼
Language Sandbox Runner (`runner/dispatcher.py` -> Python / C++ / Java / Rust)
    │ (Compiles if required; executes tests in unshare/gVisor sandbox with limits)
    ▼
Result Collector (`services/result-collector/collector.py`)
    │ (Finalizes attempt verdict in PostgreSQL idempotently; records test_results)
    ▼
Kafka Topic: `forge.execution.completed.v1` (Frees scheduler concurrency slot)
    │
    ▼
Browser / Client (Server-Sent Events SSE: `/api/v1/submissions/{id}/events` or GET `/api/v1/submissions/{id}`)
```

---

## 3. Phase-by-Phase Implementation History

### Phase 0 — Foundations (Completed)
- **10 Architecture Decision Records** (`docs/adr/ADR-001` through `ADR-010`):
  - ADR-001: Event-Driven Architecture & Outbox Pattern
  - ADR-002: Kafka as Primary Event Backbone
  - ADR-003: PostgreSQL Schema & Concurrency Strategy
  - ADR-004: Redis for Rate Limiting & Ephemeral Quotas
  - ADR-005: gVisor Sandbox Isolation Boundary
  - ADR-006: Kubernetes-Native Execution via Ephemeral Jobs
  - ADR-007: Scheduler Fairness Algorithm (Partition-Aware Heap with Aging)
  - ADR-008: OpenTelemetry Tracing & Observability
  - ADR-009: Idempotency & Retry Semantics
  - ADR-010: Supply Chain Security & Immutable Containers
- **Infrastructure Setup**:
  - `docker-compose.yml`: PostgreSQL 16 (port 5432), Redis 7.2 (port 6379), Redpanda Kafka (port 9092).
- **Database Migrations**:
  - Alembic migration `0001_initial_schema.py` creating: `problems`, `problem_versions`, `users`, `submissions`, `submission_attempts`, `test_results`, `outbox_events`, `idempotency_keys`.
- **Shared Event Contracts**:
  - Python: `packages/contracts/python/forgerun_contracts` (Pydantic models, Enums, Settings).
  - Rust: `packages/contracts/rust/src` (Serde models, EventEnvelope, Enums).
- **CI/CD Pipeline**:
  - `.github/workflows/ci.yml` with Python linting, pytest, Rust fmt, Clippy, and Cargo tests.

---

### Phase 1 — Vertical Slice (Completed)
- **Catalog Seeding**: `problems/catalog/two_sum.json` and `services/api/src/db/seed.py`.
- **FastAPI Ingress**: `services/api/src/routes/submissions.py` handling submissions, idempotency keys, and SSE streaming.
- **Outbox Publisher**: `services/outbox-publisher/publisher.py` polling `outbox_events` and publishing to Kafka.
- **Initial Scheduler**: `services/scheduler/src/main.rs` & `engine.rs` consuming Kafka, deduplicating attempts, and publishing `execution.scheduled`.
- **Python Sandbox Runner**: `runner/adapters/python_adapter.py` executing Python test cases with CPU and memory limits.
- **Execution Controller & Collector**: `services/execution-controller/controller.py` and `services/result-collector/collector.py`.
- **All 6 Mandatory Acceptance Criteria Verified** (`tests/e2e/test_vertical_slice.py`):
  1. Correct Python -> `ACCEPTED`
  2. Wrong Python -> `WRONG_ANSWER`
  3. Infinite loop -> `TIME_LIMIT`
  4. Excessive output -> `OUTPUT_LIMIT`
  5. Duplicate client_request_id -> idempotent cached response
  6. Duplicate Kafka event -> idempotent suppression

---

### Phase 2 — Scheduler Depth (Completed)
- **Queue Architecture** ([`services/scheduler/src/queue.rs`](file:///home/faith/folder/forgerun/services/scheduler/src/queue.rs)):
  - `TenantQueue`: Per-user FIFO `VecDeque<QueuedTask>` preventing head-of-line jumping.
  - `HeapCandidate`: Priority heap entry with deterministic tie-breaking (Priority -> Timestamp -> Sequence -> UUID).
- **Lazy Aging Calculation** ([`services/scheduler/src/engine.rs`](file:///home/faith/folder/forgerun/services/scheduler/src/engine.rs)):
  - Formula: $\text{effective\_priority} = \text{base\_priority} + \min(\text{MAX\_BONUS}, \lfloor\text{wait} / \text{INTERVAL}\rfloor \times \text{STEP})$.
  - Bounded candidate heap: with $N$ queued tasks across $M$ active tenants, only $M$ heads are in the heap ($M \ll N$), achieving $O(M)$ refresh with zero full-queue re-scoring.
- **Concurrency Quotas** ([`services/scheduler/src/quota.rs`](file:///home/faith/folder/forgerun/services/scheduler/src/quota.rs)):
  - Enforces `per_user_max_concurrency` and `global_max_concurrency`. Saturated tenants are deferred without starving other users.
- **Criterion Benchmark Suite** ([`services/scheduler/benches/scheduler_bench.rs`](file:///home/faith/folder/forgerun/services/scheduler/benches/scheduler_bench.rs)):
  - Measured results on Intel i7-9850H (12 vCPUs) documented in [`docs/benchmarks/scheduler_benchmarks.md`](file:///home/faith/folder/forgerun/docs/benchmarks/scheduler_benchmarks.md):
    - Enqueue Throughput: **10.05 million tasks/sec** (99.45 µs / 1,000 tasks)
    - Dequeue Throughput: **489,800 tasks/sec** (10.2 ms / 5,000 tasks)
    - Duplicate Suppression: **26.14 nanoseconds / event** (38.2 million ops/sec)
    - Fairness Overhead: **21.19 µs / cycle** under 200-task spam denial-of-service burst.

---

### Phase 3 — Execution Platform (Completed)
- **Runtime Policy Manifests** ([`runner/core/manifest.py`](file:///home/faith/folder/forgerun/runner/core/manifest.py)):
  - Policies for Python, C++, Java, and Rust with compilation timeouts, source filenames, binary names, and execution flags.
- **Multi-Language Runner Adapters**:
  - C++ Adapter ([`runner/adapters/cpp_adapter.py`](file:///home/faith/folder/forgerun/runner/adapters/cpp_adapter.py)): `g++ -O2 -std=c++20`.
  - Java Adapter ([`runner/adapters/java_adapter.py`](file:///home/faith/folder/forgerun/runner/adapters/java_adapter.py)): `javac Solution.java`, `java -Xmx{mem}m -Xms16m -XX:+UseSerialGC Solution`.
  - Rust Adapter ([`runner/adapters/rust_adapter.py`](file:///home/faith/folder/forgerun/runner/adapters/rust_adapter.py)): `rustc -O solution.rs -o solution`.
  - Central Dispatcher ([`runner/dispatcher.py`](file:///home/faith/folder/forgerun/runner/dispatcher.py)).
- **Compilation Diagnostics**:
  - Syntax errors in C++, Java, and Rust emit `Verdict.COMPILE_ERROR` with compiler stderr excerpts and 0 test cases executed.
- **Multi-Language End-to-End Suite** ([`tests/e2e/test_multi_language.py`](file:///home/faith/folder/forgerun/tests/e2e/test_multi_language.py)):
  - End-to-end acceptance tests passed for C++, Java, Rust, and their compilation error paths.

---

### Phase 4 — Security Hardening (Current Stage)
- **gVisor RuntimeClass** ([`deploy/runtimeclasses/gvisor.yaml`](file:///home/faith/folder/forgerun/deploy/runtimeclasses/gvisor.yaml)):
  - `handler: runsc` with overhead allocations and nodeSelector for gVisor-enabled nodes.
- **Kubernetes Restricted Pod Security** ([`deploy/policies/pod-security-standards.yaml`](file:///home/faith/folder/forgerun/deploy/policies/pod-security-standards.yaml)):
  - `forge-runner` namespace labeled with `pod-security.kubernetes.io/enforce: restricted`.
  - `ResourceQuota` and `LimitRange` bounding namespace compute, memory, and ephemeral storage.
- **Zero-Trust NetworkPolicies**:
  - Runner Isolation ([`deploy/policies/network-policy-runner.yaml`](file:///home/faith/folder/forgerun/deploy/policies/network-policy-runner.yaml)): Denies all Ingress, all Egress, and DNS queries from sandbox pods.
  - Control Plane Policy ([`deploy/policies/network-policy-control-plane.yaml`](file:///home/faith/folder/forgerun/deploy/policies/network-policy-control-plane.yaml)): Locks control services to internal communication.
- **Hardened Sandbox Job Template** ([`deploy/policies/runner-job-template.yaml`](file:///home/faith/folder/forgerun/deploy/policies/runner-job-template.yaml)):
  - Non-root user (`runAsNonRoot: true`, UID `65534`), `readOnlyRootFilesystem: true`, `capabilities: drop: ["ALL"]`, `seccompProfile: RuntimeDefault`, `automountServiceAccountToken: false`.
  - Dedicated runner node taints and tolerations (`dedicated=runner:NoSchedule`).
- **Immutable Rootless Dockerfiles**:
  - [`runner/images/python/Dockerfile`](file:///home/faith/folder/forgerun/runner/images/python/Dockerfile)
  - [`runner/images/cpp/Dockerfile`](file:///home/faith/folder/forgerun/runner/images/cpp/Dockerfile)
  - [`runner/images/java/Dockerfile`](file:///home/faith/folder/forgerun/runner/images/java/Dockerfile)
  - [`runner/images/rust/Dockerfile`](file:///home/faith/folder/forgerun/runner/images/rust/Dockerfile)
- **Host & Local Isolation**:
  - `SAFE_SUBPROCESS_ENV`: Excludes host environment variables (`DATABASE_URL`, `JWT_SECRET_KEY`, cloud credentials) from execution subprocesses.
  - `wrap_with_sandbox`: Uses Linux user and network namespaces (`unshare -r -n`) to disable outbound network access even in local execution.
  - Process limits (`RLIMIT_AS`, `RLIMIT_CORE`, `RLIMIT_FSIZE`, `RLIMIT_NPROC`).
- **Security Test Suite** ([`tests/security/`](file:///home/faith/folder/forgerun/tests/security)):
  - `test_environment_isolation.py`: Verifies database credentials and secrets are never exposed to submissions.
  - `test_network_restrictions.py`: Verifies socket connections and DNS resolution fail.
  - `test_filesystem_boundaries.py`: Verifies `/var/run/secrets` cannot be accessed, system directories are protected, and disk exhaustion is caught by `RLIMIT_FSIZE`.
  - `test_privilege_escalation.py`: Verifies `CAP_NET_RAW` (raw sockets) and `setuid(0)` are denied.
  - `test_process_limits.py`: Verifies memory limits, infinite loops, and controlled process probes.

---

## 4. Key Repository Files & Directory Guide

```text
forgerun/
├── ForgeRun_AI_Reference_Architecture.md    # Canonical architectural blueprint
├── docker-compose.yml                       # Postgres 16, Redis 7.2, Redpanda Kafka
├── packages/contracts/
│   ├── python/forgerun_contracts/           # Pydantic models, Enums, Settings
│   └── rust/src/                            # Serde models, EventEnvelope
├── services/
│   ├── api/                                 # FastAPI control plane & Alembic migrations
│   │   ├── migrations/                      # Alembic schema versions
│   │   └── src/routes/                      # /submissions, /problems
│   ├── scheduler/                           # Custom Rust priority & fairness engine
│   │   ├── src/                             # queue.rs, quota.rs, engine.rs, lib.rs, main.rs
│   │   └── benches/                         # Criterion benchmarks
│   ├── execution-controller/                # Consumes scheduled attempts; routes to runner
│   ├── result-collector/                    # Finalizes attempt verdicts in PostgreSQL
│   └── outbox-publisher/                    # Transactional outbox polling daemon
├── runner/
│   ├── core/                                # manifest.py, models.py
│   ├── adapters/                            # python_adapter.py, cpp_adapter.py, java_adapter.py, rust_adapter.py
│   ├── dispatcher.py                        # Central language dispatcher
│   └── images/                              # Dockerfiles for python, cpp, java, rust
├── deploy/
│   ├── policies/                            # NetworkPolicies, Pod Security, Job template
│   └── runtimeclasses/                      # gVisor runtime class definition
├── problems/
│   └── catalog/                             # two_sum.json problem definitions
├── docs/
│   ├── adr/                                 # ADR-001 through ADR-010
│   ├── benchmarks/                          # scheduler_benchmarks.md
│   └── PROJECT_TRAJECTORY_REFERENCE.md      # This master document
└── tests/
    ├── unit/                                # Language runner & dispatcher tests
    ├── integration/                         # Outbox & migration tests
    ├── e2e/                                 # Vertical slice & multi-language pipeline tests
    └── security/                            # Hardening & exploit mitigation test suite
```

---

## 5. Next Planned Phases (Roadmap)

1. **Phase 5 — Observability**:
   - OpenTelemetry tracing and span propagation across API, Kafka, Scheduler, and Runners.
   - Prometheus metrics exposition (`queue_depth`, `scheduling_latency_ms`, `verdict_counts_total`).
   - Grafana dashboards (`overview.json`, `scheduler.json`, `cluster.json`).
   - Loki logging integration.
2. **Phase 6 — Cloud Infrastructure**:
   - Terraform manifests for AWS VPC, EKS cluster, RDS PostgreSQL, Valkey/Redis, S3, ECR.
   - IAM OIDC roles and service accounts.
3. **Phase 7 — Reliability & Chaos**:
   - Chaos and failure injection (scheduler restarts under load, stale attempt reaper, broker disconnects).
   - Reconciliation loop for lost runner jobs.
4. **Phase 8 — Load Benchmarking & Portfolio Showcase**:
   - k6 API load test scripts (100+ concurrent users, latency distributions P50/P95/P99).
   - Demo video assets and measured resume bullets.

---

## 6. How to Run & Verify

```bash
# 1. Start Infrastructure
docker compose up -d

# 2. Run Database Migrations & Seed
.venv/bin/alembic upgrade head
.venv/bin/python services/api/src/db/seed.py

# 3. Run Rust Tests and Benchmarks
cargo test --workspace
cargo bench -p forgerun-scheduler --bench scheduler_bench

# 4. Run Pytest Test Suite
.venv/bin/pytest -v

# 5. Check Linting & Formatting
cargo fmt --all --check
cargo clippy --workspace -- -D warnings
.venv/bin/ruff format --check .
.venv/bin/ruff check .
```

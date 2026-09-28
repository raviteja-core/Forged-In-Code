# ForgeRun Benchmark Methodology and Results

## Non-Negotiable Rule
All performance numbers and latency statistics reported in project documentation or resumes must be backed by real, recorded benchmarks executed on documented hardware configurations. No invented numbers are permitted.

## Benchmark Test Matrix
1. **Scheduler Data Structures (Criterion.rs):**
   - Heap enqueue/dequeue throughput across 10,000 tenants.
   - Effective priority recomputation overhead.
   - Deduplication hash set performance under high collision rates.
2. **Control Plane / API (k6):**
   - P50, P95, P99 latency under 100 concurrent submitters.
   - Maximum sustainable requests per second (RPS) before database connection saturation.
3. **End-to-End Pipeline Latency:**
   - Deconstructed latency: `Ingress -> API -> Outbox -> Kafka -> Scheduler -> Controller -> Kubernetes Pod Scheduling -> Runner Execution -> Result Collector -> DB Commit`.
   - Measurement of queue latency vs execution latency.

# ForgeRun Testing Strategy

## Testing Pyramid

### 1. Unit Tests
- **API:** Request validation, authentication/JWT, outbox transactional guarantees, error taxonomy serialization.
- **Scheduler (Rust):** Heap ordering, starvation prevention, tenant aging math, quota checks, duplicate event suppression.
- **Runner:** Test execution harness, process limits, timeout traps, stdout/stderr byte truncation.

### 2. Integration Tests
- Ephemeral test containers (PostgreSQL, Redis, Kafka/Redpanda).
- Outbox publishing verification.
- Idempotency key conflict tests.
- Re-drive of duplicate Kafka messages.

### 3. End-to-End Tests
- Executed against local Kubernetes (kind/k3d).
- Full pipeline validation from submission POST to ACCEPTED verdict in PostgreSQL.
- Verifying client idempotency under duplicate requests.

### 4. Security Tests (`tests/security`)
- Attempted egress network connection (must fail).
- Attempted service account token discovery (`/var/run/secrets/kubernetes.io/serviceaccount` must not exist).
- Fork bomb and process explosion (must be terminated by cgroups).
- Infinite loop (must trigger TIME_LIMIT).
- Infinite output generator (must trigger OUTPUT_LIMIT).
- Memory allocation bomb (must trigger MEMORY_LIMIT).

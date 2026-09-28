# ADR-003: Per-Attempt Ephemeral Kubernetes Jobs for Sandbox Execution

**Status:** Accepted  
**Date:** 2026-09-28  
**Deciders:** ForgeRun Engineering Team  

## Context
Code execution platforms frequently struggle with sandbox leakage: state left behind by a previous user program (files in `/tmp`, orphan background processes, network socket bindings, memory fragmentation, altered system state). 
Additionally, long-running execution daemon pods that execute arbitrary user binaries require complex cleanup scripts, custom cgroup management, and risk container breakout or state poisoning across distinct submissions.

## Decision
ForgeRun executes every code submission attempt inside an ephemeral, single-purpose Kubernetes Job running in a dedicated `forge-runner` namespace.
Each Job:
1. Runs exactly one execution attempt with a deterministic name (`forge-attempt-<attempt_id>`).
2. Has `restartPolicy: Never` and an explicit `activeDeadlineSeconds`.
3. Mounts empty temporary storage (`emptyDir`), dropping all state upon pod termination.
4. Cleans up automatically via TTL (`ttlSecondsAfterFinished`).

## Alternatives Considered
- **Persistent Worker Daemon Pool (warm containers):** Reusing long-lived pods to execute multiple code submissions sequentially. While latency is lower, state isolation between hostile submissions is extremely difficult to guarantee, risking cross-tenant data leaks and persistent host tampering.
- **Docker-in-Docker / Containerd socket mounting:** Running an executor that talks to the host Docker daemon. Exposes the host container socket, which grants immediate root privilege over the host node. Strongly rejected.
- **Serverless / AWS Lambda:** Restricts custom compilation environments, language runtime flags, and local offline testing compatibility.

## Consequences
- **Positive:**
  - Guaranteed pristine execution environment for every single run.
  - Native Kubernetes scheduler handles node placement, resource quotas, and pod cleanup.
  - Strong failure reconciliation: if an attempt crashes or times out, Kubernetes terminates the pod deterministically.
- **Negative / Trade-offs:**
  - Pod startup overhead (~500ms - 1500ms container initialization latency).
  - Increased load on kube-apiserver with high Job churn, mitigated by batching, TTL controllers, and dedicated runner nodes.

## Security Impact
- Eliminates cross-submission state pollution.
- Pod is discarded immediately after execution; malware or persistence mechanisms cannot survive beyond the Job lifecycle.

## Operational Impact
- Requires tuned API server rate limits and Job TTL cleanup (`ttlSecondsAfterFinished: 60`).
- Controller tracks pod lifecycles via Kubernetes API informer/watch events.

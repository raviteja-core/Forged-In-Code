# ADR-008: Dedicated Runner Node Group with Taints and Tolerations

**Status:** Accepted  
**Date:** 2026-09-28  
**Deciders:** ForgeRun Engineering Team  

## Context
Untrusted user code runs in Kubernetes pods. Even with container sandboxes (gVisor), running hostile untrusted workloads on the same physical or virtual EC2 worker nodes as critical control-plane services (API, Scheduler, Execution Controller, Ingress, Database proxies) introduces severe blast-radius risks:
- Resource starvation (CPU noisy neighbors, disk I/O thrashing, memory pressure OOM kills).
- Potential container escape or kernel exploit exposing control-plane IAM credentials or network interfaces.
- Accidental placement of sensitive control workloads on untrusted nodes.

## Decision
In production and staging Kubernetes (EKS) clusters, we establish two strictly isolated worker node groups:
1. **Control Node Group (`system`):** Hosts FastAPI, Rust Scheduler, Execution Controller, Result Collector, Prometheus, and Ingress controllers.
2. **Runner Node Group (`runners`):** Dedicated exclusively to executing sandbox Jobs in the `forge-runner` namespace.
   - Nodes are labeled: `forgerun.io/role=runner`
   - Nodes are tainted: `forgerun.io/untrusted=true:NoSchedule`
   - Only sandbox execution Jobs declare the corresponding toleration:
     ```yaml
     tolerations:
       - key: "forgerun.io/untrusted"
         operator: "Exists"
         effect: "NoSchedule"
     ```
   - Node IAM role has zero access to AWS resources (no S3 write, no Secrets Manager, no KMS, no ECR push).

## Alternatives Considered
- **Single Shared Node Group:** Cheaper, but fundamentally violates isolation: a noisy user script could starve the Kubernetes API agent or scheduler controller on the node, causing cascading cluster instability.
- **Dedicated EKS Cluster per tenant or runner fleet:** Extremely high cloud cost and operational overhead with little added security benefit over tainted runner node groups with gVisor.

## Consequences
- **Positive:**
  - Complete compute, network, and IAM isolation between control-plane workloads and untrusted code.
  - No risk of control pods being co-located with untrusted workloads.
  - Node autoscaling (Cluster Autoscaler / Karpenter) scales runners to zero when there is no workload without affecting control services.
- **Negative / Trade-offs:**
  - Slightly higher baseline infrastructure cost for maintaining two node groups in production.

## Security Impact
- Compromise of a runner node does not yield control-plane IAM roles or service credentials.
- Control services cannot be evicted due to untrusted process memory or disk explosions.

## Operational Impact
- Terraform provisions distinct AWS launch templates and managed node groups.
- Manifests must strictly enforce nodeSelector and tolerations on sandbox Jobs.

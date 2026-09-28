# ForgeRun Threat Model & Security Posture

## 1. Threat Profile
All submitted source code is treated as hostile by default. Attack vectors addressed:
- **Host Resource Exhaustion:** CPU spinning, memory bombing, fork bombs, disk space exhaustion.
- **Host System Compromise:** Container breakout, Linux kernel exploit, host path tampering.
- **Network Attacks:** Lateral movement across internal networks, probing cloud metadata services (`169.254.169.254`), outbound botnet traffic.
- **Information Disclosure:** Reading environment variables, stealing database/Kafka credentials, extracting Kubernetes service account tokens, snooping on hidden test case files.
- **Tenant Starvation:** Flooding queues to monopolize runner capacity.

## 2. Multi-Layer Defense in Depth
1. **gVisor User-Space Kernel (`runsc`):** Isolates the Linux host kernel from untrusted system calls.
2. **Kubernetes Restricted Profile:**
   - `runAsNonRoot: true`
   - `allowPrivilegeEscalation: false`
   - Drop all capabilities (`capabilities: drop: ["ALL"]`)
   - `readOnlyRootFilesystem: true`
   - `automountServiceAccountToken: false`
   - `hostNetwork: false`, `hostPID: false`, `hostIPC: false`
3. **Hard Resource Limits:**
   - cgroup CPU and memory limits.
   - pids-limit to neutralize fork bombs.
   - ephemeral-storage limit on `/workspace`.
   - wall-clock timeout and process timeout.
   - stdout/stderr byte limits.
4. **Network Isolation:**
   - Kubernetes `NetworkPolicy` denies all ingress and egress from `forge-runner` pods.
5. **Physical / Node Isolation:**
   - Dedicated EKS runner node group with taint `forgerun.io/untrusted=true:NoSchedule`.
   - Node IAM role has no access permissions to cloud resources.

# ADR-004: gVisor RuntimeClass for Hostile Untrusted Code Execution

**Status:** Accepted  
**Date:** 2026-09-28  
**Deciders:** ForgeRun Engineering Team  

## Context
Standard Linux container runtimes (runc) share the host Linux kernel across all containers. Linux system calls made by a containerized process interact directly with the host kernel. Linux kernel vulnerabilities (privilege escalation, namespace escapes, zero-day syscall bugs) pose an existential risk when running arbitrary, potentially hostile user-submitted code in a multi-tenant platform.

## Decision
ForgeRun uses **gVisor** (`runsc`) as the default Kubernetes `RuntimeClass` for all sandbox runner workloads in production and staging environments where supported.
gVisor intercepts application system calls in user space and implements a substantial portion of the Linux kernel API (the Sentry), completely isolating the host kernel from the untrusted process.
When local environments lack gVisor kernel modules, the platform defaults gracefully to hardened `runc` with strict seccomp/capabilities restrictions and explicitly documents this limitation.

## Alternatives Considered
- **Standard runc with seccomp and AppArmor alone:** Good defense, but any zero-day kernel flaw in unblocked syscalls can lead to full host node takeover.
- **Kata Containers / MicroVMs (Firecracker):** Provides hardware virtualization per pod. Excellent security, but requires nested virtualization or bare-metal instances, significantly increasing cloud infrastructure costs and cold-start latency compared to gVisor.
- **Wasm / WebAssembly Sandbox:** Fast and safe, but severely limits language compatibility (difficult to run standard C++20, Python standard library with C extensions, Java JVM) without heavy non-standard compilation toolchains.

## Consequences
- **Positive:**
  - Dramatically reduced host kernel attack surface: system calls are handled by user-space Go virtual kernel (`Sentry`).
  - Native integration with Kubernetes via `runtimeClassName: gvisor`.
  - Compatibility with standard Linux binaries (ELF, Python, GCC, OpenJDK).
- **Negative / Trade-offs:**
  - Syscall overhead (file I/O, context switching) is higher than native runc.
  - Some low-level kernel features and obscure syscalls are unimplemented or behaviorally distinct.

## Security Impact
- Defends against container breakout vulnerabilities (e.g., Dirty COW, Dirty Pipe, CVE-2024-21626).
- Complemented by non-root execution, dropped capabilities, no host mounts, and network egress denial.

## Operational Impact
- EKS runner nodes must be provisioned with gVisor container runtime (`containerd` configured with `runsc`).
- CI/CD and local environments fall back to native Linux containers with clear logging when gVisor is unavailable.

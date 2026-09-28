# ADR-010: Server-Sent Events (SSE) for Real-Time Execution Status Updates

**Status:** Accepted  
**Date:** 2026-09-28  
**Deciders:** ForgeRun Engineering Team  

## Context
When a user submits code, they need real-time feedback as the submission progresses through states: `QUEUED` -> `SCHEDULED` -> `STARTING` -> `COMPILING` -> `RUNNING` -> `JUDGING` -> `ACCEPTED` / `WRONG_ANSWER`.
Polling `GET /submissions/{id}` introduces either latency or unnecessary database/API load. We need a push-based mechanism from the API to the client browser.

## Decision
For v1, ForgeRun uses **Server-Sent Events (SSE)** via `GET /api/v1/submissions/{id}/events`.
The API server streams events over standard HTTP/1.1 or HTTP/2 chunked transfer encoding as the submission advances.

## Alternatives Considered
- **WebSockets:** Full-duplex communication protocol. While powerful for interactive bidirectional editing or multi-user collaboration, code execution updates are strictly unidirectional (server to client). WebSockets require custom connection management, ping/pong heartbeats, firewall bypass handling, and do not benefit from native HTTP load balancer connection routing or HTTP/2 multiplexing as cleanly as SSE.
- **Short Polling:** Simple, but wastes significant bandwidth, generates unnecessary database queries, and introduces artificial latency between state transitions.
- **Long Polling:** Complex timeouts and connection re-establishment logic without the clean semantics of SSE.

## Consequences
- **Positive:**
  - Built-in browser reconnection and event ID tracking (`EventSource` API).
  - Operates over standard HTTP/HTTPS ports (443) through standard proxies, CDNs, and ALBs with zero special upgrade headers.
  - Lightweight implementation in FastAPI using `StreamingResponse`.
- **Negative / Trade-offs:**
  - Unidirectional only (clients cannot send commands upstream over the same channel; client actions like cancellation use standard `POST /submissions/{id}/cancel`).
  - Limits on concurrent HTTP/1.1 connections per browser domain (mitigated by HTTP/2 multiplexing).

## Security Impact
- Uses standard HTTP Authorization headers and cookie parsing for authentication.
- No special reverse-proxy WebSocket upgrade vulnerabilities.

## Operational Impact
- ALB / reverse proxy idle timeout must be configured to accommodate long executions (or periodic heartbeat comments `: keepalive\n\n` sent).

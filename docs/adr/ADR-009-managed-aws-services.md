# ADR-009: Managed AWS Services (RDS, ElastiCache, EKS) with Terraform IaC

**Status:** Accepted  
**Date:** 2026-09-28  
**Deciders:** ForgeRun Engineering Team  

## Context
Deploying a production-grade distributed system requires durable relational storage, an in-memory cache, an event broker, and a container orchestrator. Teams often debate between self-hosting stateful datastores inside Kubernetes (e.g. running PostgreSQL operators and Redis StatefulSets) versus utilizing managed cloud services.

## Decision
For cloud environments (AWS), ForgeRun provisions:
- **Amazon EKS:** Managed Kubernetes control plane.
- **Amazon RDS PostgreSQL:** Multi-AZ automated backups, storage autoscaling, and managed patching.
- **Amazon ElastiCache for Redis (or Valkey):** Managed caching and cluster replication.
- **Amazon S3:** Durable object storage for raw execution logs and test inputs/artifacts.
- **Amazon ECR:** Private container registry with vulnerability scanning.
All cloud resources are provisioned strictly via modular, declarative **Terraform** configs with no manual console mutations.
For local development, Docker Compose provides lightweight drop-ins (PostgreSQL, Redis, Redpanda) maintaining 100% API and protocol compatibility.

## Alternatives Considered
- **Self-hosting PostgreSQL and Redis on EKS StatefulSets:** Adds significant operational toil (managing storage volumes, snapshot backups, quorum recovery, kernel tuning) without demonstrating better system architecture.
- **AWS Serverless throughout (API Gateway + Lambda + DynamoDB):** Precludes custom Linux sandboxing, gVisor runtime classes, raw TCP Kafka pipelines, and custom low-latency scheduling heaps.

## Consequences
- **Positive:**
  - High availability, automated durability, and enterprise-grade SLA for critical datastores.
  - Keeps development focused on core distributed code execution algorithms rather than datastore maintenance.
  - Parity: Local Docker Compose uses exact same PostgreSQL wire protocol, Redis commands, and Kafka API.
- **Negative / Trade-offs:**
  - AWS cloud cost for managed instances during active deployments.
  - Requires clean Terraform modularization and environment isolation (`dev`, `staging`, `prod`).

## Security Impact
- Relies on AWS IAM, EKS Pod Identity, and VPC security groups rather than static long-lived database credentials.
- Cloud storage encrypted at rest via AWS KMS.

## Operational Impact
- Infrastructure changes validated via `terraform fmt`, `terraform validate`, and automated `terraform plan` on pull requests.

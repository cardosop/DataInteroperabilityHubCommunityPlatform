# Data Residency & Cross-Border Transfer Mechanisms (280.C.6.5)

**Date:** 2026-05-15  
**Owner:** Platform Engineering + Legal  
**Regulatory scope:** GDPR (EU/EEA), UK GDPR, CCPA (California)

## 1. Data Residency Architecture

### 1.1 — Primary Region

| AWS Region | Purpose | Data Categories |
|---|---|---|
| us-east-1 (N. Virginia) | Primary production | All tenant data, operational data, audit logs |
| us-east-1 | Staging | Non-production test data only |

### 1.2 — Per-Tenant Data Boundary

Each tenant's data is logically isolated at the database row level (RLS) and physically stored within the same PostgreSQL cluster in us-east-1. Tenant-level data residency controls:

- **Default:** All tenant data stored in us-east-1
- **EU tenant opt-in:** Tenant flag `data_residency_eu` restricts cross-region replication
- **Future (post-launch):** EU region deployment (eu-west-1) for EU-only tenants requiring strict data residency

### 1.3 — Data Storage Locations

| Data Category | Primary Store | Replication | Backup Location |
|---|---|---|---|
| Tenant metadata (RDS) | us-east-1 | Multi-AZ within us-east-1 | Cross-region snapshot to eu-west-1 (encrypted) |
| Object storage (S3) | us-east-1 | Cross-region replication (opt-in per bucket) | S3 IA / Glacier in us-east-1 |
| Logs (Loki/S3) | us-east-1 | None (single-region) | None (retention-based deletion) |
| Traces (Tempo/S3) | us-east-1 | None | None (14-day TTL) |
| Redis (cache/queue/events) | us-east-1 | Multi-AZ within us-east-1 | None (ephemeral) |
| Container images (ECR) | us-east-1 | None | None (immutable tags retained) |

## 2. Cross-Border Transfer Mechanisms

### 2.1 — Transfer Scenarios

| Scenario | Mechanism | SCC/EU Adequacy |
|---|---|---|
| EU tenant data → US primary region | Standard Contractual Clauses (SCCs) in DPA | Yes (DPA Addendum, `docs/compliance/dpa-addendum.md`) |
| US data → EU backup region (future) | Adequacy decision (EU-US Data Privacy Framework) | Yes (certified organization) |
| Third-party sub-processors | DPA + SCCs per sub-processor | Documented in RoPA |
| Operational telemetry (logs, metrics) | Legitimate interest (GDPR Art. 6(1)(f)) | Aggregated, no PII |

### 2.2 — Encryption in Transit

| Path | Protocol | Key Management |
|---|---|---|
| Client → API | TLS 1.2+ (HTTPS/WSS) | Let's Encrypt certificates (auto-renew 90-day) |
| API → PostgreSQL | TLS 1.2+ (hostssl) | Internal CA (`infrastructure/postgres/certs/`) |
| API → Redis | TLS 1.2+ (stunnel or redis-tls) | AWS Certificate Manager (ElastiCache) |
| API → S3 | TLS 1.2+ (HTTPS) | AWS-managed (S3 endpoint TLS) |
| Inter-service (internal) | Mutual TLS (mTLS) | Internal CA (+ INTERNAL_API_KEY header) |
| Loki → S3 | TLS 1.2+ (HTTPS) | AWS-managed |
| Prometheus → remote_write | TLS 1.2+ | Internal CA |

### 2.3 — Encryption at Rest

| Store | Encryption Type | Key Management |
|---|---|---|
| RDS (PostgreSQL) | AES-256 (AWS-managed) | AWS KMS (`aws/rds` key) |
| S3 buckets | SSE-S3 (AES-256) default; SSE-KMS for compliance buckets | AWS KMS (per-bucket key) |
| ElastiCache (Redis) | Encryption at rest (AWS-managed) | AWS KMS |
| ECR | AES-256 (AWS-managed) | AWS KMS |
| Application-level PII fields | AES-256-GCM (field-level encryption) | AWS KMS (`hub/apps/core/resilience` application key) |

## 3. Transfer Impact Assessments

### 3.1 — High-Risk Transfers (Article 49 Derogations)

The following transfers are documented per GDPR Article 49:

| Transfer | Necessity | Safeguards | TIA Status |
|---|---|---|---|
| EU tenant backup to eu-west-1 | Disaster recovery | Encrypted snapshot, SCCs, no routine access | TIA completed (see DPIA) |
| Stripe payment processing | Contract performance (billing) | Stripe SCCs, PCI-DSS Level 1 | TIA completed |
| Amazon SES (transactional email) | Service operation (notifications, OTP) | AWS DPA + SCCs | TIA completed |
| hCaptcha (DSAR form) | Security (bot prevention) | hCaptcha DPA | TIA completed |

### 3.2 — TIA Review Cadence

- **New sub-processor:** TIA required before integration
- **Annual review:** All TIAs re-validated against current SCCs and adequacy decisions
- **Regulatory change:** Within 30 days of a new adequacy decision or SCC update

## 4. Data Subject Rights & Residency

- **DSAR fulfillment:** Data is collected from us-east-1; response package is encrypted and delivered via presigned S3 URL (24h expiry)
- **Right to erasure:** Soft-delete at application level (30-day grace period); hard-delete cascade runs after grace period
- **Data portability:** Export via ODCS/JSON format; delivered as S3 presigned URL
- **Restriction of processing:** Tenant suspension flag (`Tenant.is_suspended`) blocks all processing except storage

## 5. Audit Evidence

| Control | Evidence |
|---|---|
| Encryption at rest (all stores) | AWS KMS key policies (Terraform: `modules/kms/`) |
| Encryption in transit (all paths) | TLS certificate inventory (Let's Encrypt + internal CA) |
| SCCs for sub-processors | `docs/compliance/dpa-addendum.md` |
| Data residency (tenant flag) | `Tenant.data_residency_eu` BooleanField |
| Cross-border TIA | `docs/compliance/privacy-impact-assessment.md` |
| Retention enforcement | Loki compactor config, RDS backup retention policy |

## 6. Future Roadmap

| Quarter | Milestone |
|---|---|
| Q3 2026 | EU region deployment (eu-west-1) for EU-only tenants |
| Q4 2026 | Customer-managed KMS keys (CMEK) for enterprise tenants |
| Q1 2027 | Multi-region active-active for resilience (us-east-1 + eu-west-1) |

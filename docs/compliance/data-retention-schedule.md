# Data Retention Schedule — Meshant Hub (280.C.6.6)

**Date:** 2026-05-15  
**Owner:** Platform Engineering + Legal  
**Regulatory basis:** GDPR Art. 5(1)(e) (storage limitation), Art. 30 (records of processing)

## 1. Retention Schedule by Data Category

### 1.1 — Operational Logs

| Sub-category | System | Retention | Justification | Deletion Mechanism |
|---|---|---|---|---|
| Application logs (structured) | Loki → S3 | 30 days | Operational debugging, incident response | Loki compactor (`retention_period: 720h`) |
| Access logs (Traefik/ALB) | S3 (Loki) | 30 days | Security monitoring, rate-limit analysis | Loki compactor |
| Audit events (structured) | RDS (`audit_events` table) | 30 days (chain events), 1 year (security events) | GDPR Art. 30 record-keeping, business rules chain audit | `audit_retention_category` field + management command `purge_audit_events` |
| Container stdout/stderr | Kubernetes → Loki | 7 days | Short-term debugging only | Loki per-stream retention override |

### 1.2 — Audit Events (Granular)

| Audit Category | Retention | GDPR Basis | Deletion |
|---|---|---|---|
| `business_rules` | 30 days | Chain validation audit trail | `purge_audit_events --category business_rules --older-than 30d` |
| `security` | 1 year | Security incident investigation | `purge_audit_events --category security --older-than 365d` |
| `access_control` | 1 year | Access review, least-privilege audit | `purge_audit_events --category access_control --older-than 365d` |
| `data_lifecycle` | 90 days | Data processing record | `purge_audit_events --category data_lifecycle --older-than 90d` |
| `compliance` | 1 year | Regulatory compliance evidence | `purge_audit_events --category compliance --older-than 365d` |

### 1.3 — User & Tenant Data

| Data Category | Retention | Justification | Deletion Mechanism |
|---|---|---|---|
| User account (active) | Account lifetime + 30 days | Contractual necessity | Soft-delete → hard-delete after 30-day grace period |
| User account (deleted) | 30 days after deletion request | DSAR grace period, accidental deletion recovery | Permanent deletion on day 31 |
| Tenant configuration | Tenant lifetime + 90 days | Contractual necessity, billing audit | Hard-delete 90 days after tenant termination |
| API keys / credentials | Until rotation or revocation | Security | Immediate on revocation |
| Billing records (Stripe) | 7 years | Financial record-keeping (legal requirement) | Stripe retention policy |
| KYC/KYB documents | 5 years after tenant termination | AML/KYC regulations | S3 lifecycle policy |

### 1.4 — Compliance Records

| Record | Retention | Justification | Storage |
|---|---|---|---|
| Compliance scan results | 1 year | Regulatory audit evidence | RDS `compliance_runs` table |
| DPIA documents | Duration of processing + 3 years | GDPR Art. 35 documentation | S3 `compliance` bucket |
| RoPA (Record of Processing) | Ongoing + 3 years after last processing | GDPR Art. 30 | S3 `compliance` bucket |
| DSAR requests | 3 years after fulfillment | Proof of compliance | RDS `dsar_requests` table |
| Data breach records | 3 years after incident | GDPR Art. 33/34 documentation | RDS + S3 |
| Consent records | Duration of consent + 3 years after withdrawal | GDPR Art. 7 proof of consent | RDS `consent_records` table |

### 1.5 — System & Infrastructure

| Data | Retention | Justification | Deletion |
|---|---|---|---|
| Prometheus metrics | 15 days | Operational monitoring | `--storage.tsdb.retention.time=15d` |
| Tempo traces | 14 days | Debugging, latency analysis | Tempo S3 lifecycle |
| RDS snapshots (automated) | 14 days (prod), 7 days (staging) | Disaster recovery | RDS automated backup retention |
| RDS snapshots (manual) | 90 days | Pre-migration safety, compliance | Manual deletion |
| S3 object versions | 90 days | Accidental deletion recovery | S3 lifecycle (expire non-current versions) |
| ECR images (untagged) | 7 days | Build cache cleanup | ECR lifecycle policy |
| Terraform state (S3) | Indefinite (versioned) | Infrastructure audit trail | S3 versioning (no expiration) |

### 1.6 — PII (Personally Identifiable Information)

| PII Field | Retention | Basis | Deletion |
|---|---|---|---|
| Email address | Account lifetime + 30 days | Contract necessity | Nulled on account deletion |
| Name (display) | Account lifetime + 30 days | Contract necessity | Nulled on account deletion |
| IP address (access logs) | 30 days | Legitimate interest (security) | Loki retention |
| IP address (audit events) | 1 year (security category only) | Security investigation | `purge_audit_events` |
| Payment method (Stripe) | 7 years | Financial regulation | Stripe-managed |
| KYC documents | 5 years post-termination | AML/KYC regulation | S3 lifecycle |
| DSAR subject data | 3 years after fulfillment | GDPR compliance proof | Hard-delete |

## 2. Deletion Procedures

### 2.1 — Automated Deletion

| Mechanism | Schedule | Scope |
|---|---|---|
| Loki compactor | Continuous (every 2h) | Logs older than `retention_period` |
| Prometheus TSDB retention | Continuous | Metrics older than 15 days |
| Tempo S3 lifecycle | Daily | Traces older than 14 days |
| S3 bucket lifecycle policies | Daily | Objects matching lifecycle rules |
| RDS automated backup cleanup | Daily | Snapshots older than retention period |

### 2.2 — Manual / Semi-Automated Deletion

| Command | Purpose | Run Frequency |
|---|---|---|
| `python manage.py purge_audit_events --category business_rules --older-than 30d` | Clean chain audit events | Weekly |
| `python manage.py purge_audit_events --category data_lifecycle --older-than 90d` | Clean data lifecycle events | Weekly |
| `python manage.py hard_delete_expired_accounts` | Purge accounts past grace period | Daily |
| `python manage.py cleanup_staging_test_data` | Remove test data from staging | Weekly (staging only) |

### 2.3 — Deletion Verification

- Each purge command emits an `AUDIT_EVENT_PURGED` audit event with `count` and `category`
- S3 lifecycle rules are monitored via `BucketLifecycleConfiguration` CloudWatch metrics
- Quarterly deletion audit: sample 100 records, verify they are unrecoverable

## 3. Retention Override Requests

### 3.1 — Legal Hold

- A tenant or specific record can be placed on legal hold via `GovernanceService.place_legal_hold()`
- Records under legal hold are exempt from all retention-based deletion
- Legal hold is documented in the DSAR detail view and audit trail
- Release of legal hold requires Legal Counsel approval

### 3.2 — Extended Retention

- Enterprise tenants may request extended retention (e.g., 90-day logs for SOC 2)
- Configured via `TenantConfig.extended_log_retention_days` (default: null = use platform default)
- Extended retention is billed separately (storage cost + 20% operations overhead)

## 4. Retention Schedule Review

| Cadence | Activity |
|---|---|
| Quarterly | Review deletion logs for anomalies |
| Annually | Full retention schedule review with Legal |
| After regulation change | Update retention periods within 30 days |
| After new feature launch | Classify new data categories and add to schedule |

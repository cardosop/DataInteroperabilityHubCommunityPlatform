# Sub-Processor Inventory (Phase 277.A.20)

**Last updated:** 2026-05-12

## Active Sub-Processors

| Vendor | Service | Tenant data processed | Encryption | Data residency |
|--------|---------|----------------------|------------|----------------|
| Stripe | Payments, Connect KYB | Payment methods, transaction amounts, KYC documents | TLS 1.2+, AES-256 at rest | US, EU (Stripe platform regions) |
| AWS | Secrets Manager | API keys, credentials, connection configs | AWS KMS (AES-256) | us-east-1 (configurable per tenant) |
| AWS | KMS | Encryption key material | AWS KMS HSM | us-east-1 |
| AWS | S3 | File uploads, datasets, exports | SSE-S3 / SSE-KMS | us-east-1 (configurable per tenant) |
| AWS | ECR | Container images (no tenant data) | TLS | us-east-1 |
| AWS | EKS | Orchestration (no tenant data) | TLS | us-east-1 |
| AWS | RDS (PostgreSQL) | All application data | TLS + encryption at rest | us-east-1 |
| Sentry | Error capture | Stack traces, error messages (PII redacted via beforeSend) | TLS | US |
| SendGrid/SES | Email delivery | Email addresses, notification content | TLS | US |
| OpenTelemetry | Observability | Span/trace metadata, metric labels (no PII) | TLS | US |
| Apache Fuseki | SPARQL/RDF store | Tenant RDF data | TLS (internal) | us-east-1 |
| Marquez | OpenLineage | Lineage event metadata | TLS (internal) | us-east-1 |
| Snowflake/BigQuery/Databricks/Athena | Warehouse connectivity | Tenant-managed credentials, query results (cached) | TLS 1.2+, per-connector | Per-tenant region |
| ClamAV | Virus scanning | File content (in-memory only) | N/A (in-memory) | us-east-1 |

## SOC2 / ISO27001 Control Mapping

| Control | Stripe | AWS | Sentry | SendGrid |
|---------|--------|-----|--------|----------|
| SOC2 Type II | ✅ | ✅ | ✅ | ✅ |
| ISO 27001 | ✅ | ✅ | ❌ | ✅ |
| PCI DSS Level 1 | ✅ | ✅ | N/A | N/A |
| GDPR DPA | ✅ | ✅ | ✅ | ✅ |
| Encryption in transit | TLS 1.2+ | TLS 1.2+ | TLS | TLS |
| Encryption at rest | AES-256 | AES-256 (KMS) | AES-256 | AES-256 |
| Access logs | ✅ | ✅ (CloudTrail) | ✅ | ✅ |
| Data residency | US, EU | Per-region (tenant-configurable) | US | US |

## Sub-Processor Change Notification

Tenants will be notified of new sub-processors or material changes via:
1. In-app notification (30 days before change)
2. Email to tenant admin (30 days before change)
3. CHANGELOG entry in sub-processor registry

Opt-out: Tenants may object to new sub-processors within 30 days.
Objection → tenant may terminate agreement without penalty per DPA §7.

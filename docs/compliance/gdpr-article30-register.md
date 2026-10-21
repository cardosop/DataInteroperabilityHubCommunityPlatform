# GDPR Article 30 — Records of Processing Activities (281.B.4.4)

**Date:** 2026-05-15  
**Controller:** Meshant (product brand)  
**DPO:** See `docs/compliance/privacy-impact-assessment.md`  
**Supervisory Authority:** To be filed per EU member state where controller is established

## 1. Controller Processing Activities

### 1.1 — User Account Management

| Field | Detail |
|---|---|
| Purpose | Provision and management of user accounts for platform access |
| Legal basis | Contractual necessity (GDPR Art. 6(1)(b)) |
| Data categories | Email, name (display), role, tenant affiliation, authentication identifiers |
| Data subjects | Tenant administrators, users |
| Recipients | None (internal processing only) |
| Retention | Account lifetime + 30 days grace period |
| Transfers | None outside EEA (us-east-1 with SCCs) |

### 1.2 — Billing & Payments

| Field | Detail |
|---|---|
| Purpose | Subscription management and payment processing |
| Legal basis | Contractual necessity + legal obligation (financial records) |
| Data categories | Billing contact email, payment method (Stripe tokenized), billing address, VAT ID |
| Data subjects | Tenant billing contacts |
| Recipients | Stripe, Inc. (payment processor, DPA signed) |
| Retention | 7 years (financial record-keeping requirement) |
| Transfers | Stripe (US, SCCs in place) |

### 1.3 — Marketplace Listings & Orders

| Field | Detail |
|---|---|
| Purpose | Marketplace catalogue, order processing, entitlement management |
| Legal basis | Contractual necessity |
| Data categories | Listing title, description, pricing, seller identity, buyer identity, order history |
| Data subjects | Marketplace sellers and buyers |
| Recipients | None |
| Retention | Listing: account lifetime + 90 days; Order: 7 years |
| Transfers | None |

### 1.4 — Compliance & Audit

| Field | Detail |
|---|---|
| Purpose | Automated compliance scanning, audit trail, regulatory evidence |
| Legal basis | Legal obligation (GDPR Art. 30 record-keeping) + legitimate interest (security) |
| Data categories | Tenant configuration, compliance scan results, audit events (with PII redaction where possible) |
| Data subjects | Tenant administrators, users (audit trail) |
| Recipients | External auditors (under NDA), supervisory authorities (on request) |
| Retention | Category-based: 30d (business rules), 1y (security, compliance, access control), 90d (data lifecycle) |
| Transfers | None |

### 1.5 — DSAR Processing

| Field | Detail |
|---|---|
| Purpose | Fulfilment of data subject access requests per GDPR Chapter III |
| Legal basis | Legal obligation (GDPR Art. 15-22) |
| Data categories | Subject email, request type, applicable regimes, ID verification, response data |
| Data subjects | Any natural person submitting a DSAR |
| Recipients | Supervisory authority (if escalated) |
| Retention | 3 years after fulfilment |
| Transfers | None |

### 1.6 — Operational Telemetry

| Field | Detail |
|---|---|
| Purpose | Platform monitoring, performance optimization, security incident detection |
| Legal basis | Legitimate interest (GDPR Art. 6(1)(f)) — necessary for service operation |
| Data categories | Request metadata (IP, user agent, endpoint, latency), error logs (PII redacted via structlog), access logs (Authorization/Cookie headers dropped) |
| Data subjects | All platform users (aggregated, no individual profiling) |
| Recipients | AWS (infrastructure provider, DPA signed) |
| Retention | Logs: 30 days (Loki), Metrics: 15 days (Prometheus), Traces: 14 days (Tempo) |
| Transfers | AWS us-east-1 (SCCs in AWS DPA) |

## 2. Processor Activities

### 2.1 — Infrastructure (AWS)

| Field | Detail |
|---|---|
| Processor | Amazon Web Services, Inc. |
| Processing | Hosting, storage, networking, compute |
| DPA | AWS Data Processing Addendum (online, incorporated by reference) |
| SCCs | EU SCCs included in AWS DPA |
| Location | us-east-1 (N. Virginia) |

### 2.2 — Payment Processing (Stripe)

| Field | Detail |
|---|---|
| Processor | Stripe, Inc. |
| Processing | Payment tokenization, subscription management |
| DPA | Stripe Data Processing Agreement (signed) |
| SCCs | Stripe EU SCCs |
| Location | US (global infrastructure) |

### 2.3 — Email Delivery (Amazon SES)

| Field | Detail |
|---|---|
| Processor | Amazon Web Services (SES) |
| Processing | Transactional email (DSAR OTP, notifications, verify email) |
| DPA | Covered under AWS DPA |
| SCCs | EU SCCs in AWS DPA |
| Location | us-east-1 |

### 2.4 — Bot Detection (hCaptcha)

| Field | Detail |
|---|---|
| Processor | Intuition Machines, Inc. (hCaptcha) |
| Processing | Bot detection on public DSAR form |
| DPA | hCaptcha Data Processing Agreement |
| SCCs | hCaptcha EU SCCs |
| Location | Global (SCCs apply) |

## 3. Filing Status

| Requirement | Status | Evidence |
|---|---|---|
| Article 30(1) — Controller records | ✅ Complete | This document |
| Article 30(2) — Processor records | ✅ Complete | §2 of this document |
| Article 30(3) — Written format | ✅ Complete | Markdown, stored in Git (immutable history) |
| Article 30(4) — Available to SA on request | ✅ Ready | Export as PDF via CI automation |
| DPO designated | ✅ | See PIA |
| Filed with supervisory authority | ⚠️ Pending | File after DPO confirms completeness |

## 4. Maintenance

- **Owner:** DPO + Platform Engineering
- **Review cadence:** Quarterly or within 30 days of any processing change
- **Update triggers:** New subprocessor, new processing purpose, retention change, legal basis change

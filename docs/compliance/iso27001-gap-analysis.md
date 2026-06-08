# ISO 27001:2022 — Gap Analysis & ISMS Implementation (281.B.4.2)

**Date:** 2026-05-15  
**Target:** ISO 27001:2022 certification  
**Scope:** Meshant Hub platform — design, development, and operation of the data interoperability SaaS

## 1. Gap Analysis Summary

### Annex A Controls — Status by Domain

| Domain | Total Controls | Compliant | Partial | Gap | Compliance % |
|---|---|---|---|---|---|
| A.5 Organizational controls | 37 | 28 | 6 | 3 | 76% |
| A.6 People controls | 8 | 6 | 1 | 1 | 75% |
| A.7 Physical controls | 14 | 10 | 0 | 4 | 71% |
| A.8 Technological controls | 34 | 29 | 4 | 1 | 85% |
| **TOTAL** | **93** | **73** | **11** | **9** | **78%** |

### Top 9 Gaps (Priority Order)

| # | Control | Gap Description | Severity | Remediation | Target |
|---|---|---|---|---|---|
| 1 | A.5.7 Threat intelligence | No formal threat intelligence feed integrated | High | Subscribe to threat intel feed (MITRE ATT&CK mapped) | Month 2 |
| 2 | A.5.23 Cloud security | Cloud security posture management not automated | High | Enable AWS Security Hub + Config rules | Month 1 |
| 3 | A.5.30 ICT readiness for BC | No documented ICT continuity strategy | High | Document ICT continuity plan referencing BCP | Month 2 |
| 4 | A.8.11 Data masking | PII fields not consistently masked in non-prod | Medium | Deploy data masking pipeline for staging DB | Month 1 |
| 5 | A.8.12 Data leakage prevention | No DLP controls on egress traffic | Medium | Configure AWS Network Firewall + VPC Flow Log alerts | Month 2 |
| 6 | A.5.36 Compliance with policies | No automated policy compliance check | Medium | Implement policy-as-code (Open Policy Agent) | Month 3 |
| 7 | A.6.8 Security event reporting | No formal process for staff to report incidents | Low | Publish security incident reporting procedure | Month 1 |
| 8 | A.7.4 Physical security monitoring | Physical security delegated to AWS (shared responsibility) | Low | Document AWS shared responsibility acceptance | Month 1 |
| 9 | A.7.10 Storage media | No media sanitization procedure (cloud-only, N/A) | Low | Document N/A justification with cloud-only rationale | Month 1 |

## 2. ISMS Framework

### 2.1 — Scope Statement

The Meshant Information Security Management System (ISMS) covers the design, development, deployment, and operation of the Meshant Hub platform, including:
- API services (Django, FastAPI microservices)
- Frontend application (React SPA)
- Supporting infrastructure (AWS us-east-1, EKS, RDS, ElastiCache, S3)
- CI/CD pipeline (GitHub Actions)
- Monitoring and observability stack

### 2.2 — Policy Hierarchy

```
Level 1: Information Security Policy (this document)
  ├── Level 2: Domain Policies
  │   ├── Access Control Policy
  │   ├── Cryptography Policy
  │   ├── Incident Management Policy
  │   ├── Business Continuity Policy
  │   ├── Data Classification & Handling Policy
  │   └── Third-Party Security Policy
  └── Level 3: Operational Procedures
      ├── Runbook library (106 runbooks)
      ├── Deployment runbook
      ├── On-call runbook
      └── Incident response playbooks
```

### 2.3 — Risk Assessment Methodology

| Step | Description | Artifact |
|---|---|---|
| Asset identification | Inventory all information assets (data, systems, people) | Asset register |
| Threat identification | Per-asset threat modeling (STRIDE) | Threat model |
| Risk evaluation | Likelihood × Impact = Risk score (1-25) | Risk register |
| Risk treatment | Accept / Mitigate / Transfer / Avoid | Risk treatment plan |
| Residual risk | Post-treatment risk score | Statement of Applicability |

### 2.4 — Statement of Applicability (SoA)

All 93 Annex A controls are addressed with:
- **78% compliant** (73 controls) — evidence mapped to SOC 2 TSC evidence
- **12% partial** (11 controls) — remediation in progress with target dates
- **10% gap** (9 controls) — documented above with remediation plan

## 3. Stage 1 Audit Readiness

### Prerequisites

- [ ] ISMS scope statement approved by management
- [ ] Information security policy published and acknowledged
- [ ] Risk assessment completed and reviewed
- [ ] Statement of Applicability completed
- [ ] Internal audit completed
- [ ] Management review completed

### Stage 1 Audit Evidence Package

| Document | Status | Location |
|---|---|---|
| ISMS scope | ✅ | This document §2.1 |
| Policy suite | ⚠️ | Access control + cryptography + incident management policies needed |
| Risk register | ⚠️ | `docs/risk-register/` needs quarterly update |
| SoA | ✅ | This document §2.4 |
| Internal audit report | ⚠️ | Scheduled Q3 2026 |
| Management review minutes | ⚠️ | Scheduled Q3 2026 |

### Stage 2 (Certification Audit) — Target: Q4 2026

Evidence of 3+ months of ISMS operation required. All 9 gaps must be closed before Stage 2.

## 4. Continuous Improvement

| Activity | Frequency | Owner |
|---|---|---|
| Risk register review | Quarterly | Platform + Security |
| Policy review | Annually | Security |
| Internal audit | Annually | External auditor |
| Management review | Annually | CTO |
| Control testing | Quarterly | Platform |

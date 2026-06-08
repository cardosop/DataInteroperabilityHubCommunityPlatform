# DPA Subprocessor Inventory & Agreement Tracking (281.B.4.5)

**Date:** 2026-05-15  
**Owner:** Platform Engineering + Legal  
**Audit requirement:** GDPR Art. 28(2) — controller shall use only processors providing sufficient guarantees

## 1. Subprocessor Inventory

| # | Subprocessor | Service | Data Processed | DPA Signed | SCCs | Location | Review Date |
|---|---|---|---|---|---|---|---|
| 1 | Amazon Web Services (AWS) | Infrastructure (compute, storage, networking) | All platform data | ✅ (AWS DPA online) | ✅ EU SCCs | us-east-1 | 2026-05-15 |
| 2 | Stripe, Inc. | Payment processing | Billing contact, payment method token | ✅ (Stripe DPA) | ✅ EU SCCs | US (global) | 2026-05-15 |
| 3 | Amazon SES (AWS) | Transactional email | Email address, notification content | ✅ (AWS DPA) | ✅ EU SCCs | us-east-1 | 2026-05-15 |
| 4 | Intuition Machines (hCaptcha) | Bot detection | IP address, browser metadata | ✅ (hCaptcha DPA) | ✅ EU SCCs | Global | 2026-05-15 |
| 5 | GitHub, Inc. | Source code, CI/CD | Code, commit metadata (no PII) | ✅ (GitHub DPA) | ✅ EU SCCs | US | 2026-05-15 |
| 6 | Let's Encrypt (ISRG) | TLS certificates | Domain names (public) | N/A (no PII) | N/A | US | 2026-05-15 |
| 7 | Grafana Labs | Observability (optional, self-hosted) | Metrics, logs (PII redacted) | N/A (self-hosted) | N/A | us-east-1 | 2026-05-15 |

## 2. DPA Signing Status

| Status | Count | Subprocessors |
|---|---|---|
| ✅ Signed + SCCs | 4 | AWS, Stripe, hCaptcha, GitHub |
| ✅ Self-hosted (no DPA needed) | 2 | Grafana, Let's Encrypt |
| ⚠️ Pending | 0 | — |

## 3. DPA Review Schedule

| Trigger | Action |
|---|---|
| New subprocessor | DPA must be signed BEFORE processing begins |
| DPA renewal | Annual review of existing DPAs for currency |
| Regulatory change | Within 30 days of new SCCs or adequacy decision |
| Subprocessor security incident | Immediate review of DPA breach notification terms |

## 4. Template DPA Terms

Every subprocessor DPA must cover:

- [ ] Subject matter and duration of processing
- [ ] Nature and purpose of processing
- [ ] Type of personal data and categories of data subjects
- [ ] Processor's obligation to process only on documented instructions
- [ ] Confidentiality commitment from processor personnel
- [ ] Technical and organizational security measures (TOMs)
- [ ] Sub-subsidiary processor restrictions (no sub-subs without controller consent)
- [ ] Data subject rights assistance (processor shall assist controller)
- [ ] Breach notification (processor shall notify controller without undue delay)
- [ ] Deletion or return of data at end of processing
- [ ] Audit rights (controller may audit processor's compliance)
- [ ] EU Standard Contractual Clauses (SCCs) or equivalent adequacy mechanism

## 5. Subprocessor Onboarding Checklist

- [ ] Security assessment completed (SOC 2 report or ISO 27001 cert reviewed)
- [ ] DPA reviewed by Legal
- [ ] SCCs verified as current (post-Schrems II)
- [ ] Data flow documented (what data, where stored, who has access)
- [ ] TIA completed if data crosses EEA border
- [ ] Added to Article 30 register
- [ ] Added to subprocessor disclosure page (`docs/compliance/sub-processors.md`)
- [ ] Tenant notification sent (30 days before new subprocessor begins processing)

## 6. Cross-Reference

- **Article 30 register:** `docs/compliance/gdpr-article30-register.md`
- **Data retention schedule:** `docs/compliance/data-retention-schedule.md`
- **Privacy impact assessment:** `docs/compliance/privacy-impact-assessment.md`
- **Subprocessor disclosure:** `docs/compliance/sub-processors.md`

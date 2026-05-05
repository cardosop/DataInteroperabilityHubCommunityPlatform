# Privacy Impact Assessment (PIA)

**Phase**: 250.5.F.3 (closes G-4)
**Status**: DRAFT — DPO sign-off required before P5 GA per G-4
**Last reviewed**: 2026-05-04
**Next review**: every 12 months OR before any cross-border data flow change

This Privacy Impact Assessment covers the Meshant Data
Interoperability Hub's processing of personal data per **GDPR
Article 35** (and the equivalent obligations under LGPD Article
38, UK GDPR DPIA, CCPA-CPRA risk assessments). The PIA must be
signed by the Data Protection Officer (DPO) and reviewed by
external counsel **before P5 General Availability** per the G-4
gap-closure plan.

## 1. Processing overview

| Question | Answer |
| --- | --- |
| Controller | The customer tenant ("Producer Tenant" or "Consumer Tenant") |
| Processor | Meshant operating the Hub on behalf of the controller |
| Sub-processor | AWS (compute + S3); Stripe (billing only); SendGrid (transactional email) |
| Purpose | Data product creation, governance, marketplace, federated import/export |
| Legal basis | Article 6(1)(b) contract performance; 6(1)(f) legitimate interest (audit / fraud prevention); 6(1)(a) consent (federated cross-region transfer) |
| Data subjects | Tenant employees (users of the platform), customers of producer tenants whose data is uploaded as datasets, federated-import counterparties |
| Categories of data | Account metadata (name / email), audit logs (IP / user-agent), uploaded datasets (varies by tenant — may include PII per the contract), derived metadata (DQ + compliance scores) |

## 2. Data flows in scope

1. **Upload path**: tenant user → POST /api/v1/files/init → S3
   pre-signed URL → tenant uploads bytes → POST /complete → ClamAV
   scan → schema inference → DQ run → compliance scan → asset
   creation. Personal data potentially in the file body; metadata
   (filename, size) in audit log.

2. **Federated import path**: source tenant → marketplace
   listing → consumer tenant invokes
   `DiscoveryService.create_federated_asset_with_contracts` →
   metadata + URL stored in `ExternalResourceReference`. Personal
   data potentially in the metadata blob; the consumer-side
   metadata is classified per
   `Tenant.federated_import_classification_default` (Phase
   250.5.F.1; default `INTERNAL`).

3. **Marketplace listing path**: producer tenant publishes a
   listing → ODPS document references the contract + asset →
   consumer tenants discover and request access. The listing
   metadata is published; the underlying dataset stays in the
   producer's S3 bucket gated by entitlement.

4. **Audit / observability**: every API call emits an `AuditEvent`
   with `actor_user`, `tenant`, `resource_type`, `resource_id`,
   `details_json`. Personal data may appear in `details_json`
   under keys like `email`, `display_name`, `ip_address`,
   `user_agent`. Phase 250.5.F.5 extends the GDPR right-to-erasure
   scrub to every common PII key.

## 3. Risk register

| # | Risk | Likelihood | Impact | Mitigation |
| --- | --- | --- | --- | --- |
| 1 | Cross-tenant data leak via IDOR on federated assets | Low | High | Per-resource SSRF + IDOR test sweep (Phase 250.5.B + 250.5.C); cross-tenant `GET` returns 404 for non-VERIFIED listings (`marketplace.views`); ABAC tenant scoping at every queryset (`get_request_tenant_id`). |
| 2 | Federated metadata classified PUBLIC by default leaks unclassified PII | Mitigated | High | Phase 250.5.F.1 default INTERNAL (NOT PUBLIC); tenants must explicitly set lower-sensitivity defaults. |
| 3 | Right-to-erasure does not cascade through assets | Mitigated | High | Phase 250.5.F.5 cascades through user-owned assets (anonymise, NOT hard-delete) + scrubs extended PII key list in audit `details_json`. |
| 4 | Cross-region transfer without explicit consent | Mitigated | High | I2-3 (see asset-creation/spec.md): cross-region federated import refused unless `cross_region_consent=True`; refusal emits `FEDERATED_IMPORT_CROSS_REGION_BLOCKED` audit event. |
| 5 | Source-tenant deletion orphans consumer-side federated copies | Mitigated | Medium | D250.16: source-tenant soft-delete cascades `source_tenant_deleted_at`; 90-day grace window before scheduled hard-delete. |
| 6 | Consumer cannot delete their federated copy without affecting source | Mitigated | Low | Phase 250.5.F.2: independent `deleted_at` field on `ExternalResourceReference`; consumer-side delete preserves source-side row. |
| 7 | DPA addendum not executed before customer onboarding | Pending | High | Phase 250.5.F.4: DPO + Legal sign-off required before P5 GA; tracked as P5 launch dependency in [docs/compliance/dpa-addendum.md](./dpa-addendum.md). |
| 8 | Audit-event PII retained beyond GDPR retention | Mitigated | Medium | Phase 234 (audit retention) + Phase 250.5.F.5 PII scrub on erasure; per-event-type retention policies. |

## 4. Outstanding mitigations (P5-blocking)

* **DPO sign-off** on this PIA — required before P5 GA per G-4.
* **External counsel review** of the DPA addendum and the
  cross-border transfer clauses (relevant for EU/UK data flowing
  into US-based AWS regions).
* **Privacy notice** at the tenant onboarding flow naming the
  sub-processors (AWS / Stripe / SendGrid) explicitly.
* **DSAR procedure runbook** at
  `docs/runbooks/data-subject-access-requests.md` (planned;
  references `ErasureService` + `ExportService`).

## 5. DPO sign-off section (to be filled at GA-1 week)

| Field | Value |
| --- | --- |
| DPO name | _to be filled_ |
| DPO signature | _to be filled_ |
| Date | _to be filled_ |
| Counsel name | _to be filled_ |
| Counsel signature | _to be filled_ |
| Date | _to be filled_ |
| Effective date | _to be filled_ |

## 6. Re-assessment triggers

This PIA MUST be re-assessed when ANY of the following occur:

* New sub-processor added or removed.
* New data category collected (e.g. biometric, health data).
* New cross-border transfer flow introduced.
* New federated marketplace integration.
* New AI / ML inference path on personal data.
* Material change to data retention policy.
* Annual review (12 months from last sign-off date).

## 7. References

* GDPR Article 35 — Data Protection Impact Assessment.
* LGPD Article 38 — Relatório de Impacto à Proteção de Dados Pessoais.
* UK GDPR Article 35 + ICO DPIA guidance.
* CCPA-CPRA §1798.185(a)(15) Risk Assessments.
* ADR-AST-002 (federated import) — internal cross-reference.
* D250.16 (source-tenant tombstone) — internal cross-reference.
* Phase 250.5.F.5 (right-to-erasure cascade) — internal cross-reference.

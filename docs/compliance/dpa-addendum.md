# Data Processing Addendum (DPA) — Addendum

**Phase**: 250.5.F.4 (closes G-5)
**Status**: DRAFT — DPO + Legal sign-off required before P5 GA
**Last reviewed**: 2026-05-04
**Effective date**: _to be set on counter-signature_

This DPA Addendum is supplemental to the master Customer
Agreement between Meshant ("Processor") and the customer tenant
("Controller"). It governs the processing of personal data
under GDPR Article 28 and the equivalent obligations under LGPD
Article 39, UK GDPR, CCPA-CPRA, and other applicable data
protection laws.

The Addendum **MUST be executed before P5 General Availability**
per the G-5 gap-closure plan. Tracked as a P5 launch dependency
in `openspec/changes/preprod01/tasks.md` Phase 250.5.F.4.

## 1. Definitions

* **Processor** — Meshant.
* **Controller** — the customer tenant.
* **Sub-processor** — any third party engaged by the Processor
  to assist in performing the services. Current sub-processors:
  AWS (compute, S3 storage), Stripe (billing), SendGrid
  (transactional email).
* **Personal Data** — as defined in GDPR Article 4(1).
* **Processing** — as defined in GDPR Article 4(2).
* **Data Subject** — the natural person to whom the Personal
  Data relates.
* **Federated Asset** — an asset imported from another tenant's
  marketplace, classified per
  `Tenant.federated_import_classification_default` (Phase
  250.5.F.1).

## 2. Scope of processing

The Processor processes Personal Data on behalf of the
Controller for the following purposes:

* Hosting and serving the Controller's data products.
* Running governance, DQ, and compliance checks on uploaded
  datasets.
* Providing marketplace discovery and federated import.
* Generating audit logs for the Controller's compliance needs.
* Sending transactional notifications (account, billing, alerts).

The categories of Data Subjects, Personal Data, and processing
activities are enumerated in
[docs/compliance/privacy-impact-assessment.md](./privacy-impact-assessment.md)
(the PIA).

## 3. Sub-processors

| Sub-processor | Service | Region | DPA in place |
| --- | --- | --- | --- |
| AWS | Compute (EKS), Object Storage (S3), DNS (Route 53) | us-east-1 / eu-west-1 | Yes — AWS DPA |
| Stripe | Payment processing (billing only) | US | Yes — Stripe DPA |
| SendGrid | Transactional email (verification, password reset, alerts) | US | Yes — SendGrid DPA |

The Processor SHALL provide the Controller with at least 30
days' notice before adding or replacing any sub-processor.

## 4. Controller obligations

The Controller represents that it has the necessary legal
basis to upload Personal Data to the Hub. The Controller is
responsible for classifying its uploaded datasets per the
governance taxonomy (`ClassificationCategory`).

For federated import, the Controller acknowledges that the
default classification is `INTERNAL` per
`Tenant.federated_import_classification_default` (Phase
250.5.F.1) — the Controller MUST flip to a stricter
classification (`PII`, `RESTRICTED`, `CONFIDENTIAL`) before
importing from marketplaces known to carry sensitive payloads.

## 5. Processor obligations

The Processor SHALL:

* Process Personal Data only on the Controller's documented
  instructions (the Customer Agreement + tenant configuration).
* Ensure all personnel with access to Personal Data are bound
  by confidentiality obligations.
* Implement appropriate technical and organisational measures
  per GDPR Article 32 (encryption at rest + in transit, access
  controls, audit logging, SSRF protections per Phase 250.5.B,
  IDOR test coverage per Phase 250.5.C).
* Assist the Controller in responding to Data Subject requests
  via the right-to-erasure pipeline (`ErasureService` + Phase
  250.5.F.5 asset cascade) and the data portability pipeline
  (`ExportService`).
* Notify the Controller of any Personal Data Breach without
  undue delay (target: ≤72 hours, mirroring the GDPR Article 33
  notification window).
* Make available all information necessary to demonstrate
  compliance (audit logs, security reports, the PIA, this DPA).

## 6. Data Subject rights

The Processor SHALL assist the Controller in fulfilling Data
Subject rights:

| Right | Implementation |
| --- | --- |
| Access (Art. 15) | `ExportService.create_portability_request` — exports tenant data as JSON archive. |
| Rectification (Art. 16) | Standard PATCH endpoints; tenant-administered correction. |
| Erasure (Art. 17) | `ErasureService.execute_erasure` — anonymises user profile + cascades through user-owned assets (Phase 250.5.F.5) + scrubs extended PII key list in audit `details_json`. |
| Restriction (Art. 18) | Tenant-administered — Tenant.status flag. |
| Portability (Art. 20) | `ExportService.create_portability_request` — same surface as Access. |
| Objection (Art. 21) | Tenant-administered. |

## 7. Cross-border transfers

The Processor MAY transfer Personal Data outside the
Controller's residency region (`Tenant.data_residency_region`)
ONLY when:

1. The Controller has explicitly opted in via
   `cross_region_consent=True` per the federated-import I2-3
   spec, AND
2. The transfer is to a sub-processor in a country deemed
   adequate by the Controller's regulator (e.g. EU adequacy
   decision, UK adequacy regulations, LGPD adequacy resolution),
   OR
3. The Processor and the sub-processor have executed Standard
   Contractual Clauses (SCCs) per the EDPB framework.

A cross-region transfer without explicit consent is REFUSED at
the federated-import gate per the
[asset-creation/spec.md "Cross-Region Federated-Import Consent
(I2-3)" requirement](../../openspec/changes/preprod01/specs/asset-creation/spec.md).
The refusal emits `FEDERATED_IMPORT_CROSS_REGION_BLOCKED` and
the parent `FEDERATED_IMPORT_REJECTED` audit events.

## 8. Termination

Upon termination of the Customer Agreement:

* The Processor SHALL return or delete all Personal Data within
  90 days, at the Controller's option.
* The Processor MAY retain Personal Data after termination
  ONLY where required by applicable law (audit-log retention,
  tax records). Such retention is documented in the audit log
  retention policy + the per-event-type retention registry
  (Phase 234.5).

## 9. Sign-off section (to be filled at counter-signature)

| Field | Value |
| --- | --- |
| Controller (Customer) name | _to be filled_ |
| Controller representative | _to be filled_ |
| Controller signature | _to be filled_ |
| Date | _to be filled_ |
| Processor (Meshant) representative | _to be filled_ |
| Processor signature | _to be filled_ |
| Date | _to be filled_ |
| Effective date | _to be filled_ |
| DPO concur (Meshant) | _to be filled_ |
| Legal counsel concur (Meshant) | _to be filled_ |

## 10. Re-execution triggers

This Addendum MUST be re-executed when any of the following
occur:

* New sub-processor added.
* Material change to the technical security measures (e.g.
  encryption algorithm change, new region added).
* Change to the Personal Data Breach notification timeline.
* Change to the Data Subject rights process.
* Change to the cross-border transfer mechanism.

## 11. References

* GDPR Article 28 — Processor obligations.
* GDPR Article 32 — Security of processing.
* GDPR Article 33 — Breach notification.
* GDPR Article 35 — DPIA (cross-references the PIA).
* LGPD Article 39 — Operating Agent obligations.
* CCPA-CPRA §1798.140(c) — Service Provider definition.
* [docs/compliance/privacy-impact-assessment.md](./privacy-impact-assessment.md) — companion PIA.
* [openspec/changes/preprod01/specs/asset-creation/spec.md](../../openspec/changes/preprod01/specs/asset-creation/spec.md) — I2-3 cross-region consent requirement.
* Phase 250.5.F.5 (right-to-erasure cascade) — implementation reference.

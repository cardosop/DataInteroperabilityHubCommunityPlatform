# Phase 232 regulator-audit tabletop exercise

**Phase:** 232.DoD.7
**Cadence:** quarterly + before any subsystem flag flips ON in production
**Owners:** Auth/Compliance Engineering Lead + DPO + Legal Counsel + SRE on-call
**Last reviewed:** 2026-05-05

## Purpose

Phase 232.DoD.7 mandates: *"Tabletop exercise (regulator audit
simulation) executed; timing + completeness captured as DoD evidence."*
This playbook is the **authoritative procedure**: it describes the
scenarios that simulate a real GDPR / PIPL / LGPD regulator audit, the
timing budget per scenario, the artefacts the team must produce within
the budget, and the ledger ([docs/audit-reports/232-tabletop-ledger.md](../audit-reports/232-tabletop-ledger.md))
that records each run.

A clean run of this exercise — with sign-offs from DPO + Legal Counsel +
EM — closes 232.DoD.7. It does NOT replace the pen-test gate (DoD.6) or
the privacy-counsel reviews (D232.14): those are independent.

## Scope

The exercise covers all seven Phase 232 subsystems plus the
cross-cutting platform DPIA:

1. **Consent management** (232.1) — purposes, records, HMAC proofs,
   3-key rotation.
2. **DSAR workflow** (232.2) — public ingress, statutory clock,
   IDV gates, response packaging, presigned downloads.
3. **Breach notification** (232.3) — incident → notification, statutory
   clocks per regulator, S3 Object Lock proofs.
4. **RoPA generator** (232.4) — multi-format export, per-regulation
   templates, S3 lifecycle.
5. **DPIA tooling** (232.5) — high-risk auto-trigger, residual-risk
   review queue, 12-month review cron.
6. **Processor agreements** (232.6) — DPA / BAA / SCC / BCR registry,
   expiry alerts, sub-processor change notification.
7. **Retention auto-enforcer** (232.7) — regulation-keyed retention,
   legal-hold suspension, tombstone + 90-day grace.
8. **Platform recursive DPIA** (232.0.12 / 232.8.1) — the platform
   owner's own privacy posture.

## Roles for the exercise

| Role | Real-world stand-in | What they do |
|---|---|---|
| Regulator | Legal Counsel + DPO | Issues mock data subject access / audit requests on a clock; grades responses against statutory deadlines and completeness. |
| Tenant Admin | Compliance Engineering Lead | Operates the tenant-facing UI: triages DSARs, files breach incidents, regenerates RoPA. |
| DPO (subject) | Compliance Engineering / Privacy | Files DPIA reviews, approves/rejects, validates consent records. |
| SRE on-call | SRE rotation | Operates kill switches, exercises the rollback runbooks if a scenario triggers them. |
| Observer | EM + Auth/Compliance Engineer | Records timing + evidence + outcome to the ledger. |

## Scenarios + timing budget

Each scenario is a real action against the **staging** environment with
a fresh test tenant + test subject (provisioned by the seeder before
the exercise). The clock starts when the regulator sends the request;
the clock stops when the deliverable is produced AND the observer logs
the outcome.

> ⚠️ Run against staging with **`compliance_*_enabled=True`** on the
> test tenant only. Do not flip flags on real-customer tenants for the
> exercise.

### S1 — DSAR ACCESS within statutory deadline (60 min budget)

* Regulator submits a DSAR ACCESS request via the public form
  (`/legal/dsar`) with hCaptcha + EMAIL_OTP IDV.
* Tenant Admin verifies, materialises the response ZIP, sends the
  presigned download link.
* DPO downloads the ZIP, validates `MANIFEST.json`, asserts every
  PII-holding model from the registry ([hub/apps/core/pii_registry.py](../../hub/apps/core/pii_registry.py))
  is represented.
* Acceptance: regulator receives the ZIP within 60 min and the
  manifest is complete.

### S2 — DSAR ERASURE with active legal hold (45 min budget)

* Regulator submits an ERASURE request for a subject with a
  `legal_hold=True` retention policy.
* Tenant Admin attempts erasure; system MUST return a structured
  refusal with the legal-hold rationale (no data deleted).
* DPO records the outcome; regulator confirms the refusal is
  defensible.
* Acceptance: erasure refused with structured `LEGAL_HOLD_ACTIVE`
  signal; no rows touched (verified by DB snapshot diff).

### S3 — Breach notification within 72 h (90 min budget)

* SRE on-call files a synthetic breach via the emergency form
  (TENANT_ADMIN/DPO/SECURITY_ADMIN).
* The breach engages **two** regulators (e.g. GDPR + PIPL_CN); the
  system must auto-create one `BreachNotification` per regulator with
  the **soonest** statutory deadline.
* DPO drafts and sends the notification; the system records SHA-256
  proof of delivery into the Object-Lock bucket.
* Acceptance: both notifications drafted within 90 min; statutory
  countdown matches the matrix ([hub/apps/regulation_policies/](../../hub/apps/regulation_policies/));
  proof persisted with Object Lock retention metadata.

### S4 — RoPA export under load (30 min budget)

* Regulator demands a GDPR RoPA covering all assets (~10k).
* Tenant Admin triggers `POST /ropa/generate?regulation=GDPR&format=pdf`;
  job streams to the `meshant-staging-ropa-output` bucket.
* DPO downloads + validates the PDF, asserts every Asset with
  `processing_purposes` is present.
* Acceptance: generation completes in ≤ 30 s (per 232.4.16 SLO);
  manifest matches `Asset.objects.filter(...).count()` for the
  test tenant.

### S5 — DPIA required for high-risk asset (45 min budget)

* Tenant Admin marks an Asset as containing biometric data (high-risk
  trigger).
* System auto-creates a `DPIA` record in DRAFT; DPO walks the
  multi-step wizard to APPROVED.
* DPO blocks an attempted publish until the DPIA is APPROVED.
* Acceptance: DPIA gate enforced on publish; APPROVED DPIA persisted
  with reviewer signature; "DPIA required" badge visible on Asset
  detail page.

### S6 — Consent revocation propagates (30 min budget)

* Subject revokes consent for `marketplace_personalization` purpose.
* System must:
  * Mark the consent record revoked (HMAC-verified).
  * Publish `consent.revoked` webhook to the test webhook endpoint.
  * Block downstream marketplace order creation that requires that
    purpose (`enforce_marketplace_order_consent`).
* Acceptance: webhook delivered within 30 s of revocation; order
  attempt returns 403 with structured `CONSENT_REVOKED` signal.

### S7 — Statuspage incident communication (15 min budget)

* SRE on-call posts a synthetic "Consent Banner degraded" incident on
  Statuspage (per 232.8.9).
* DPO confirms tenant-facing email comm fires; observer captures the
  incident URL + timestamp.
* Acceptance: incident published, comms delivered, end-to-end ≤ 15 min.

## Evidence capture

For each scenario the observer appends one row to
[docs/audit-reports/232-tabletop-ledger.md](../audit-reports/232-tabletop-ledger.md)
with:

* Scenario ID (S1–S7)
* Run date (UTC)
* Wall-clock duration vs budget (delta in minutes; positive = within budget)
* Pass / fail / partial
* Artefact links (ZIP / PDF / Statuspage incident URL / breach proof
  S3 key)
* One-line root-cause note if partial / fail

A run is **green** when every scenario is `pass` AND every wall-clock
duration is within budget. One `fail` row reverts the run; one
`partial` row downgrades it to `partial` (DPO can either accept or
re-schedule).

## Sign-off

| Role | Name | Date | Run outcome |
|---|---|---|---|
| Compliance Engineering Lead | _to be filled_ | _YYYY-MM-DD_ | _green/partial/fail_ |
| DPO | _to be filled_ | _YYYY-MM-DD_ | _attestation_ |
| Legal Counsel | _to be filled_ | _YYYY-MM-DD_ | _attestation_ |
| EM | _to be filled_ | _YYYY-MM-DD_ | _approval to flip flags_ |

A green run unlocks per-tenant flag flips (D232.3) per the cadence in
the proposal. A partial / fail run requires a follow-up runbook and
re-execution before any production flag flips.

## Maintenance

Review this playbook:

- After every Phase 232 sub-phase ships (sub-phase may add a new
  scenario).
- After any regulator change (e.g. EU DPF re-adequacy, PIPL_CN clock
  update) — the timing budgets here track the statutory matrix in
  `regulation_policies/`.
- Annually thereafter.

Updates land in this file via PR review; the ledger appends per run.

## Maintenance

- **Owner**: Platform Engineering
- **Last reviewed**: 2026-05-13
- **Next review**: 2026-08-11

# Phase 232 public-endpoint pen-test ledger

**Phase:** 232.DoD.6
**Owner:** Security Engineering Lead (custodian) / EM (approver)
**Last reviewed:** 2026-05-05

Phase 232.DoD.6 mandates: *"Public-endpoint pen-test results clean
before any subsystem flips on for production."* This file is the
authoritative ledger of pen-test runs against the Phase 232 public
attack surface (DSAR public form, consent banner, RoPA download links,
breach emergency form).

## Companion artefacts

* **Scope + procedure**: [docs/runbooks/dsar-public-penetration-review.md](../runbooks/dsar-public-penetration-review.md)
* **Automated baseline workflow**: [.github/workflows/phase232-public-zap-baseline.yml](../../.github/workflows/phase232-public-zap-baseline.yml)
  — runs ZAP weekly when `PHASE232_ZAP_TARGET` is set; results uploaded
  as a workflow artifact.
* **Manual Burp engagement**: per the runbook; outputs land in this
  ledger.

## Closure criteria per subsystem

A subsystem flag flips ON in production only after **all** of:

- One run with **zero HIGH/CRITICAL findings** that targets the
  subsystem's public endpoints.
- Any MEDIUM/LOW findings have either been remediated or have a tracked
  exception with sign-off from Security Engineering Lead + DPO.
- Tabletop exercise ledger ([docs/audit-reports/232-tabletop-ledger.md](./232-tabletop-ledger.md))
  is green (DoD.7 gate).

## Run ledger

Each row is one pen-test engagement (ZAP baseline, ZAP active scan, or
Burp manual). Append new rows; do **not** edit historical rows — they
are the audit trail.

### ZAP baseline runs (automated)

| Run date (UTC) | Trigger | Target | Findings (H/M/L) | Workflow run | Notes |
|----------------|---------|--------|------------------|--------------|-------|
| _YYYY-MM-DD_ | cron / dispatch | _staging URL_ | _0H / 0M / 0L_ | _GH run URL_ | _—_ |

### ZAP active scans (gated by Security)

| Run date (UTC) | Operator | Target | Findings (H/M/L) | Report path | Notes |
|----------------|----------|--------|------------------|-------------|-------|
| _YYYY-MM-DD_ | _name_ | _staging URL_ | _0H / 0M / 0L_ | _S3 / drive link_ | _—_ |

### Burp manual engagements

| Engagement window | Operator | Scope (subsystems) | Findings (H/M/L) | Report path | Notes |
|-------------------|----------|--------------------|------------------|-------------|-------|
| _YYYY-MM-DD → YYYY-MM-DD_ | _name_ | _DSAR / consent / breach / etc._ | _0H / 0M / 0L_ | _S3 / drive link_ | _—_ |

## Per-subsystem clean-status attestation

For each Phase 232 subsystem flipping ON in production, the Security
Engineering Lead records the most recent green run that exercised that
subsystem's public surface:

| Subsystem | Most recent green run | Date | Findings | Sign-off | Notes |
|---|---|---|---|---|---|
| 232.1 Consent management | _GH run URL / report path_ | _YYYY-MM-DD_ | _0H / 0M / 0L_ | _Sec Lead name_ | _—_ |
| 232.2 DSAR workflow | _GH run URL / report path_ | _YYYY-MM-DD_ | _0H / 0M / 0L_ | _Sec Lead name_ | _—_ |
| 232.3 Breach notification | _GH run URL / report path_ | _YYYY-MM-DD_ | _0H / 0M / 0L_ | _Sec Lead name_ | _—_ |
| 232.4 RoPA generator | _GH run URL / report path_ | _YYYY-MM-DD_ | _0H / 0M / 0L_ | _Sec Lead name_ | _—_ |
| 232.5 DPIA tooling | _GH run URL / report path_ | _YYYY-MM-DD_ | _0H / 0M / 0L_ | _Sec Lead name_ | _—_ |
| 232.6 Processor agreements | _GH run URL / report path_ | _YYYY-MM-DD_ | _0H / 0M / 0L_ | _Sec Lead name_ | _—_ |
| 232.7 Retention auto-enforcer | _GH run URL / report path_ | _YYYY-MM-DD_ | _0H / 0M / 0L_ | _Sec Lead name_ | _—_ |

## Closure block

| Role | Name | Date | Attestation |
|---|---|---|---|
| Security Engineering Lead | _to be filled_ | _YYYY-MM-DD_ | _all subsystems green; no open H/C_ |
| DPO | _to be filled_ | _YYYY-MM-DD_ | _privacy-impact concurrence_ |
| EM | _to be filled_ | _YYYY-MM-DD_ | _approval for production flip_ |

A signed closure block closes 232.DoD.6 for the listed subsystems.
Subsystems not yet exercised remain blocked from production flip until
their per-subsystem row has a green run.

## Maintenance

* The automated ZAP baseline runs weekly; results land here on every
  green run + on every red run with a triage note.
* Manual Burp engagements happen on a quarterly cadence + before any
  flag flip.
* If a finding moves from HIGH/CRITICAL to remediated, append a new
  row with the remediation reference (PR / commit SHA) — do not edit
  the original.

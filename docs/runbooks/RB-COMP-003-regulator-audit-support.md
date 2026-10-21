# RB-COMP-003 — Regulator Audit Support & Evidence Packaging

**Date:** 2026-05-20
**Feature flag:** N/A (platform-level compliance infrastructure)
**Audit event:** `COMPLIANCE_EVIDENCE_EXPORTED`, `REGULATOR_AUDIT_PACKAGE_CREATED`

## 1. Overview

Operational procedure for supporting external regulator audits — evidence
packaging, audit trail exports, compliance report generation, and
data subject access request (DSAR) evidence. Complements the
compliance fail-closed (RB-COMP-001) and consent (RB-COMP-002) runbooks
with the regulator-facing operational workflow.

## 2. When This Runbook Fires

- **Regulator audit notification** — GDPR Art. 30, CCPA, or other regulatory
  authority requests audit evidence.
- **DSAR evidence package request** — data subject requests full processing
  record (GDPR Art. 15).
- **Internal compliance audit** — quarterly or annual compliance review.
- **DPO request** — Data Protection Officer requests compliance evidence.

## 3. Scope

1. **Evidence packaging** — `create_regulator_audit_package` management command
   generates a ZIP of: audit event log for the requested period, compliance
   scan history, consent records, DSAR processing log, RoPA report, DPIA
   register, and breach notification log.
2. **Audit trail export** — filtered by tenant, date range, event category.
   Output as JSON Lines for machine processing.
3. **Compliance report generation** — per-tenant, per-regulation compliance
   status report with framework-level detail.
4. **Chain of custody** — each export is checksummed (SHA-256) and the hash
   is logged as an audit event for tamper-evidence verification.

## 4. Investigation Procedure

### 4.1 — Create evidence package

```bash
python manage.py create_regulator_audit_package \
  --tenant <tenant-slug> \
  --regulation GDPR \
  --from 2025-01-01 \
  --to 2025-12-31 \
  --output /tmp/audit-package.zip
```

### 4.2 — Verify package integrity

```bash
sha256sum /tmp/audit-package.zip
# Compare against the hash logged in:
# GET /api/v1/audit/events/?action=COMPLIANCE_EVIDENCE_EXPORTED&since=1h
```

### 4.3 — Export audit trail

```bash
python manage.py export_audit_trail \
  --tenant <tenant-slug> \
  --since 2025-01-01 \
  --until 2025-12-31 \
  --format jsonl \
  --output /tmp/audit-trail.jsonl
```

## 5. Remediation

### Missing compliance data

1. Check if the tenant had `compliance_*_enabled` flags active during the
   requested period
2. Check retention policy: data may have been deleted per retention window
3. If within retention window but missing: investigate compliance-service
   health during the affected period

### Incomplete evidence package

1. Re-run with `--verbose` to see which sections failed
2. Check each sub-module's data availability:
   - Compliance scans: `GET /api/v1/compliance/runs/?tenant=<slug>`
   - Consent records: `GET /api/v1/governance/consent-records/`
   - DSAR log: `GET /api/v1/governance/dsar/`
   - RoPA: `GET /api/v1/ropa/`
   - DPIA: `GET /api/v1/dpia/`
   - Breach log: `GET /api/v1/governance/breach/`

## 6. Forensic Queries

```sql
-- Compliance scan coverage for a tenant in a period
SELECT framework, regulation_key, COUNT(*) AS scans,
       SUM(CASE WHEN allowed_to_store THEN 1 ELSE 0 END) AS compliant,
       SUM(CASE WHEN NOT allowed_to_store THEN 1 ELSE 0 END) AS non_compliant
FROM compliance_runs
WHERE tenant_id = '<tenant-uuid>'
  AND created_at BETWEEN '2025-01-01' AND '2025-12-31'
GROUP BY framework, regulation_key
ORDER BY framework, regulation_key;
```

## 7. Evidence Package Contents

| Section | Source | Description |
|---|---|---|
| audit_trail.jsonl | `audit_events` table | All audit events for the tenant in the period |
| compliance_scans.jsonl | `compliance_runs` table | All compliance scan results |
| consent_records.jsonl | Consent module | All consent receipts |
| dsar_log.jsonl | DSAR module | All data subject requests and responses |
| ropa_report.json | RoPA module | Record of Processing Activities |
| dpia_register.jsonl | DPIA module | Data Protection Impact Assessments |
| breach_log.jsonl | Breach module | Breach notifications |
| checksums.txt | SHA-256 | Checksums of all files in the package |

## 8. Related

- **Spec**: `openspec/changes/preprod01/specs/compliance/`
- **Design**: `openspec/changes/preprod01/design.md` — Phase 232 (Compliance Programme)
- **Code**:
  - `hub/apps/compliance/models.py` — `ComplianceRun`
  - `hub/apps/compliance/management/commands/create_regulator_audit_package.py`
  - `hub/apps/audit/management/commands/export_audit_trail.py`
- **Alerts**: `monitoring/prometheus/alerts/compliance.yml`
- **Dashboard**: `monitoring/grafana/dashboards/compliance-intake-gate.json`
- **Cross-runbook**:
  - [`RB-COMP-001-compliance-fail-closed.md`](RB-COMP-001-compliance-fail-closed.md)
  - [`RB-COMP-002-consent.md`](RB-COMP-002-consent.md)
  - [`RB-GDPR-001-data-request-failure.md`](RB-GDPR-001-data-request-failure.md)
  - [`phase232-regulator-audit-tabletop.md`](phase232-regulator-audit-tabletop.md)

## Maintenance

- **Owner**: Compliance Team
- **Last reviewed**: 2026-05-20
- **Next review**: 2026-08-18

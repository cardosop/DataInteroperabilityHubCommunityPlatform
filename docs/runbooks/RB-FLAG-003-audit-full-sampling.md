# RB-FLAG-003 — Compliance Audit Full Sampling Feature Flag

**Flag:** `compliance_audit_full_sampling`
**Stage:** GA
**Owner:** privacy-eng@meshant.com
**Created:** 2026-05-16 (Phase 283.6.4)
**Sensitive:** Yes (flipping back to sampled mode hides per-read forensics)

## Design Decision

`default_new=False` is the **correct default**. Rationale:
- **Cost safety:** Full sampling emits a `FILE_METADATA_VIEWED` audit event on every successful `GET /files/{id}/`. For tenants with high read volume, this can generate millions of audit rows per day, inflating operational cost.
- **Progressive disclosure:** New tenants start with 10% deterministic sampling (see Phase 260.2.F B3-5), which provides statistically valid coverage for compliance without the cost overhead. Tenants needing forensics-level tracking opt in.
- **Regulatory alignment:** Most privacy regulations require "appropriate technical measures" — 10% deterministic sampling satisfies this for the default posture. Full sampling is a premium forensics feature.
- **Two-person rule:** Flag is `sensitive=True`, requiring dual PLATFORM_ADMIN approval to flip (Phase 235.1).

## Symptom Index

| Symptom | Likely cause | First checks |
|---------|-------------|--------------|
| `FILE_METADATA_VIEWED` volume spike | Flag recently enabled; tenant has high file read volume | Audit event rate; `file_metadata_viewed_total` |
| Missing read events in investigation | Flag is OFF (sampling mode); specific read fell in the 90% unsampled | Audit log; `compliance_audit_full_sampling` flag state |
| Audit DB storage growth | Full sampling enabled on high-traffic tenant | `audit_events_total{event="FILE_METADATA_VIEWED"}`; DB disk usage |
| Sampled audit incomplete for legal hold | Tenant requires forensics but flag is OFF | Flag state; legal hold requirements document |

## Metrics

- **Dashboard:** `monitoring/grafana/dashboards/audit.json`
- **Primary:** `file_metadata_viewed_total{tenant_id, sampling_mode}`
- **Sampling rate:** `file_metadata_sampling_ratio{tenant_id}` (1.0 = full, 0.1 = sampled)
- **Storage:** `audit_table_size_bytes{event_type="FILE_METADATA_VIEWED"}`
- **Audit:** `FILE_METADATA_VIEWED` (always), `TENANT_FEATURE_FLAG_FLIPPED` on toggle

## Execution Checklist

1. Verify flag state: `GET /api/v1/admin/tenants/{id}/feature-flags/`
2. Check audit volume: `file_metadata_viewed_total` rate over last 24h
3. Storage impact: audit DB disk usage trend; retention policy window (30-day default)
4. Sampling verification: in sampled mode, verify ~10% of reads produce events (check over >1000 reads)
5. Flag flip requires dual approval: two PLATFORM_ADMIN must approve (sensitive flag)
6. Flag flip audit: `TENANT_FEATURE_FLAG_FLIPPED` with `flag=compliance_audit_full_sampling`

## Escalation

- **P3** — Audit event rate increase >2x after flag enable (expected; monitor storage)
- **P2** — Audit DB approaching 80% disk capacity due to full-sampling volume
- **P1** — Audit event loss detected (audit-DB outage during full-sampling mode)

## Related

- `hub/apps/files/metadata_view_audit.py` — Sampling logic (Phase 260.2.F B3-5)
- `hub/apps/audit/event_types.py` — `FILE_METADATA_VIEWED` event definition
- `docs/runbooks/audit-tamper-evidence.md` — Audit integrity verification

## Maintenance

- **Owner:** Privacy Engineering
- **Last reviewed:** 2026-05-16
- **Next review:** 2026-08-16

# RB-FLAG-007 — Processor Agreements Feature Flag

**Flag:** `compliance_processor_agreements_enabled`
**Stage:** GA (opt-in — `default_new=False`, requires DPO signoff)
**Owner:** privacy-eng@meshant.com
**Created:** 2026-05-16 (Phase 283.6.4)

## Scope

Gates the Phase 232.6 processor register, Article 28 agreement templates, and asset–processor linking. Default OFF for new tenants (opt-in with DPO signoff). When enabled, tenants can maintain a register of data processors, generate Article 28-compliant agreements, and link assets to processors for compliance tracking.

## Symptom Index

| Symptom | Likely cause | First checks |
|---------|-------------|--------------|
| Processor register returns 403 | `compliance_processor_agreements_enabled=False` | Flag state; DPO signoff status |
| Article 28 agreement generation fails | Template missing for jurisdiction; asset–processor link broken | Template registry; `processor_agreement_template_errors_total` |
| Asset–processor link broken | Processor or asset deleted; cascading unlink | Asset status; processor status; `processor_agreement_link_errors_total` |
| Agreement export PDF corrupted | Rendering engine error; missing font/asset | `processor_agreement_export_errors_total`; template rendering logs |
| DPO review workflow stuck | Delegation chain broken; reviewer unavailable | `ApprovalDelegation` state; DPO availability |

## Metrics

- **Dashboard:** `monitoring/grafana/dashboards/compliance.json`
- **Primary:** `processor_agreement_operations_total{operation}` (create, link, export, review)
- **Errors:** `processor_agreement_errors_total{error_code}`
- **Audit:** `PROCESSOR_AGREEMENT_CREATED`, `PROCESSOR_AGREEMENT_REVIEWED`, `PROCESSOR_LINKED_TO_ASSET`

## Execution Checklist

1. Verify flag state: `GET /api/v1/admin/tenants/{id}/feature-flags/`
2. Confirm DPO signoff: check `requires_dpo_signoff=True` in registry → signoff record exists
3. Test processor register: `GET /api/v1/processor-agreements/processors/`
4. Test agreement creation: create Article 28 agreement for a test processor
5. Test asset–processor linking: `POST /api/v1/processor-agreements/links/`
6. Verify PDF export: agreement exports cleanly with correct jurisdiction template
7. Flag flip audit: `TENANT_FEATURE_FLAG_FLIPPED` with `flag=compliance_processor_agreements_enabled`

## Escalation

- **P3** — Template rendering issues for specific jurisdiction
- **P2** — Agreement export failing for all tenants
- **P1** — Processor register data loss (restore from backup; SEV1)

## Related

- `docs/runbooks/phase232-compliance-programme.md` — Compliance programme overview
- `docs/mvpdocs/concepts/governance.md` — Governance concepts
- `hub/apps/processor_agreements/views.py` — REST surface

## Maintenance

- **Owner:** Privacy Engineering
- **Last reviewed:** 2026-05-16
- **Next review:** 2026-08-16

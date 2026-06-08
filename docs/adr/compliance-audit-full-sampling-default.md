# ADR: `compliance_audit_full_sampling` Default — `default_new=False`

**Date:** 2026-05-16
**Phase:** 283.6.3
**Status:** Accepted
**Author:** Platform Engineering

## Context

The feature flag `compliance_audit_full_sampling` controls whether every successful
`GET /files/{id}/` emits a `FILE_METADATA_VIEWED` audit event (full sampling) or
only ~10% of reads emit the event (deterministic sampling per Phase 260.2.F B3-5).

The flag is GA-stage with `default_new=False`. This ADR documents why `False` is
the correct default for new tenants.

## Decision

`default_new=False` is confirmed as the **correct default**. Full sampling is an
opt-in premium forensics feature, not a baseline compliance requirement.

## Rationale

1. **Cost safety.** Full sampling emits one audit row per file read. For tenants
   with high read volume (e.g., 10M+ reads/day), this generates 10M audit rows/day
   vs 1M with 10% sampling — a 10× storage cost increase. New tenants should not
   incur this cost by default.

2. **Progressive disclosure.** 10% deterministic sampling provides statistically
   valid coverage for routine compliance needs. The sampling uses a deterministic
   hash (tenant_id + file_id + date), so the same read always produces the same
   sampling decision — an auditor can verify coverage without full volume.

3. **Regulatory alignment.** Most privacy regulations (GDPR Art. 30, CCPA, LGPD)
   require "appropriate technical measures" for access logging. 10% deterministic
   sampling satisfies this baseline. Full sampling is a premium feature for tenants
   under consent decree, litigation hold, or forensics investigation.

4. **Two-person rule.** The flag is `sensitive=True` (Phase 235.1). Flipping it
   requires two PLATFORM_ADMIN approvals. This ensures full sampling isn't enabled
   (or disabled) unilaterally — appropriate given the cost and compliance implications.

5. **Precedent.** Other opt-in GA flags follow this pattern:
   - `compliance_dpia_enabled` — `default_new=False` (DPO signoff required)
   - `compliance_retention_enforcer_enabled` — `default_new=False` (DPO signoff required)
   - `compliance_intake_gate_enabled` — `default_new=False` (opt-in)

## Consequences

- New tenants start with 10% deterministic sampling, generating manageable audit volume.
- Tenants requiring full forensics must request a flag flip, which requires dual
  PLATFORM_ADMIN approval.
- Flag flip to `True` triggers `TENANT_FEATURE_FLAG_FLIPPED` audit event with
  `flag=compliance_audit_full_sampling`.
- Runbook `RB-FLAG-003` documents operational procedures for full-sampling mode.

## Alternatives Considered

**`default_new=True`** — Rejected. While it would provide maximum forensics coverage,
it imposes disproportionate cost on new tenants who haven't assessed their audit
volume needs. The cost of missing a read event in sampled mode is bounded (the
event is still deterministically reproducible); the cost of runaway audit storage
is unbounded.

## Related

- `hub/apps/files/metadata_view_audit.py` — Sampling implementation
- `docs/runbooks/RB-FLAG-003-audit-full-sampling.md` — Operational runbook
- `hub/apps/tenants/feature_flag_registry.py` — Flag definition

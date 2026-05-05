# Risk Register — Phase 250 Asset Creation Hardening

**Phase**: 250.0.17
**Status**: Authoritative; reviewed at every phase milestone (250.0 → 250.7) and at closeout.
**Owners**: Phase 250 Driver, EM (Eng), Risk Officer

## Methodology

Each row scores Likelihood × Impact ∈ {LOW, MED, HIGH, CRITICAL}. Mitigation owner + status fields tracked. Risks closed-out are kept in the register as historical record (greyed status).

| Likelihood | Impact | Severity |
|---|---|---|
| LOW | LOW | LOW |
| LOW | MED | LOW |
| LOW | HIGH | MED |
| MED | MED | MED |
| MED | HIGH | HIGH |
| HIGH | MED | HIGH |
| HIGH | HIGH | CRITICAL |
| ANY | CRITICAL | CRITICAL |

## Active risks

| # | Description | Likelihood | Impact | Severity | Mitigation | Owner | Status |
|---|---|---|---|---|---|---|---|
| R-001 | Workflow re-sequence (250.1.A) regresses P95 latency for asset-creation API | MED | MED | MED | D250.7 workflow versioning lets prior version coexist for 14 days; nightly k6 perf gate (T2-2 enforced); rollback via env-var (D250.5). | EM | OPEN |
| R-002 | Compliance microservice version mismatch on first deploy → silent runtime failures | MED | HIGH | HIGH | D250.15 cross-service version-compatibility startup check (Phase 250.0.14) — Hub fails to start if version < required. | SRE | OPEN |
| R-003 | Webhook subscribers receive `asset.created` event timing change → integration breakage | MED | HIGH | HIGH | 30-day soak with `compliance_fail_closed_enabled=False` on existing tenants per D250.12; pre-merge announcement (250.0.18 protocol); explicit timing change documented in webhook reference docs (per [audit-reports/b2-6-asset-webhook-timing-2026-05-03.md](../audit-reports/b2-6-asset-webhook-timing-2026-05-03.md)). | EM | OPEN |
| R-004 | Optimistic-locking 412s overwhelm frontend without retry-with-merge UX | MED | MED | MED | Figma sign-off REQUIRED per F2-7 before 250.7.B implementation; rolling-deploy-safe via `OPTIMISTIC_LOCK_REQUIRE_IF_MATCH=False` env var for first 7 days. | Frontend Lead | OPEN |
| R-005 | `Asset.objects.create()` direct callers (9 production sites per [audit-reports/b2-13-direct-asset-create-callers-2026-05-03.md](../audit-reports/b2-13-direct-asset-create-callers-2026-05-03.md)) bypass the new gate ordering | MED | HIGH | HIGH | Phased migration via 250.1.G; CI lint guard (`scripts/check_asset_create_bypass.py`) added to fail PRs that introduce new bypasses; existing 9 sites refactored in separate PRs with feature-flag gating per D250.12. | EM | OPEN |
| R-006 | Federated import default-FALSE rollout surprises tenants currently using marketplace integrations | MED | MED | MED | 30-day notice email to all tenants with `MarketplaceConnection` rows; explicit flag-flip request UI; documented in CHANGELOG. | DPO + Legal | OPEN |
| R-007 | `ExternalResourceReference.url` SSRF holes (Gap 14 partially closed per [audit-reports/gap-14-external-resource-ssrf-idor-2026-05-03.md](../audit-reports/gap-14-external-resource-ssrf-idor-2026-05-03.md)) | LOW | HIGH | MED | 250.5.B.1 contingency sub-task adds model-level `clean()` calling `validate_webhook_url()`; pre_save signal as belt-and-suspenders; security audit at 250.5.E STRIDE. | Sec | OPEN |
| R-008 | Cross-tenant IDOR on federated assets (Gap 14) | LOW | HIGH | MED | 250.5.C tenant-isolation pytest sweep + queryset filter audit; HTTP 404 (not 403) for cross-tenant reads to prevent existence leak. | Sec | OPEN |
| R-009 | DPO/Legal sign-off on federated import (250.5.A) blocks deploy | MED | HIGH | HIGH | Engage DPO + Legal at phase kickoff per RACI matrix; threat model pre-circulated; office-hour Q&A scheduled 1 week before deploy per 250.0.18 protocol. | EM + DPO + Legal | OPEN |
| R-010 | Workflow versioning soak window (14 days) too short for some long-running async workflows | LOW | MED | LOW | Per-workflow override allowed via `WorkflowVersionManager.get_versions_eligible_for_inflight_runs(soak_days=N)` (Phase 250.0.12); telemetry on deprecated-version usage; alert when long-running runs exceed soak. | Eng | OPEN |
| R-011 | `Idempotency-Key` Redis storage growth (24h × 100 RPS = ~8 GB/day) | MED | LOW | LOW | Redis TTL eviction; cardinality cap on per-tenant key count; storage growth tracked in capacity-planning addendum (Phase 250.0.24). | SRE | OPEN |
| R-012 | `visibility` field deprecation breaks external integrators reading the field | MED | MED | MED | Two-phase deprecation (250.3.B nulls column; 250.3.C drops after 3 release cycles); `visibility` remains read-only in Phase 1; CHANGELOG + pre-merge announcement. | EM | OPEN |
| R-013 | Auto-activation default ON (D250.2) trips compliance gate on edge-case data + re-routes user to manual activation | MED | LOW | LOW | Per-tenant override `tenant.asset_auto_activate_on_gate_pass`; default TRUE only when ALL gates PASS (WARN does not auto-activate); UX banner explains. | Eng | OPEN |
| R-014 | Semantic mapping retry queue depth grows under semantic-service outage | MED | MED | MED | Exponential backoff (1m / 5m / 30m / 1h / 2h / dead-letter); per-tenant rate-limit max 10 retries/min; dead-letter triggers ops PagerDuty (NOT customer's). | SRE | OPEN |
| R-015 | KYC gate (Gap 8 — already closed per [audit-reports/gap-8-kyc-marketplace-publish-2026-05-03.md](../audit-reports/gap-8-kyc-marketplace-publish-2026-05-03.md)) regresses if a future change drops the `tenant__kyc_status="VERIFIED"` filter | LOW | HIGH | MED | Add a regression test asserting un-verified-tenant publish returns 404 from public catalogue; pin in 250.3.A test plan. | Eng | OPEN |
| R-016 | Trivy scan growth from new Phase 250 SDKs (cross-service version client deps) trips deploy gate | LOW | MED | LOW | Pre-emptive CVE audit before adding new deps to `requirements.txt`; `.trivyignore` budget reviewed in Phase 250.0.22 CI matrix. | SRE | OPEN |
| R-017 | OTel sampling change (250.0.23 — 100% on fail-closed paths) explodes trace volume | LOW | LOW | LOW | Per-path sampling rate configurable; cardinality monitored at OTel collector; tail-sampling for happy-path keeps cost bounded. | SRE | OPEN |
| R-018 | Stale feature flags accumulate (Phase 250 introduces ~6 new flags) | HIGH | LOW | MED | D250.13 stale-flag CI alert; 180-day retire-by enforcement; tech-debt review weekly per Phase 250.0.15 lifecycle policy. | Platform Eng | OPEN |
| R-019 | Cross-team coordination delay (Sec + DPO + Legal sign-offs) slips Phase 250 calendar | MED | MED | MED | RACI matrix front-loads conversations (Phase 250.0.16); pre-circulated artifacts; office-hour Q&A protocol per 250.0.18. | EM + Director | OPEN |
| R-020 | Optimistic-locking introduced ASSET_VERSION_MISMATCH errors confuse first-time users | MED | LOW | LOW | 3-way merge UX (per ADR-AST-004) + remediation URL in error response + tooltip explaining concurrent-edit semantics. | Frontend Lead | OPEN |

## Closed risks

(Greyed entries are kept as historical record after Phase 250 closeout.)

| # | Description | Resolution | Closed by | Closed date |
|---|---|---|---|---|
| _(none yet — register opens at Phase 250.0.17)_ | | | | |

## Review cadence

- **Pre-phase kickoff**: full register reviewed; new risks added.
- **Weekly during phase execution**: register status updated by EM; CRITICAL/HIGH risks reviewed in standup.
- **Phase milestone (each 250.X completion)**: closed-out risks moved to Closed section.
- **Phase 250 closeout**: full register reviewed; risks accepted, mitigated, or transferred to Phase 251+ register if persistent.

## Risk acceptance procedure

A risk MAY be accepted (not mitigated) only with explicit sign-off from:
- **LOW severity**: EM (Eng).
- **MED severity**: EM (Eng) + Eng Director.
- **HIGH severity**: Eng Director + Sec / DPO / Legal as RACI dictates.
- **CRITICAL severity**: Eng Director + Risk Officer + at least one C-suite signatory.

Accepted risks are documented here with the sign-off chain in the Status field.

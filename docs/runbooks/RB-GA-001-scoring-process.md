# RB-GA-001 — GA Flag Scoring Process

**Owner:** platform-eng@meshant.com | **Created:** 2026-05-18
**Phase:** 285.7.6 | **Review:** Quarterly or after flag promotion

## 1. Overview

Every GA feature flag receives a readiness score (0–100) across the 13-gate
unified rubric. Scores are computed by `scripts/check_ga_gate_scores.py` and
published in `docs/ga-readiness-audit-2026-05.md`.

**Threshold:** ≥95 = fully production-ready. ≥70 = GA with documented gap plan.
<70 = blocked from GA promotion.

## 2. Automated Gates (Run Scripts)

These gates are scored by automated CI checks:

| Gate | Script / Command | What it checks |
|------|-----------------|---------------|
| CLI (1) | `python scripts/check_ga_gate_scores.py` | `datahub <group>` exists with ≥2 subcommands |
| SDK (2) | `python scripts/check_ga_gate_scores.py` | SDK module with dedicated API class + ≥2 methods |
| RLS (3) | `python hub/manage.py lint_rls_policies` | Every tenant_id-bearing model has paired RLS policy |
| Throttle (4) | `python hub/manage.py check_throttle_coverage` | Every View/ViewSet has `throttle_classes` |
| Audit (5) | `python scripts/check_ga_gate_scores.py` | Feature emits audit events on state transitions |

**Run all automated checks:**
```bash
python scripts/check_ga_gate_scores.py          # ≥70 threshold (CI gate)
python scripts/check_ga_gate_scores.py --strict # ≥95 threshold (readiness review)
python scripts/check_stale_defaults.py           # opt-in justification check
python scripts/detect_stale_feature_flags.py --fail-on-critical
python hub/manage.py check_throttle_coverage     # zero uncovered endpoints
python hub/manage.py lint_rls_policies           # RLS policy coverage
openspec validate preprod01 --strict             # change validation
```

## 3. Manual Gates (Verify Pages / Run E2E)

These gates require manual verification or E2E test execution:

| Gate | Verification Method |
|------|-------------------|
| E2E (6) | `npx playwright test frontend/e2e/journeys/` — Playwright spec exists and passes |
| A11y/Axe (7) | Route in `detail-pages-axe-manifest.ts`; `npx playwright test frontend/e2e/a11y/` — zero critical/serious violations |
| Dark Mode (8) | Manual walkthrough: toggle dark mode, verify all feature pages render with adaptive palette, no white backgrounds |
| Error UX (9) | ErrorDisplay / RetryBanner / toast patterns used; no white-screens on API 4xx/5xx |
| i18n (10) | `grep "useTranslation" frontend/src/features/<feature>/` — component uses `useTranslation()` |
| Runbook (11) | `docs/runbooks/RB-*-<feature>.md` exists with 7 sections |
| Metrics (12) | Prometheus counter/gauge registered in `observability/` app |
| Docs (13) | Feature in `PRODUCT_GUIDE.md` with flag name, default state, enable procedure |

## 4. Scoring Rules

**0–10 per gate.** Total: 0–130, normalized to 0–100 scale.

| Score | CLI | SDK | Error UX |
|-------|-----|-----|----------|
| **10** | Dedicated command group with ≥2 subcommands | Dedicated SDK class with ≥2 methods | ErrorDisplay + RetryBanner; toast on transient errors |
| **7** | Command group exists with 1 subcommand | SDK class exists with 1 method | ErrorDisplay used for main flow |
| **5** | No direct CLI | No dedicated SDK class | Basic error handling; some paths white-screen |
| **0** | No CLI path | No SDK path | No error handling |

**General gates (RLS, Throttle, Audit, E2E, A11y, Dark, i18n, Runbook, Metrics, Docs):**

| Score | Description |
|-------|------------|
| **10** | Fully implemented per gate definition |
| **7** | Partially implemented (e.g., some routes covered, runbook exists but incomplete) |
| **5** | Minimal coverage (e.g., shared runbook, partial a11y) |
| **0** | Not implemented |

## 5. Scoring Frequency

| Trigger | Action |
|---------|--------|
| **Quarterly** | Re-score all GA flags. Update `docs/ga-readiness-audit-YYYY-MM.md` |
| **After flag promotion** | Score the newly-promoted flag against all 13 gates |
| **After SEV1 incident** | Re-score affected flag to verify gates still hold post-incident |
| **After new feature launch** | Score the feature's flag within 1 week of GA |

## 6. Score Publication

1. Run `python scripts/check_ga_gate_scores.py` → copy scores
2. Update `docs/ga-readiness-audit-YYYY-MM.md` with new scores
3. If any flag drops below 70: create gap closure plan in `docs/adr/`
4. Notify #platform-eng Slack channel with score delta summary

## 7. Related

- `scripts/check_ga_gate_scores.py` — automated scoring script
- `scripts/check_stale_defaults.py` — opt-in justification check
- `docs/ga-readiness-audit-2026-05.md` — current scores
- `docs/runbooks/feature-flag-lifecycle.md` — flag lifecycle policy

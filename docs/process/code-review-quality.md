# Code Review Quality Monitoring (281.B.7.10)

**Date:** 2026-05-15  
**Owner:** Platform Engineering  
**Target:** Review latency <4h, quality assessed quarterly, checklist compliance tracked

## 1. Review Latency SLA

| Metric | Target | Measurement |
|---|---|---|
| Time-to-first-review | <4 hours (business hours) | GitHub PR `ready_for_review` → first review comment |
| Time-to-merge | <24 hours | `ready_for_review` → merged |
| Stale PR (>48h no activity) | <5% of open PRs | GitHub API query |
| Review response time (re-review) | <2 hours | Review requested → re-review submitted |

## 2. Quality Assessment Criteria

Each PR review is assessed quarterly on a 1-5 scale across 5 dimensions:

| Dimension | 1 (Poor) | 3 (Adequate) | 5 (Excellent) |
|---|---|---|---|
| **Correctness** | Missed obvious bugs | Caught logic errors | Caught edge cases + race conditions |
| **Security** | No security review | Checked auth/RLS | Checked OWASP Top 10 + injection + secrets |
| **Design** | Rubber-stamped | Suggested alternatives | Identified architectural implications |
| **Testing** | Accepted without tests | Verified test coverage | Suggested missing test cases |
| **Clarity** | No comments or vague "LGTM" | Specific, actionable feedback | Clear reasoning + links to docs/ADR |

## 3. Checklist Compliance

### Required Review Items (per PR)

- [ ] **RLS policies:** New models with `tenant_id` have RLS migration (CI enforced)
- [ ] **Throttle classes:** Search/semantic views have `throttle_classes` (CI enforced)
- [ ] **Audit events:** Search/SPARQL executions emit audit events (CI enforced)
- [ ] **Chain primitives:** Multi-rule ops use `execute_chain()` (semgrep enforced)
- [ ] **Dependencies:** New deps have license checked (CI enforced via `license-scan.yml`)
- [ ] **Documentation:** User-facing changes have changelog entry + docs update
- [ ] **Tests:** New code has unit + integration tests
- [ ] **Type hints:** New Python functions have type annotations
- [ ] **i18n:** User-facing strings use `_()` gettext (frontend: i18n keys)

### Exemption Tracking

Reviewers may skip items with documented justification:
```
SKIP_RLS: Model has no tenant_id — global config table
SKIP_I18N: Internal-only error message, never surfaced to users
SKIP_AUDIT: Read-only health endpoint, no audit needed
```

## 4. Quarterly Quality Audit

| Activity | Method | Output |
|---|---|---|
| Sample 20 random PRs | Review against 5-dimension rubric | Quality score per reviewer |
| Checklist compliance rate | Count PRs missing required items | Compliance % (target >95%) |
| Review latency p95 | GitHub API + CI tracking | Latency trend chart |
| Reviewer workload balance | Reviews per engineer per week | Workload distribution chart |
| Bug escape rate | Bugs found in production / total bugs | Escape rate % (target <5%) |

## 5. Monitoring Dashboard

Prometheus metrics emitted via CI:
- `code_review_latency_seconds{repo, pr}` — time to first review
- `code_review_checklist_compliance{repo, pr, item}` — 0/1 per checklist item
- `code_review_quality_score{reviewer, dimension}` — 1-5 quarterly score

## 6. Continuous Improvement

| Activity | Frequency | Owner |
|---|---|---|
| Review latency report | Weekly (automated) | CI bot |
| Quality audit sample | Quarterly | Platform Lead |
| Reviewer calibration | Quarterly (group review of 5 PRs) | Platform Lead |
| Checklist update | Bi-annually | Platform + Security |

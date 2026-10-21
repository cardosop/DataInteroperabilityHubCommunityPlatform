# Pre-Production Audit Retrospective — Phase 277 (May 2026)

**Date:** 2026-05-13
**Audit scope:** 26 dimensions (277.A.1–277.A.26), 100+ remediation tasks

## What worked

- **Audit-first architecture landed cleanly.** The 277.A audit pass (26 dimensions, each producing a structured gap report with severity and acceptance criteria) made the remediation phase systematic. Each remediation task had a clear spec reference, root cause, and fix sketch — zero ambiguity.
- **Existing infrastructure was reused heavily.** Many gaps were filled by wiring existing infrastructure into the request/response cycle rather than building new primitives. Examples: `APIVersionMiddleware` existed but wasn't in `MIDDLEWARE`; `ManagementCommandAdminRouter` existed but lacked audit events; `CircuitBreaker` existed but wasn't wired into RQ task consumers.
- **TDD/contract-first approach prevented regressions.** Every backend remediation shipped with a paired test file. Types-first FE work (quotaFormatting.ts, errorUtils.ts) meant shared changes propagated without per-file rework.
- **Documentation-as-code reduced context-switching.** Treating runbooks, ADRs, and templates as code artefacts (committed, reviewed, versioned) meant docs and code stayed in sync.

## What didn't work

- **Scope creep from "6 tasks" to "100+ tasks."** The audit revealed far more gaps than anticipated — each A-pass dimension uncovered 3–8 remediation items. The original estimate of 6 management command audits ballooned to a full 26-dimension sweep with 100+ tasks. Future audits should budget a 3–5× multiplier from initial gap estimate to remediation count.
- **Some tasks were already completed by prior phases and required reverification only.** Approximately 30% of 277.B remediation tasks (277.B.085 GDPR FE, 277.B.087 Merkle CI, 277.B.094 unique constraint, 277.B.096 two-person rule) turned out to be already implemented — the audit report missed the fact that Phase 224-225 and Phase 235 had already closed these gaps. A reconciliation pass between the audit report and the git history before task generation would have saved effort.
- **Frontend `shared/` directory .gitignore caused commit friction.** Multiple frontend components created under `frontend/src/shared/` required `git add -f` to bypass a blanket `.gitignore` rule. The rule was intended for `node_modules`-style artifacts but caught source code.
- **The tasks.md file grew to 22,000+ lines.** This made the task tracker unwieldy — searching for specific task IDs required grep. Future phases should consider a database-backed tracker or per-phase task files.

## Surprise findings

- **The `ManagementCommandAdminRouter` class existed but was never implemented.** It was referenced in `DATABASE_ROUTERS` settings but the class body was entirely missing — every management command was using `default` (RLS-enforcing) credentials. This was a P0 gap found at the DB router level, not in any individual command.
- **`display.py` dependencies lay dormant for 7 months.** The `html2text` library was already in `requirements.txt` and the plain-text email generation pipeline was wired — it just needed 3 explicit `.txt` templates to be created. The infrastructure was complete; the documentation task was the gap.
- **`RESOURCE_COUNTERS` had 30+ registered counters but only 6 were queried.** The `/me/usage/` endpoint hardcoded 6 resource types while the billing limit registry had full counter definitions for all 30 `KNOWN_LIMIT_KEYS`. Tenants were receiving false headroom on 24 resource types.

## Effort — actual vs estimate

| Dimension | Estimated tasks | Actual tasks | Ratio |
|---|---|---|---|
| Auth & tenancy (277.A.14-15) | ~10 | ~25 | 2.5× |
| Observability (277.A.2, 277.A.16, 277.A.26) | ~8 | ~18 | 2.3× |
| Compliance & privacy (277.A.12, 277.A.17) | ~6 | ~14 | 2.3× |
| API surface (277.A.18) | ~5 | ~12 | 2.4× |
| Documentation & DX (277.A.12) | ~4 | ~8 | 2.0× |
| CI & schema (277.A.11, 277.A.16) | ~3 | ~6 | 2.0× |
| **Total** | **~36** | **~83 implemented, ~17 verified-complete** | **2.8×** |

## Lessons for future phases

1. **Reconcile audit against `git log` before generating task list.** The 30% overlap with prior phases could have been caught by diffing the audit report's "Missing" items against prior commit messages.
2. **Use "verified-complete" as a first-class task status.** Many tasks required zero code changes — they were already done. A dedicated status (`[v]` or `VERIFIED`) would distinguish "implemented during this phase" from "verified as already complete."
3. **Per-phase task files scale better than monolithic tracker.** The 22,000-line `tasks.md` slowed down editing and searching. Per-phase files (`tasks-277B-001-020.md`, etc.) would have been more ergonomic.
4. **Audit dimensions are the right grain.** The 26 A-dimensions provided natural epics; the B-remediations were concrete sub-tasks. This 2-level structure was the most successful part of the process — keep it.

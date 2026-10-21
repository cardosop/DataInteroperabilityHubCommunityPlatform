# Critical Review — openspec/changes/oss-release-remediation

**Date:** 2026-10-06 · **Reviewer:** critical re-audit of the plan against both audit reports ([round 1](../audits/oss-maturity-assessment-2026-10-05.md), [round 2](../audits/round2-deep-review-findings-2026-10-05.md)), the pilot program state (`openspec/changes/pilot-readiness/tasks.md`), and the repo's own contracts (CLAUDE.md, GATE conventions, U.6–U.8).

**Verdict:** the change has the right philosophy — root-cause-first, pattern-level fixes, verification per repo convention — and correctly sequences the four hard edges (secrets → public; authz → pilot onboarding; money → Stripe-live; pipelines → pilot E2E). But as written it has **~15 substantive coverage gaps**, several **sequencing hazards that would break real flows if executed in the written order**, and an **over-optimistic schedule that ignores the pilot program running in parallel on the same team**. It is not yet execution-ready.

---

## 1. What the plan gets right

1. **Pattern-level taxonomy (P1–P6) is the correct altitude** — fixes classes, not 100+ symptoms; each workstream cites the canonical correct pattern that already exists in the repo (`locked_contract_version()`, atomic job claims, `run_after_commit`, files `get_object()` IDOR audit).
2. **Milestone ordering respects the real hard edges** (M1 gates pilot onboarding, M2 gates Stripe-live, M3 gates pilot E2E, M5 gates release).
3. **Conventions section is mostly right**: RED-first pins, W16, GATE-40, atomic domain commits, batch verification.
4. **DoD is concrete and measurable** (6 items, including stranger-path ≤30 min and fork-CI green).
5. **Risk register catches the two scariest items** (history rewrite coordination; RLS arming) — though it misses several others (§4).

## 2. Coverage gaps — findings from the audits that no task owns

These are findings with explicit file:line evidence that **fall through the mapping table**. Each needs a task or an explicit deferral decision:

| # | Missing from the plan | Severity | Where it belongs |
|---|---|---|---|
| G1 | **Provider-boundary violations** (5 sites importing `databricks_admin` outside the sanctioned seam — round-1 HIGH) | HIGH | W1/W4 — cleanup or allowlist-extension with a GATE-29-style import checker |
| G2 | **`lint-no-client-tenant-id` is RED right now** (drifted line anchors) and its patterns miss `serializer.validated_data` reads — the exact class that let R2-B1/B2/event-replay through | HIGH | W1 — fix anchors + extend patterns as part of the authz hardening, not later |
| G3 | **Queryset-coverage audit for RLS arming**: D2 arms the GUC, but there is no task to sweep tenant-scoped viewsets for missing filters. Arming without the audit converts silent leaks into silent empty pages — safe, but only if someone notices | HIGH | W1.4 must include: automated "every tenant-scoped ModelViewSet filters its queryset" check + allowlist (the API audit's own recommendation) |
| G4 | **Dependency-vuln policy (CVE-ignore rot)**: `audit_pinned_cves --strict` exits 1, `.trivyignore` reviews overdue since ~May, pip-audit non-blocking — round-2 MEDIUM + pilot Week-4 item 4.2 | HIGH | W1/W7 — make pip-audit block new HIGH/CRITICAL; triage the backlog |
| G5 | **Refresh-token grace-period session transfer** (revoked token within 5s gets a fresh pair + revokes the victim's sibling — round-2 MEDIUM, security) | MEDIUM-HIGH | W1 (auth) |
| G6 | **Marketplace orders bypass the monthly access-request cap** (B-8), **versioning consumes `max_datasets`** (B-9), **job Redis counters fail open** (B-10) | MEDIUM | W2.7 (plan-limit workstream) |
| G7 | **Missing event emitters**: `contract.created` never emitted on the primary path (C1); `MarketplaceEventPublisher` is dead code (C2) — fixing the bus (W4.1) without deciding the emitters leaves the pub/sub surface still empty | MEDIUM-HIGH | W4.1 — wire or delete each publisher |
| G8 | **Working-tree FIX-FIRST items** from the delta review: `mock_audit_results.json` (DO-NOT-COMMIT), `service-client-audit.json` wiped to 0, spa_smoke vacuous default check, `ckan_token_remint` non-atomic writes, warehouse suite plain-`skipif` (W1 false-claim), **customer AWS account ID/IAM ARN in pilot docs (C1 privacy finding)**, `seed_pilot_privacy_tenant` RLS-contract violation (R1) | HIGH (C1, R1) | W0 (redaction before any push) + W9.2 |
| G9 | **Traceability drift items**: critical-registry header 37+33 vs 35+29 + regex absorbing 6 paid DB IDs; persona-journey-mapping staleness + unwired regenerator; duplicate EXPORT-001 spec; stale doc counts (181/146); TRACEABILITY_ARCHITECTURE.md counts | MEDIUM | W7.2/W9.3 — the plan touches registries for PAID annotations anyway; fix drift in the same change |
| G10 | **CLAUDE.md veracity pass**: the DRF 3.16 "throttled() removed" claim is false (round-1 HIGH); chain table omits 6 databricks chains; per-request RLS prose; settings.py:2127 comment | MEDIUM-HIGH | W9.3 — the plan's P4 promises contract audits but doesn't schedule the first correction |
| G11 | **Frontend WS subscribe-at-mount race** (subscriptions dropped before socket OPEN — MEDIUM-3) and **silent console-only save failures** (MEDIUM-8) are only partially owned by W5.4's wording | LOW-MEDIUM | W5.4 — make explicit |
| G12 | **settings.py password-guessing boot loop** (round-2 LOW, my own find) + `_DEV_SECRET_KEY` fallback pattern | MEDIUM (ops footgun) | W9.2 bootstrap hygiene |
| G13 | **Round-1 P2 deferrals are not declared as deferred**: contracts monolith, 200KB legacy files, 3 GraphQL stacks, signal `tenant_context` lint, 101 uncovered management commands, `routes.tsx` split, glob override, storybook-static, ODPS/CPO E2E coverage holes. "Fix all findings" is the goal; undeclared deferral looks like a gap | LOW (but audit-integrity) | Add a "Deferred to post-release with tickets" section to design.md |

## 3. Sequencing hazards — executed as written, these break real flows

| # | Hazard | Fix |
|---|---|---|
| S1 | **`ENFORCE_JWT_SCOPES` default-True (W1.3) flips before the frontend/SDK/CLI carry scopes.** The flip would 403 the platform's own clients — W5/W6 (client scope work) lands weeks later. | Re-sequence: client-side scope adoption first (or a per-surface flag with staging soak), then the default flip in W6/W9. Make the dependency explicit in the milestone graph |
| S2 | **W2.2 has an unstated ops prerequisite**: `Subscription.modify(items=...)` requires PRO/FREE **Stripe Price IDs provisioned in the Stripe dashboard** (U-owned action). Without it the fix is untestable in test mode. | Add prerequisite task + U-gated owner |
| S3 | **W1.5 assumes the pilot IdP exposes JWKS.** Some IdPs don't. authlib/pyoidc needs JWKS (or a cert-pinned fallback). If the pilot IdP lacks it, the SSO fix stalls M1. | Contingency in design: cert-pinned JWT validation or SAML re-scope; verify IdP capabilities as a Week-2 precondition |
| S4 | **History rewrite (W0.4) changes every SHA on `origin`** — the public remote (separate rewritten history) and the merge-back flow (`pull_public_pr.sh`, DCO gate) must be re-verified afterward; also protected-branch settings, open PRs, and dependabot PRs on the public remote survive the rewrite incorrectly. | Add W0/W7 item: end-to-end merge-back drill post-rewrite |
| S5 | **The 17 `backup-staging-*` tags are also restore points.** Deleting them without archiving loses staging restore history. | W0.6: mirror the tag trees to S3 before deletion (staging-backup exists) |
| S6 | **The pilot program and this program share one team.** Pilot Week-3/4 items (3.3 privacy pack, 3.4 journeys E2E, 4.1–4.5) overlap M1–M2 calendar. The plan never reconciles the two programs — 8 weeks of ~60 tasks plus pilot closeout on one engineer is not schedulable. | Add a cross-program section: either pilot-first sequencing (OSS M0 starts after pilot 4.5) or an explicit capacity split; milestones should be **order-based, not calendar-based** |
| S7 | **The working tree still has uncommitted pilot work.** The remediation branch must start from a clean, committed tree. | Precondition to M0: land the pilot Week-3/4 working tree (with its FIX-FIRST items, G8) first; branch `oss-release-remediation` from `prepro01`; define merge order with `main` |
| S8 | **Public remote is stale and broken (`mvp-up` references a missing file, no CI).** Between now and W7.1, public visitors see a broken repo; the first re-sync must land only after W7.1/W7.2 or it publishes red CI. | Explicit "public remote freeze" decision until W7.1 is green |
| S9 | **RLS arming is staged for Week 2 but the G3 audit and staging soak need more time than one week** for 56 apps / ~500 viewsets. | Move arming to end of M1 (after G3 lands) with a soak period; keep the GUC behind an env kill switch |

## 4. Risk-register omissions

1. **ClamAV fail-closed policy change** (W1.16) can block all downloads during AV outages — needs an ops decision (`SCAN_UNAVAILABLE_POLICY=allow` with alerting) or a runbook, not a silent default flip.
2. **W2 money migration on historical float prices** — plan says migration + audit, but not *reversibility*: route it through the U.7 migration-rehearsal + reversibility gates like every other schema change (conventions should state this for ALL workstreams — several add schema: UsageRecord unique, heartbeat columns, state-machine columns).
3. **Snowflake PAT rotation (W0.5) mid-batch** breaks live connector tests — coordinate with `verify_test_stack_creds` pre/post (partially covered; make it a named step).
4. **W1.3/register-throttle behavior changes are API-breaking for the pilot's own integrations** — needs an API-compatibility impact note per workstream in CHANGELOG (the repo's error-code catalogue gate also requires new error codes to ship with docs rows — new codes like REGISTRATION_JOIN_FORBIDDEN must be registered).
5. **`queryClient.clear()` on switch/logout (W5.2) increases refetch load** and the RLS GUC adds a set_config per request — both cheap, but the repo has perf gates (k6, contracts-perf-benchmark) that should be run after W4/W5, not assumed.
6. **Registry accounts/org ownership for W6 publishing** (PyPI/npm orgs, CI publishing secrets) is an unstated prerequisite.

## 5. Process & structure improvements

1. **No owners, no sizes.** tasks.md items need an Owner column (U / dev / legal / ops) and S/M/L size — otherwise Week assignments are fiction. Split U-gated steps explicitly (GCP/AWS/Azure/Databricks/Snowflake/Stripe console actions, IdP config, legal).
2. **D1 (license) sits on M0's critical path with a legal dependency** — decouple: start W1–W4 immediately (they don't need a license), give D1 a drop-dead date before W9.
3. **Independent review of the fixes**: the findings were agent-generated; the fixes should be reviewed by a second pass (peer session or independent agent review) before merge — the repo already has `security-review`/`code-review` mechanics; add a round-3 targeted re-audit of the changed surfaces to W10.
4. **Conventions addenda**: new enforcement points must emit audit events (audit contract) and register error codes (error-codes catalogue gate); new UI strings must enter the i18n catalog (i18n-check stays green); new test files must be registered in `scripts/batch_definitions.txt` (GATE-43); every new gate/pin must be added to the falsifiability harness (GATES registry) — proving the new checks can fail, not just pass.
5. **Per-milestone stop-the-line criteria** (pilot-readiness pattern): e.g., M1 stops if W1.4's audit surfaces unfixable queryset gaps; M2 stops if Stripe-side price modeling forces a re-scope. The plan has none.
6. **Milestone exit criteria**: one-line "leaves this milestone" summary per M0–M5 (gates + batches + evidence artifacts).
7. **Evidence-artifact ownership**: the two audit docs and this change itself are untracked — committing them should be task W0.9 (they are the evidence base).
8. **Maintenance model**: the user's goal includes "and maintained" — the plan has no release cadence, support matrix, or OSS security-update SLA section. Add to W9.3.
9. **Testing improvement opportunity**: hypothesis-based property tests for the money conversion helper and the two SQL compilers (round-trip + injection invariant) — the repo has no property-testing precedent, and these are the two highest-regret bug classes.
10. **GATE-30**: verify the change passes the openspec structural gate (the change ships no `specs/` — if the validator requires one, add a minimal spec or an explicit exemption note).

## 6. Priority-ordered revision list

**Must fix before execution starts:** G1, G2, G3, G4, G8 (privacy/redaction subset), S1, S2, S3, S4, S6, S7, S8 — coverage gaps on HIGHs and sequencing hazards that would break the platform's own clients, the pilot, or the publish flow.

**Should fix when revising:** G5, G6, G7, G9, G10, G12, G13 (declare deferrals), S5, S9, risk-register items 1–3, process items 1, 2, 3, 4, 5, 6, 7.

**Nice to have:** owners/sizes columns, milestone exit criteria, maintenance model, hypothesis tests, GATE-30 check, perf-gate additions.

**Bottom line:** the skeleton is right; the content has holes where audit findings fell between workstreams, and the calendar is fiction until the pilot-program collision (S6) and client-scope ordering (S1) are resolved. Revisions 2 of `proposal.md`/`design.md`/`tasks.md` should incorporate §2–§5 before any checkbox is marked.

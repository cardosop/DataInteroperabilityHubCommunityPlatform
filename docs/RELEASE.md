# Release criteria and gate

**Last Updated**: 2026-02-08  
**Status**: Active  
**Source**: gapfix1 Phase 6.3.1; testreview1 Phase 16 / GAP_REMEDIATION_PLAN §11

---

## Release gate (mandatory)

**Do not release** (staging or production) until the following gate is satisfied:

1. **Green Phase 12A** — Full test suite run and all critical suites green.
2. **Test summary report** — Report generated from evidence and retained.
3. **Sign-off** — When gap remediation applies, product/tech lead sign-off obtained.

In short: **Green Phase 12A + test summary report + sign-off** is the gate before release.

---

## How to satisfy the gate

### 1. Green Phase 12A

Run the full Phase 12A suite (backend unit/integration/E2E, frontend unit/E2E, security, performance, concurrency, regression):

```bash
./scripts/run_phase_12a_full_suites.sh
```

- Use the same suite every time so release is consistent. See [TEST_EXECUTION_PLAN.md](TEST_EXECUTION_PLAN.md) and [RUNBOOKS.md — Full test suite (Phase 12A-style)](RUNBOOKS.md#full-test-suite-phase-12a-style).
- If any suite fails, fix at **root cause** (no mocks/stubs; no masking). Re-run until green.

### 2. Test summary report

Generate the report from the evidence collected by the Phase 12A run:

```bash
./scripts/generate_test_summary_report.sh YYYY-MM-DD
```

- Evidence lives under `test_reports_comprehensive/{date}/`. The report summarizes pass/fail, duration, coverage, and evidence links. See [EVIDENCE_COLLECTION_PLAN.md](EVIDENCE_COLLECTION_PLAN.md).

### 3. Sign-off

When **gap remediation** applies (e.g. [gapfix1](../openspec/changes/gapfix1/tasks.md), [testreview1](../openspec/changes/testreview1/tasks.md) Phase 16):

- Complete [RUNBOOKS.md — Gap remediation validation](RUNBOOKS.md#gap-remediation-validation).
- Product/tech lead confirms documentation and implementation; gap items resolved or deferred as planned; evidence and report location recorded.
- **Release MUST NOT proceed** until sign-off is obtained. See [GAP_REMEDIATION_PLAN.md §11](../openspec/changes/testreview1/GAP_REMEDIATION_PLAN.md).

---

## Related documentation

- [RUNBOOKS.md — Deployment and rollback](RUNBOOKS.md#deployment-and-rollback): Deploy only after green Phase 12A + sign-off.
- [RUNBOOKS.md — Gap remediation validation](RUNBOOKS.md#gap-remediation-validation): Steps and sign-off.
- [DOCKER_COMPOSE_DEPLOYMENT.md](DOCKER_COMPOSE_DEPLOYMENT.md): Release gate (Step 0), deployment steps, rollback.

# Asset-creation saga — mutation testing methodology

**Phase**: 250.1.B.5
**Status**: Authoritative
**Owners**: Asset-Creation Eng + SRE on-call (nightly triage)
**Companion CI**: [.github/workflows/mutmut-asset-saga.yml](../../.github/workflows/mutmut-asset-saga.yml)

## Purpose

Mutation testing introduces small bytecode-level mutations into source ([`hub/apps/orchestration/workflows/asset_activation_saga.py`](../../hub/apps/orchestration/workflows/asset_activation_saga.py)) and runs the existing test suite against each mutant. A mutant that the test suite KILLS (causes a test failure) is healthy — the test suite caught the regression. A mutant that SURVIVES is an actionable gap: the test suite did not detect the change.

Survived mutants are tech-debt signals. They indicate either:
1. **Missing test coverage** — a behaviour the saga expresses but no test asserts.
2. **Equivalent mutation** — a transformation that produces semantically-identical code (e.g. `x > 0` → `x >= 1` for integer `x`). These are NOT actionable; we mark them as "equivalent" in the triage process.
3. **Untestable code** — code reachable only via runtime conditions impossible to reproduce in tests (e.g. specific OS / kernel / Redis-version branches). These are documented + tagged.

## When the workflow runs

- **Nightly at 04:00 UTC** via `cron` schedule. CI runners are off-peak; the ~20 min runtime doesn't compete with PR CI.
- **On-demand** via `workflow_dispatch` (any team member can trigger a run for a specific branch).
- **NOT on PR** — mutation testing is too slow + noisy for blocking gates per the lineage-validator precedent ([.github/workflows/mutmut-lineage-validator.yml](../../.github/workflows/mutmut-lineage-validator.yml)).

## Test runner used by mutmut

The mutmut config (CLI args in the workflow YAML) drives:

```
python -m pytest hub/apps/orchestration/workflows/tests/test_asset_activation_saga.py \
                 hub/apps/orchestration/workflows/tests/test_asset_creation_workflow_property.py \
                 -x -q --no-header
```

The two test files together exercise:
- **Unit-level saga tests** — happy-path step ordering + each compensation function in isolation.
- **Phase 250.1.B.4 property test** — Hypothesis-driven random failure injection at every step + saga compensation invariants (INV-1 through INV-5).

`pytest -x` (fail-fast) is used so mutmut detects mutant kills quickly. The property test's `max_examples=50` per shape is sufficient — runs in ~5s per mutant on a healthy CI runner.

## Triage workflow (for survived mutants)

When the nightly workflow surfaces survived mutants, the on-call SRE creates a tracking issue per survived-mutants count:

1. **`mutmut show <mutant_id>`** — view the mutant diff.
2. **Classify**:
   - **A — actionable test gap**: write a test that kills the mutant. File a Phase 250.1.B sub-task.
   - **B — equivalent mutation**: append the mutant id to `tests/mutmut-equivalents-asset-saga.txt` (NEW per this runbook) with a one-line justification. Future runs skip these.
   - **C — untestable**: append to `tests/mutmut-untestable-asset-saga.txt` with the reason (e.g. "requires Redis cluster mode; unit tests are single-node").
3. **For Class A**: TDD — write the killing test first; verify it kills the mutant locally via `mutmut kill <mutant_id>`; commit.

Healthy steady-state: <5 survived mutants, all Class B/C with documented justifications.

## Local development

To run mutmut locally without waiting for the nightly:

```bash
pip install mutmut hypothesis pytest pytest-django
mutmut run \
  --paths-to-mutate=hub/apps/orchestration/workflows/asset_activation_saga.py \
  --tests-dir=hub/apps/orchestration/workflows/tests \
  --runner='python -m pytest hub/apps/orchestration/workflows/tests/test_asset_activation_saga.py hub/apps/orchestration/workflows/tests/test_asset_creation_workflow_property.py -x -q --no-header' \
  --no-backup
mutmut results
mutmut show <mutant_id>     # inspect a specific mutant diff
```

Expected runtime: ~15-20 minutes for ~330 LOC of saga code. Coffee.

## Why this matters for fail-closed

The Phase 250.1.A workflow re-sequence depends on saga compensation correctness. A subtle mutation that:
- Reverses two compensation steps (running step-3 compensation before step-4 compensation),
- Skips a compensation function on a specific exception type,
- Returns success-without-actually-compensating,

...would create orphan rows in production. The unit + property tests assert the invariants; mutation testing verifies the assertions actually catch regressions. Without it, we ship correct-looking-but-fragile compensation logic.

## Related deliverables

- [hub/apps/orchestration/workflows/asset_activation_saga.py](../../hub/apps/orchestration/workflows/asset_activation_saga.py) — the saga module under mutation.
- [hub/apps/orchestration/workflows/tests/test_asset_activation_saga.py](../../hub/apps/orchestration/workflows/tests/test_asset_activation_saga.py) — unit tests.
- [hub/apps/orchestration/workflows/tests/test_asset_creation_workflow_property.py](../../hub/apps/orchestration/workflows/tests/test_asset_creation_workflow_property.py) — Phase 250.1.B.4 property test.
- [docs/adr/asset-creation/ADR-AST-001-fail-closed-asset-persistence.md](../adr/asset-creation/ADR-AST-001-fail-closed-asset-persistence.md) — the design rationale being verified.

## Quarterly review

Track mutation-testing trends quarterly:
- Total mutants generated.
- Killed / Survived / Equivalent / Untestable counts.
- Trend of Class A discoveries (rising → test suite is gradually weakening; falling → discipline is paying off).

The numbers feed into the Phase 250 closeout audit-pass DoD evidence per Phase-240 precedent.

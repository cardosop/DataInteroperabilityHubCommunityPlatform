# Traceability Architecture

**Last Updated**: 2026-06-17 | **Phase**: 312.5  
**Purpose**: Single-page reference for the documentation-test traceability system.

---

## Overview

The Meshant platform maintains bidirectional traceability between documented user journeys/use cases and test code across 10 layers. Eight CI gates and two pre-commit hooks enforce consistency. Three marker types link tests to documentation.

```
┌──────────────────────────────────────────────────────────────────┐
│                    DOCUMENTATION REGISTRIES                        │
│  docs/USER_JOURNEYS.md  ←→  docs/USE_CASES.md                    │
│  docs/CRITICAL_UC_JOURNEY_IDS.yaml (CI gate subset)              │
│  docs/mvpdocs/_meta/persona-mapping.yaml                         │
│  docs/mvpdocs/_meta/persona-journey-mapping.yaml                 │
└──────────────────────────┬───────────────────────────────────────┘
                           │ bidirectional sync (CI GATE-27, GATE-28)
                           ▼
┌──────────────────────────────────────────────────────────────────┐
│                     TEST MARKER LAYERS                             │
│  @pytest.mark.journey("JOURNEY-XXX")  ← 73 distinct IDs          │
│  @pytest.mark.uc("UC-XXX")            ← 57 distinct IDs          │
│  @pytest.mark.persona("Persona Name") ← 13 personas              │
│  frontend/e2e/journeys/**/JOURNEY-*.spec.ts ← 149 filename IDs   │
└──────────────────────────────────────────────────────────────────┘
```

---

## Marker Types

| Marker | Format | Example | Where Used | Count |
|--------|--------|---------|-----------|-------|
| `journey` | `JOURNEY-{PERSONA}-{NNN}` | `JOURNEY-DPO-001` | `tests/e2e/`, `hub/apps/*/tests/` | 73 |
| `uc` | `UC-{DOMAIN}-{NNN}` | `UC-AUTH-001` | `tests/e2e/`, `tests/integration/`, `hub/apps/*/tests/` | 57 |
| `persona` | Free text | `"Data Product Owner"` | `tests/e2e/test_persona_*.py` | 13 |
| (filename) | `JOURNEY-{PERSONA}-{NNN}.spec.ts` | `JOURNEY-DPO-001.spec.ts` | `frontend/e2e/journeys/` | 149 |

All markers are registered in `pytest.ini` and validated by `scripts/check_marker_consistency.py`.

---

## Documentation Registries

| Registry | Path | Content | Canonical? |
|----------|------|---------|-----------|
| User Journey Index | `docs/USER_JOURNEYS.md` | 149 journeys across 13 personas | ✅ Yes |
| Use Case Index | `docs/USE_CASES.md` | 95 use cases across 12 domains | ✅ Yes |
| Critical ID Registry | `docs/CRITICAL_UC_JOURNEY_IDS.yaml` | 37 UC + 28 journey CI-gate-critical IDs | ✅ Yes |
| Persona Mapping | `docs/mvpdocs/_meta/persona-mapping.yaml` | 13 fixture personas → 6 canonical personas | ✅ Yes |
| Persona-Journey Mapping | `docs/mvpdocs/_meta/persona-journey-mapping.yaml` | Persona → journey ID list | Planned (Phase 5) |

**Deprecated** (retained for historical reference only):
- `docs/deprecated-doc/product-originals/USER_JOURNEYS.md`
- `docs/deprecated-doc/product-originals/USE_CASES.md`

---

## CI Enforcement Gates

| Gate | Script | What It Checks | Severity |
|------|--------|---------------|----------|
| GATE-01 | `check_assert_true_true.py` | Zero `assertTrue(True)` stubs | BLOCKING |
| GATE-17 | `check_marker_consistency.py` | All markers registered in `pytest.ini` | BLOCKING |
| GATE-18 | `spec_coverage_report.py` | Spec coverage baseline | WARNING |
| GATE-26 | `lint_journey_marker_coverage.py --blocking` | Critical journeys have markers | BLOCKING (post 2026-06-21) |
| GATE-27 | `check_doc_journey_marker_sync.py --ci-mode` | Bidirectional journey doc↔marker sync | BLOCKING (critical) / WARNING |
| GATE-28 | `check_doc_uc_marker_sync.py --ci-mode` | Bidirectional UC doc↔marker sync | BLOCKING (critical) / WARNING |
| — | `check_persona_mapping_drift.py` | Persona fixture consistency | BLOCKING |
| — | `report_uc_journey_test_coverage.py --ci-mode` | CI gate coverage report | BLOCKING (threshold) |

All gates use `continue-on-error: ${{ inputs.warn-only }}` for a one-week tuning period after introduction.

---

## Pre-commit Hooks

| Hook | Trigger | What It Validates |
|------|---------|-----------------|
| `check-journey-doc-sync` | Changes to `USER_JOURNEYS.md` or test files | Journey docs ↔ markers |
| `check-uc-doc-sync` | Changes to `USE_CASES.md` or test files | UC docs ↔ markers |

---

## Test Layers and Scan Coverage

| Layer | Path | Journey Coverage | UC Coverage | Scanned By |
|-------|------|-----------------|-------------|-----------|
| Backend E2E | `tests/e2e/` | ✅ 73 markers | ✅ 57 markers | GATE-26, 27, 28 |
| Backend Integration | `tests/integration/` | ❌ 0 | ✅ Some | GATE-28 |
| Django App Tests | `hub/apps/*/tests/` | ✅ 6 (transformation) | ✅ 18 | GATE-26, 27, 28 |
| CLI Tests | `cli/tests/use_cases/` | ❌ 0 | ❌ 0 | GAP — Phase 4 |
| SDK Tests | `sdk/python/tests/use_cases/` | ❌ 0 | ❌ 0 | GAP — Phase 4 |
| Service Tests | `services/*/tests/` | ❌ 0 | ❌ 0 | GAP — Phase 4 |
| Performance Tests | `tests/performance/` | ❌ 0 | ❌ 0 | GAP — P3 deferred |
| Security Tests | `tests/security/` | ❌ 0 | ❌ 0 | GAP — P3 deferred |
| Load Tests | `tests/load/` | ❌ (internal names) | ❌ 0 | GAP — Phase 4 |
| Chaos/Resilience | `tests/chaos/`, `tests/resilience/` | ❌ 0 | ❌ 0 | GAP — P3 deferred |
| Frontend E2E | `frontend/e2e/journeys/` | ✅ 149 (filename) | ✅ 27 (filename) | GATE-27, 28 |

---

## Sync Script Behavior

### `check_doc_journey_marker_sync.py`
1. **Forward**: Every JOURNEY-XXX in `USER_JOURNEYS.md` must have ≥1 marker OR frontend spec
2. **Reverse**: Every `@pytest.mark.journey("JOURNEY-XXX")` must have a doc entry
3. **Critical**: Every JOURNEY-XXX in `CRITICAL_UC_JOURNEY_IDS.yaml` must be in docs
4. **Frontend**: Every `JOURNEY-*.spec.ts` filename must have a doc entry
5. **Duplicate**: No duplicate journey IDs in docs

### `check_doc_uc_marker_sync.py`
Same five checks for UC-XXX IDs.

---

## Makefile Targets

| Target | What It Runs |
|--------|-------------|
| `make test-ci-lint` | Ruff + `check_assert_true_true` + `check_persona_mapping_drift` + `lint_journey_marker_coverage` |
| `make check-docs-sync` | Both bidirectional sync scripts + persona mapping drift |
| `make audit-docs` | All of the above + marker consistency + CI gate coverage report |

---

## How to Add a New Journey (End-to-End)

1. **Document** — Add entry to `docs/USER_JOURNEYS.md` in the correct persona table.
2. **Backend test** — Add `@pytest.mark.journey("JOURNEY-NEW-001")` to the relevant test method.
3. **Frontend test** — Create `frontend/e2e/journeys/<persona>/JOURNEY-NEW-001.spec.ts`.
4. **Persona aggregator** — Import the new spec in `frontend/e2e/personas/<persona>.spec.ts`.
5. **Critical?** — Add to `docs/CRITICAL_UC_JOURNEY_IDS.yaml` if CI-gate-critical.
6. **Verify** — Run `make audit-docs` before merge. All gates must pass.

---

## How to Add a New Use Case (End-to-End)

1. **Document** — Add entry to `docs/USE_CASES.md` in the correct domain table.
2. **Backend test** — Add `@pytest.mark.uc("UC-NEW-001")` to the relevant test method.
3. **Frontend test** — Create `frontend/e2e/use-cases/<domain>/UC-NEW-001.spec.ts` (optional).
4. **Critical?** — Add to `docs/CRITICAL_UC_JOURNEY_IDS.yaml` if CI-gate-critical.
5. **Verify** — Run `make audit-docs` before merge.

---

## Script Inventory

| Script | Purpose | Phase |
|--------|---------|-------|
| `scripts/check_assert_true_true.py` | Detect `assertTrue(True)` stubs | 285.14.6.7 |
| `scripts/check_marker_consistency.py` | Validate pytest marker registration | 312.7 |
| `scripts/check_persona_mapping_drift.py` | Verify persona fixture consistency | 217.0.4 |
| `scripts/lint_journey_marker_coverage.py` | Critical journey → marker coverage | TR.L.4 |
| `scripts/report_uc_journey_test_coverage.py` | CI gate coverage report | Traceability CI Gate |
| `scripts/check_doc_journey_marker_sync.py` | Bidirectional journey sync | 312.5.5 |
| `scripts/check_doc_uc_marker_sync.py` | Bidirectional UC sync | 312.5.6 |
| `scripts/extract_persona_journey_mapping.py` | Extract persona→journey from frontend | Planned (Phase 5) |
| `scripts/check_persona_journey_mapping_drift.py` | Verify persona-journey mapping | Planned (Phase 5) |
| `scripts/spec_coverage_report.py` | Spec coverage reporting | Existing |

---

**Last reviewed**: 2026-06-17 | **Next review**: 2026-09-17

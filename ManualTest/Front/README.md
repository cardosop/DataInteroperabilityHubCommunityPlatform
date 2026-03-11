# QA Manual Test Tutorial — Frontend

**Version**: 1.0.0  
**Last Updated**: 2026-03-06  
**Status**: Active

---

## Overview

This manual test tutorial provides step-by-step scripts for QA engineers to execute manual tests against the Data Interoperability Hub frontend. It mirrors the automated E2E coverage: **~114 use cases**, **97 user journeys**, and **13 personas**.

**Principles**:
- **Real backend only** — No mocks or stubs
- **Traceability** — Each script links to use cases, journeys, personas, and E2E specs
- **Reproducibility** — Prerequisites, data, and steps are explicit

---

## Quick Start

1. **Prerequisites**: Complete [00-PREREQUISITES.md](00-PREREQUISITES.md)
2. **Support Material**: Use [05-SUPPORT-MATERIAL/](05-SUPPORT-MATERIAL/) — contracts (ODCS/ODPS), sample data (CSV/JSON), test users
3. **Execution**: Follow [01-TEST-EXECUTION-SCRIPT.md](01-TEST-EXECUTION-SCRIPT.md) in order
4. **Step-by-step scripts**: Auth journeys in [03-USER-JOURNEYS/auth/](03-USER-JOURNEYS/auth/); DPO journeys in [03-USER-JOURNEYS/dpo/](03-USER-JOURNEYS/dpo/)

---

## Directory Structure

```
ManualTest/Front/
├── README.md                    # This file
├── 00-PREREQUISITES.md         # Environment, users, backend setup
├── 01-TEST-EXECUTION-SCRIPT.md # Master execution script (ordered)
├── 02-USE-CASES/               # Use case manual tests (~109)
├── 03-USER-JOURNEYS/           # Journey-based manual tests (96)
├── 04-PERSONAS/                # Persona-focused test suites (13)
├── 05-SUPPORT-MATERIAL/        # Test users, ODCS/ODPS contracts, sample CSV/JSON data
├── 06-CHECKLISTS/              # Smoke, alternate flows, release sign-off
│   ├── smoke-test.md
│   ├── alternate-flows.md
│   └── release-sign-off.md
└── 07-TRACEABILITY/            # UC/Journey/Persona → script mapping
    └── README.md
```

---

## Coverage Summary

| Dimension | Count | Status |
|-----------|-------|--------|
| Use Cases | ~114 | 5 auth scripts in 02-USE-CASES/; rest via persona scripts |
| User Journeys | 97 | 5 auth scripts in 03-USER-JOURNEYS/auth/; rest via persona scripts |
| Personas | 13 | See 04-PERSONAS/ |
| Deferred (Transformation Pipeline) | 6 | Documented in index |

---

## Resource Pickers (UX)

Flows that select assets, contracts, datasets, or files use **searchable pickers** (AssetPicker, ContractPicker, DatasetPicker, FilePicker) instead of manual UUID entry. Affected journeys: JOURNEY-DPO-015 (ODPS upload), JOURNEY-DPO-016 (ODPS link), JOURNEY-DPO-018 (dataset edit), JOURNEY-DE-003 (DQ), JOURNEY-CPO-002 (retention), JOURNEY-CPO-004 (compliance), plus asset attach, scheduled export, access request. See [docs/UI/RESOURCE_PICKERS.md](../../docs/UI/RESOURCE_PICKERS.md).

---

## Related Documentation

- [Use Cases](../../docs/USE_CASES.md)
- [User Journeys](../../docs/USER_JOURNEYS.md)
- [User Personas](../../docs/USER_PERSONAS.md)
- [Test Traceability](../../docs/TEST_TRACEABILITY.md)
- [E2E Full Coverage Plan](../../frontend/e2e/E2E_FULL_COVERAGE_PLAN.md)

**Social / Communities (Phase 27)**: Communities route is `/communities`; legacy `/social` redirects to `/communities`. Asset ratings, reviews, and Community section are on the asset detail page (`/assets/:id`). Manual scripts: JOURNEY-CM-001–004, JOURNEY-DC-008, JOURNEY-DC-009, JOURNEY-DPO-009, JOURNEY-DPO-011, JOURNEY-DPO-012.

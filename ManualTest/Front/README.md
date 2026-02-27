# QA Manual Test Tutorial — Frontend

**Version**: 1.0.0  
**Last Updated**: 2026-02-17  
**Status**: Active

---

## Overview

This manual test tutorial provides step-by-step scripts for QA engineers to execute manual tests against the Data Interoperability Hub frontend. It mirrors the automated E2E coverage: **~109 use cases**, **96 user journeys**, and **13 personas**.

**Principles**:
- **Real backend only** — No mocks or stubs
- **Traceability** — Each script links to use cases, journeys, personas, and E2E specs
- **Reproducibility** — Prerequisites, data, and steps are explicit

---

## Quick Start

1. **Prerequisites**: Complete [00-PREREQUISITES.md](00-PREREQUISITES.md)
2. **Execution**: Follow [01-TEST-EXECUTION-SCRIPT.md](01-TEST-EXECUTION-SCRIPT.md) in order
3. **Support Material**: Use [05-SUPPORT-MATERIAL/](05-SUPPORT-MATERIAL/) for credentials, contracts, and sample data

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
├── 05-SUPPORT-MATERIAL/        # Test users, ODPS, contracts, sample data
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
| Use Cases | ~109 | 4 auth scripts in 02-USE-CASES/; rest via persona scripts |
| User Journeys | 96 | 4 auth scripts in 03-USER-JOURNEYS/; rest via persona scripts |
| Personas | 13 | See 04-PERSONAS/ |
| Deferred (Transformation Pipeline) | 6 | Documented in index |

---

## Related Documentation

- [Use Cases](../../docs/USE_CASES.md)
- [User Journeys](../../docs/USER_JOURNEYS.md)
- [User Personas](../../docs/USER_PERSONAS.md)
- [Test Traceability](../../docs/TEST_TRACEABILITY.md)
- [E2E Full Coverage Plan](../../frontend/e2e/E2E_FULL_COVERAGE_PLAN.md)

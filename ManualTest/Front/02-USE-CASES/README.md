# Use Case Scripts

**Version**: 1.1.0  
**Last Updated**: 2026-03-01

---

## Overview

Each use case script maps to a use case in [docs/USE_CASES.md](../../docs/USE_CASES.md). Scripts provide step-by-step manual test instructions with expected results and pass checkboxes.

**Before running**: Complete [00-PREREQUISITES.md](../00-PREREQUISITES.md). Use [05-SUPPORT-MATERIAL/test-users.md](../05-SUPPORT-MATERIAL/test-users.md) for credentials.

**Note**: Five auth use cases (UC-AUTH-001–005) have dedicated scripts. The remaining ~104 use cases are covered via persona scripts (04-PERSONAS/), which reference journeys that implement multiple use cases.

---

## Auth Use Cases

| Use Case | Title | Script |
|----------|-------|--------|
| UC-AUTH-001 | User Registers (Self-Service Sign-Up) | [UC-AUTH-001.md](UC-AUTH-001.md) |
| UC-AUTH-002 | User Logs In | [UC-AUTH-002.md](UC-AUTH-002.md) |
| UC-AUTH-003 | User Resets Password | [UC-AUTH-003.md](UC-AUTH-003.md) |
| UC-AUTH-004 | Unauthenticated User Accesses Public Resources | [UC-AUTH-004.md](UC-AUTH-004.md) |
| UC-AUTH-005 | User Switches Active Tenant | [UC-AUTH-005.md](UC-AUTH-005.md) |

## Dataset and File Use Cases

| Use Case | Title | Script |
|----------|-------|--------|
| UC-DS-EDIT | Edit Dataset and Link to Asset | [UC-DS-EDIT.md](UC-DS-EDIT.md) |
| UC-FILE-UPLOAD | Upload File | [UC-FILE-UPLOAD.md](UC-FILE-UPLOAD.md) |

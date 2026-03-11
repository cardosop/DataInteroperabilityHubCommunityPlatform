# E2E Use Cases

Use case–based E2E tests. Each use case spec maps to one or more UC-* IDs from `docs/USE_CASES.md` and `E2E_FULL_COVERAGE_PLAN.md`.

## Directory Structure

```
use-cases/
├── auth/           # UC-AUTH-001 to UC-AUTH-004 (registration, login, password reset, public access)
├── assets/         # UC-AM-001 (asset management)
├── contracts/      # UC-CM-001, UC-CM-002 (contract management)
├── marketplace/    # UC-MKT-001 to UC-MKT-004 (marketplace publish, browse, purchase, entitlements)
├── dq/             # UC-DQ-001 (data quality)
├── compliance/     # UC-COMP-001 (compliance)
├── odps/           # UC-ODPS-001 to UC-ODPS-003 (ODPS product)
├── integrations/   # UC-INT-001, UC-INT-002 (connectors)
└── webhooks/       # UC-WH-001 (webhook management)
```

## UC → Spec Mapping

| Use Case ID | Title | Spec File | Status |
|-------------|-------|-----------|--------|
| UC-AUTH-001 | User Registers | `auth/UC-AUTH-001.spec.ts` | ✅ Via journeys/auth |
| UC-AUTH-002 | User Logs In | `auth/UC-AUTH-002.spec.ts` | ✅ Via journeys/auth |
| UC-AUTH-003 | User Resets Password | `auth/UC-AUTH-003.spec.ts` | ✅ Via journeys/auth |
| UC-AUTH-004 | Unauthenticated User Accesses Public Resources | `auth/UC-AUTH-004.spec.ts` | ✅ Via journeys/auth |
| — | Accept Invitation (JOURNEY-TA-001) | `auth/accept-invitation.spec.ts` | ✅ Implemented |
| UC-AM-001 | Create Asset via Data-First Flow | `assets/UC-AM-001.spec.ts` | ✅ Phase 29.4.1 |
| UC-CM-001 | Create Contract | `contracts/UC-CM-001.spec.ts` | ✅ Phase 29.4.1 |
| UC-CM-002 | Validate Contract / Link ODPS | `contracts/UC-CM-002.spec.ts` | ✅ Phase 29.4.1 |
| UC-DQ-001 | Run Data Quality Check | `dq/UC-DQ-001.spec.ts` | ✅ Phase 29.4.1 |
| UC-COMP-001 | Run Compliance Scan | `compliance/UC-COMP-001.spec.ts` | ✅ Phase 29.4.1 |
| UC-MKT-001 | Publish Asset to Marketplace | `marketplace/UC-MKT-001.spec.ts` | ✅ Phase 29.4.1 |
| UC-MKT-002 | Browse Marketplace Listings | `marketplace/UC-MKT-002.spec.ts` | ✅ Phase 29.4.1 |
| UC-MKT-003 | Purchase Asset | `marketplace/UC-MKT-003.spec.ts` | ✅ Phase 29.4.1 |
| UC-MKT-004 | Access Entitlements | `marketplace/UC-MKT-004.spec.ts` | ✅ Phase 29.4.1 |
| UC-ODPS-001 | Create ODPS Product | `odps/UC-ODPS-001.spec.ts` | ✅ Phase 29.4.2 |
| UC-ODPS-002 | Link ODPS to Contract | `odps/UC-ODPS-002.spec.ts` | ✅ Phase 29.4.2 |
| UC-ODPS-003 | Export ODPS Product | `odps/UC-ODPS-003.spec.ts` | ✅ Phase 29.4.2 |
| UC-INT-001 | Install Pre-built Connector | `integrations/UC-INT-001.spec.ts` | ✅ Phase 29.4.2 |
| UC-INT-002 | Create Custom Connector | `integrations/UC-INT-002.spec.ts` | ✅ Phase 29.4.2 |
| UC-WH-001 | Create/Manage Webhook | `webhooks/UC-WH-001.spec.ts` | ✅ Phase 29.4.2 |

## Journey vs Use Case

- **Journey specs** (`journeys/*/JOURNEY-*.spec.ts`): End-to-end user flows per persona.
- **Use case specs** (`use-cases/*/UC-*.spec.ts`): Focused tests for a single use case (Success/Failure/Edge).

Use case specs may import from journey specs or fixtures for shared steps.

## Run Commands

```bash
# All use cases
npm run test:e2e -- e2e/use-cases/

# Auth use cases only
npm run test:e2e -- e2e/use-cases/auth/

# Assets use cases only
npm run test:e2e -- e2e/use-cases/assets/
```

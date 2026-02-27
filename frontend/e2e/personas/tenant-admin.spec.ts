/**
 * Persona Aggregator: Tenant Admin
 * Imports and runs all TA journey specs (JOURNEY-TA-001 through TA-008)
 * and JOURNEY-MP-001 (Connect to External Marketplace; per MARKETPLACE_USER_JOURNEYS.md MP-001 persona is DPO+TA).
 * Run: npm run test:e2e -- e2e/personas/tenant-admin.spec.ts
 * Reference: E2E_FULL_COVERAGE_PLAN.md
 */

import '../journeys/ta/JOURNEY-TA-001.spec';
import '../journeys/ta/JOURNEY-TA-002.spec';
import '../journeys/ta/JOURNEY-TA-003.spec';
import '../journeys/ta/JOURNEY-TA-004.spec';
import '../journeys/ta/JOURNEY-TA-005.spec';
import '../journeys/ta/JOURNEY-TA-006.spec';
import '../journeys/ta/JOURNEY-TA-007.spec';
import '../journeys/ta/JOURNEY-TA-008.spec';
import '../journeys/marketplace/JOURNEY-MP-001.spec';

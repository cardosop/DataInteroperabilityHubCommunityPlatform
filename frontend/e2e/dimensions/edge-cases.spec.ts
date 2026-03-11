/**
 * Dimension: Edge Cases
 * Aggregates journey specs that verify boundary conditions.
 * Per E2E_FULL_COVERAGE_PLAN: Empty/null, min/max values, special chars, pagination.
 * Phase 29.4.4: Real tests in cross-cutting/edge-cases-tests.spec.ts (runnable; dimensions in testIgnore).
 * Run: npm run test:e2e -- e2e/cross-cutting/edge-cases-tests.spec.ts
 * No mocks/stubs; real backend only.
 */

import '../cross-cutting/edge-cases-tests.spec';
import '../journeys/auth/JOURNEY-AUTH-001.spec';
import '../journeys/auth/JOURNEY-AUTH-002.spec';
import '../journeys/auth/JOURNEY-AUTH-003.spec';
import '../journeys/auth/JOURNEY-AUTH-004.spec';
import '../cross-cutting/404-403-session.spec';
import '../personas/data-product-owner.spec';
import '../personas/data-engineer.spec';
import '../personas/data-consumer.spec';
import '../personas/tenant-admin.spec';
import '../personas/platform-admin.spec';
import '../personas/compliance-officer.spec';
import '../personas/external-developer.spec';
import '../personas/auditor.spec';
import '../personas/data-scientist.spec';
import '../personas/data-analyst.spec';
import '../personas/community-manager.spec';
import '../personas/data-mesh-domain-owner.spec';
import '../journeys/governance-retention/governance-retention-crud.spec';
import '../journeys/contracts-odps/contracts-odps-routes.spec';
import '../journeys/marketplace-dc/marketplace-dc-routes.spec';
import '../journeys/dq-compliance-governance/dq-compliance-governance-routes.spec';

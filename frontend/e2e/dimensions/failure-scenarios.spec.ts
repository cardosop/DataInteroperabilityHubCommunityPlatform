/**
 * Dimension: Failure Scenarios
 * Aggregates journey specs that verify error handling.
 * Per E2E_FULL_COVERAGE_PLAN: Invalid input, API errors (4xx/5xx), network failures, timeouts.
 * Run: npm run test:e2e -- e2e/dimensions/failure-scenarios.spec.ts
 * No mocks/stubs; real backend only.
 */

import '../journeys/auth/JOURNEY-AUTH-001.spec';
import '../journeys/auth/JOURNEY-AUTH-002.spec';
import '../journeys/auth/JOURNEY-AUTH-003.spec';
import '../journeys/auth/JOURNEY-AUTH-004.spec';
import '../journeys/auth/unavailable-403.spec';
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
import '../journeys/admin-audit-settings/admin-audit-settings-routes.spec';
import '../journeys/dq-compliance-governance/dq-compliance-governance-routes.spec';
import '../journeys/integrations-jobs-webhooks/integrations-jobs-webhooks-routes.spec';

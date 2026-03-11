/**
 * Dimension: Happy Paths
 * Aggregates journey specs that verify primary success scenarios.
 * Per E2E_FULL_COVERAGE_PLAN: "Happy path scenarios across all journeys".
 * Phase 29.4.5: Aggregator for use-case happy paths.
 * Run: npm run test:e2e -- e2e/use-cases/ (dimensions in testIgnore; use-cases run directly)
 * No mocks/stubs; real backend only.
 */

import '../use-cases/assets/UC-AM-001.spec';
import '../use-cases/contracts/UC-CM-001.spec';
import '../use-cases/contracts/UC-CM-002.spec';
import '../use-cases/dq/UC-DQ-001.spec';
import '../use-cases/compliance/UC-COMP-001.spec';
import '../use-cases/marketplace/UC-MKT-001.spec';
import '../use-cases/marketplace/UC-MKT-002.spec';
import '../use-cases/marketplace/UC-MKT-003.spec';
import '../use-cases/marketplace/UC-MKT-004.spec';
import '../use-cases/odps/UC-ODPS-001.spec';
import '../use-cases/odps/UC-ODPS-002.spec';
import '../use-cases/odps/UC-ODPS-003.spec';
import '../use-cases/integrations/UC-INT-001.spec';
import '../use-cases/integrations/UC-INT-002.spec';
import '../use-cases/webhooks/UC-WH-001.spec';
import '../login-app-shell.spec';
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
import '../journeys/admin-audit-settings/admin-audit-settings-routes.spec';
import '../journeys/dq-compliance-governance/dq-compliance-governance-routes.spec';
import '../journeys/integrations-jobs-webhooks/integrations-jobs-webhooks-routes.spec';
import '../journeys/mesh-virtualization-search-ai/mesh-search-ai-routes.spec';
import '../journeys/scheduled-export/scheduled-export-journey.spec';
import '../journeys/scheduled-ingestion/scheduled-ingestion-journey.spec';

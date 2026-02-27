/**
 * Persona Aggregator: Visitor / Prospect
 * Imports and runs all auth journey specs (JOURNEY-AUTH-001 through JOURNEY-AUTH-004).
 * Per E2E_FULL_COVERAGE_PLAN: Visitor/Prospect persona (4 auth journeys).
 * Run: npm run test:e2e -- e2e/personas/visitor.spec.ts
 * No mocks/stubs; real backend only.
 */

import '../journeys/auth/JOURNEY-AUTH-001.spec';
import '../journeys/auth/JOURNEY-AUTH-002.spec';
import '../journeys/auth/JOURNEY-AUTH-003.spec';
import '../journeys/auth/JOURNEY-AUTH-004.spec';

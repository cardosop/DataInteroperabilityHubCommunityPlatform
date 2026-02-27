/**
 * E2E Test: JOURNEY-DA-001 — Create Transformation Pipeline (DEFERRED)
 *
 * Journey: Create Transformation Pipeline
 * Persona: Data Analyst
 * Reference: docs/USER_JOURNEYS.md, E2E_TEST_SKIP_DOCUMENTATION.md
 *
 * Deferred: Transformation pipeline backend not implemented.
 * UC-TRANS-001, BACKLOG_TRANSFORMATION_PIPELINE.md
 */

import { test } from '@playwright/test';

test.describe.skip('JOURNEY-DA-001: Create Transformation Pipeline', () => {
  test('transformation pipeline creation — deferred', async () => {
    // Deferred: Transformation pipeline backend not implemented.
    // See: docs/USER_JOURNEYS.md, docs/BACKLOG_TRANSFORMATION_PIPELINE.md, E2E_TEST_SKIP_DOCUMENTATION.md
  });

  test.describe('Failure', () => {
    test.skip('failure scenario — deferred with journey', async () => {
      // When journey is enabled: add ≥1 failure test (validation, auth, or 404).
    });
  });
});

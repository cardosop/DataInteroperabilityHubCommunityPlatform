/**
 * E2E Test: JOURNEY-DC-007 — Create Transformation Pipeline for Data
 *
 * Journey: Create Transformation Pipeline for Data
 * Persona: Data Consumer
 * Reference: docs/USER_JOURNEYS.md
 *
 * Status: DEFERRED — Transformation pipeline backend is not yet implemented.
 * Backlog: docs/BACKLOG_TRANSFORMATION_PIPELINE.md, UC-TRANS-001
 *
 * When the feature ships, implement:
 *   Success: authenticated user creates a pipeline (name, schedule, source/target) → verifies
 *            it appears in the list and can be triggered manually.
 *   Failure: submit with empty name / invalid schedule → validation error stays on form.
 *   Edge:    pipeline creation for a user without DATA_CONSUMER role → 403 or redirect.
 */

import { test } from '@playwright/test';

test.describe.skip('JOURNEY-DC-007: Create Transformation Pipeline for Data (DEFERRED)', () => {
  // All tests in this describe are skipped until UC-TRANS-001 is implemented.
  test.describe('Success', () => {
    test('user creates a transformation pipeline and it appears in the list', async () => {
      // TODO: implement when transformation pipeline backend is shipped.
    });
  });

  test.describe('Failure', () => {
    test('submit with empty pipeline name shows validation error', async () => {
      // TODO: implement when transformation pipeline backend is shipped.
    });

    test('unauthenticated access to pipeline create redirects to login', async () => {
      // TODO: implement when transformation pipeline backend is shipped.
    });
  });

  test.describe('Edge', () => {
    test('pipeline creation for restricted role shows 403 or redirect', async () => {
      // TODO: implement when transformation pipeline backend is shipped.
    });
  });
});

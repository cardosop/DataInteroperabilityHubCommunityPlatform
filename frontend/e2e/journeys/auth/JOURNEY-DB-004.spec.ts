/**
 * E2E Test: JOURNEY-DB-004 — Session Refresh and Expiry Handling
 *
 * Persona: Any (authenticated)
 * Reference: docs/USER_JOURNEYS.md, docs/mvpdocs/journeys/JOURNEY-DB-004.md
 *
 * Real backend: an authenticated user WITHOUT Databricks bindings (the
 * default e2e user) must see NO countdown banner — the banner is driven
 * by the session endpoint's countdown state, which stays inactive when
 * no binding exists.
 */

import { expect, test } from '@playwright/test';
import { getTestUser } from '../../fixtures/auth';
import { loginAndNavigateToRoute } from '../../fixtures/helpers';

test.describe('JOURNEY-DB-004: Session Refresh and Expiry Handling', () => {
  test.setTimeout(120000);

  test.describe('Inactive', () => {
    test('no countdown banner for users without Databricks bindings', async ({
      page,
    }) => {
      const user = await getTestUser();
      await loginAndNavigateToRoute(page, user, '/', {
        timeout: 60000,
      });
      await page.waitForTimeout(2000); // allow the first session poll
      await expect(
        page.getByTestId('databricks-countdown-banner')
      ).not.toBeVisible({ timeout: 5000 });
    });
  });
});

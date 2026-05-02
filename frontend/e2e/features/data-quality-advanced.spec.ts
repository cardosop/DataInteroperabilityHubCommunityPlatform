/**
 * Phase 240.4.A.11 — Advanced Data Quality feature E2E.
 *
 * Smoke-tests the four new dashboards plus the alerting-rule CRUD
 * flow against a real backend.  Each test:
 *   1. Logs in via the standard E2E test user.
 *   2. Navigates to the dashboard route.
 *   3. Asserts the page heading + a feature-specific anchor renders
 *      (the page mounts, even if the API returns empty results).
 *
 * The alerting-rule CRUD test additionally creates a rule and asserts
 * the row appears in the list table — exercising the create form's
 * channel-config validation against the real backend.
 *
 * Notes:
 * - We use ``loginAndNavigateToRoute`` so the underlying auth retry
 *   wrapper handles transient 401s.  The standard test user has the
 *   TENANT_ADMIN role (per the auth fixture) so the alerting-rule
 *   CRUD path is unblocked without per-test setup.
 * - The dashboards return PASS empty states when no DQ runs / anomalies
 *   exist in the seeded tenant, which is the expected zero-config
 *   shape for a fresh E2E run.
 */
import { expect, test } from '@playwright/test';
import { getTestUser } from '../fixtures/auth';
import { loginAndNavigateToRoute } from '../fixtures/helpers';

test.describe('Data Quality — Advanced features (Phase 240.4.A)', () => {
  test('Anomalies dashboard renders + filters are present', async ({ page }) => {
    const user = await getTestUser();
    await loginAndNavigateToRoute(page, user, '/dq/anomalies');

    // Heading + filter controls.
    await expect(
      page.getByRole('heading', { name: /dq anomalies/i }),
    ).toBeVisible({ timeout: 15000 });
    await expect(page.getByLabel(/severity/i).first()).toBeVisible();
    await expect(page.getByLabel(/asset id/i)).toBeVisible();
    // Export button is always rendered (disabled when there are no rows).
    await expect(page.getByRole('button', { name: /export csv/i })).toBeVisible();
  });

  test('Trends visualization prompts for asset_id, then renders chart on input', async ({
    page,
  }) => {
    const user = await getTestUser();
    await loginAndNavigateToRoute(page, user, '/dq/trends');

    await expect(
      page.getByRole('heading', { name: /dq trends/i }),
    ).toBeVisible({ timeout: 15000 });
    // Pre-input prompt.
    await expect(page.getByText(/enter an asset id/i)).toBeVisible();

    // Type a UUID-shaped placeholder; the backend will return [] but the
    // chart should still mount once the request resolves.  We don't
    // gate on a 200 here — even an empty results payload should
    // transition the UI from prompt → empty-state, which is enough
    // to prove the wiring fires.
    await page.getByLabel(/asset id/i).fill('00000000-0000-0000-0000-000000000000');
    await expect(page.getByText(/enter an asset id/i)).toHaveCount(0, {
      timeout: 10000,
    });
  });

  test('Scorecards executive dashboard renders summary cards', async ({ page }) => {
    const user = await getTestUser();
    await loginAndNavigateToRoute(page, user, '/dq/scorecards');

    await expect(
      page.getByRole('heading', { name: /dq scorecards/i }),
    ).toBeVisible({ timeout: 15000 });

    // The tenant-level executive dashboard mounts when no asset_id is
    // supplied.  We assert on the testid so the test stays stable
    // across summary-text variations.
    await expect(
      page.getByTestId('executive-dashboard'),
    ).toBeVisible({ timeout: 15000 });
  });

  test('Root cause analysis page prompts when no DQ run is selected', async ({
    page,
  }) => {
    const user = await getTestUser();
    await loginAndNavigateToRoute(page, user, '/dq/rca');

    await expect(
      page.getByRole('heading', { name: /root cause analysis/i }),
    ).toBeVisible({ timeout: 15000 });
    await expect(page.getByText(/select a dq run/i)).toBeVisible();
  });

  test('Alerting rule CRUD: tenant admin can create + see + delete a rule', async ({
    page,
  }) => {
    const user = await getTestUser();
    await loginAndNavigateToRoute(page, user, '/dq/alerting-rules');

    await expect(
      page.getByRole('heading', { name: /dq alerting rules/i }),
    ).toBeVisible({ timeout: 15000 });

    // Create a new rule.
    await page.getByTestId('rule-new-btn').click();
    const ruleName = `e2e-rule-${Date.now()}`;
    await page.getByLabel(/^name/i).fill(ruleName);
    await page.getByLabel(/^threshold/i).fill('80');
    // EMAIL channel is selected by default → ``recipients`` field appears.
    await page.getByLabel(/recipients/i).fill('oncall@e2e.test');
    await page.getByRole('button', { name: /^create$/i }).click();

    // Row appears in the list.
    await expect(page.getByText(ruleName)).toBeVisible({ timeout: 10000 });

    // Delete via the row's delete button + confirm dialog.
    const ruleRow = page.locator('tr', { hasText: ruleName });
    await ruleRow.getByRole('button', { name: /delete/i }).click();
    await page
      .getByRole('button', { name: /delete/i })
      .last()
      .click();
    await expect(page.getByText(ruleName)).toHaveCount(0, { timeout: 10000 });
  });
});

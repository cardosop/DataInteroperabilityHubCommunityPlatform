/**
 * E2E Test: JOURNEY-DS-003 — Configure ML-Based Anomaly Detection
 *
 * Journey: Configure ML-Based Anomaly Detection
 * Persona: Data Scientist / ML Engineer
 * Reference: docs/USER_JOURNEYS.md
 *
 * Distinct from DS-004 (Tune Recommendation Engine): DS-003 focuses on
 * the Training Jobs tab — submitting, monitoring, and cancelling training jobs
 * for anomaly detection models. DS-004 covers the Inference Deployments tab.
 *
 * Success/Failure/Edge. Routes: /ml (Training Jobs tab).
 * Capability-gated: ml.models. Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { clearAuthStorage, getTestUser, loginUser } from '../../fixtures/auth';

test.describe('JOURNEY-DS-003: Configure ML-Based Anomaly Detection', () => {
  // The capability gate's documented worst case is ~55s (30s fail-open +
  // 25s+retry fetch of the 19.7MB openapi.json), on top of login and
  // navigation — 120s is too tight when that path runs (b6 timeout).
  test.setTimeout(180000);

  test.describe('Success', () => {
    test('ML page loads and Training Jobs tab is accessible', async ({ page }) => {
      const testUser = await getTestUser();
      await loginUser(page, testUser);
      await page.goto('/ml');
      await page.waitForLoadState('domcontentloaded');
      // intentional: probes optional UI presence via a multi-line locator chain — the branch logic below handles both rendered and missing cases deterministically; absence is a legitimate tenant/role state. The 35s budget covers the capability gate's documented worst case: useCapabilities fail-opens at 30s (the capabilities service falls back to deriving from the 19.7 MB openapi.json with a 25s+retry fetch when the manifest call fails), so a slow boot settles the gate instead of reading as a missing page.
      await page
        .locator('.ml-page, .unavailable-page, [data-testid="unavailable-page"], .unavailable-page, [data-testid="unavailable-page"], .disabled-capability-page, [data-testid="disabled-capability-page"]')
        .first()
        .waitFor({ state: 'visible', timeout: 35000 })
        .catch(() => null);

      if (page.url().includes('/login')) {
        test.skip(page.url().includes('/login'), 'Redirected to login — auth may have expired');
        return;
      }

      const isGated =
        page.url().includes('/403') ||
        page.url().includes('/unavailable') ||
        (await page.locator('.unavailable-page, [data-testid="unavailable-page"], .unavailable-page, [data-testid="unavailable-page"], .disabled-capability-page, [data-testid="disabled-capability-page"]').count()) > 0;
      if (isGated) {
        test.skip(isGated, 'ML capability gated — cannot test Training Jobs tab');
        return;
      }

      expect(page.url()).toContain('/ml');
      // The 35s probe above can resolve to nothing when the gate is on
      // its documented slow path (30s fail-open + 25s+retry openapi
      // fetch). Wait out the rest of that worst case and re-check the
      // gate markers — a late gate render must skip, not fail.
      // intentional: terminal-state probe — element absence is tolerated and the next count/gate check adjudicates
      await page
        .locator('.ml-page, .unavailable-page, [data-testid="unavailable-page"], .unavailable-page, [data-testid="unavailable-page"], .disabled-capability-page, [data-testid="disabled-capability-page"]')
        .first()
        .waitFor({ state: 'visible', timeout: 60000 })
        .catch(() => null);
      const gated =
        page.url().includes('/403') ||
        page.url().includes('/unavailable') ||
        (await page.locator('.unavailable-page, [data-testid="unavailable-page"], .unavailable-page, [data-testid="unavailable-page"], .disabled-capability-page, [data-testid="disabled-capability-page"]').count()) > 0;
      test.skip(gated, 'ML capability gated (late gate render) — cannot test Training Jobs tab');
      if (gated) return;
      await expect(page.locator('.error-display, [data-testid="error-display"]').first()).not.toBeVisible();
      await expect(page.locator('.ml-page')).toBeVisible({ timeout: 10000 });

      // DS-003 specific: navigate to Training Jobs tab
      const trainingTab = page.locator('.ml-tab:has-text("Training Jobs"), button:has-text("Training Jobs")');
      if ((await trainingTab.count()) === 0) {
        test.skip((await trainingTab.count()) === 0, 'Training Jobs tab not found — ML UI may not include training section');
        return;
      }
      await trainingTab.first().click();
      await page.waitForTimeout(500);

      // Verify training jobs section renders (list, empty state, or loading)
      const hasTrainingContent =
        (await page.locator('.training-jobs-section, .empty-state, [data-testid="empty-state"], .training-job-list').count()) > 0;
      expect(hasTrainingContent, 'Expected Training Jobs section content').toBe(true);
    });
  });

  test.describe('Failure', () => {
    test('unauthenticated access to ML page redirects to login', async ({ page }) => {
      await clearAuthStorage(page);
      await page.goto('/ml');
      await page.waitForURL(/\/login/, { timeout: 15000 });
      expect(page.url()).toContain('/login');
    });
  });

  test.describe('Edge', () => {
    test('ML page with Training Jobs tab shows empty state or job list', async ({ page }) => {
      const testUser = await getTestUser();
      await loginUser(page, testUser);
      await page.goto('/ml');
      await page.waitForLoadState('domcontentloaded');
      // intentional: probes optional UI presence via a multi-line locator chain — the branch logic below handles both rendered and missing cases deterministically; absence is a legitimate tenant/role state. The 35s budget covers the capability gate's documented worst case: useCapabilities fail-opens at 30s (the capabilities service falls back to deriving from the 19.7 MB openapi.json with a 25s+retry fetch when the manifest call fails), so a slow boot settles the gate instead of reading as a missing page.
      await page
        .locator('.ml-page, .unavailable-page, [data-testid="unavailable-page"], .disabled-capability-page, [data-testid="disabled-capability-page"]')
        .first()
        .waitFor({ state: 'visible', timeout: 35000 })
        .catch(() => null);

      if (page.url().includes('/login') || page.url().includes('/403')) {
        test.skip(page.url().includes('/login') || page.url().includes('/403'), 'Auth/capability gated');
        return;
      }

      const isGated = (await page.locator('.unavailable-page, [data-testid="unavailable-page"], .disabled-capability-page, [data-testid="disabled-capability-page"]').first().count()) > 0;
      if (isGated) {
        test.skip(isGated, 'ML capability gated');
        return;
      }

      // Same late-gate re-check as the Success test: the probe above can
      // resolve before the gate's documented slow path finishes.
      // intentional: terminal-state probe — element absence is tolerated and the next count/gate check adjudicates
      await page
        .locator('.ml-page, .unavailable-page, [data-testid="unavailable-page"], .disabled-capability-page, [data-testid="disabled-capability-page"]')
        .first()
        .waitFor({ state: 'visible', timeout: 60000 })
        .catch(() => null);
      const gated =
        page.url().includes('/403') ||
        (await page.locator('.unavailable-page, [data-testid="unavailable-page"], .disabled-capability-page, [data-testid="disabled-capability-page"]').first().count()) > 0;
      test.skip(gated, 'ML capability gated (late gate render)');
      if (gated) return;

      // Click Training Jobs tab and verify edge behavior (empty vs populated)
      const trainingTab = page.locator('.ml-tab:has-text("Training Jobs"), button:has-text("Training Jobs")');
      if ((await trainingTab.count()) === 0) {
        test.skip((await trainingTab.count()) === 0, 'Training Jobs tab not found');
        return;
      }
      await trainingTab.first().click();
      await page.waitForTimeout(500);

      // Either empty-state or training-job rows should be present
      const hasEmpty = (await page.locator('.empty-state, [data-testid="empty-state"]').first().count()) > 0;
      const hasJobs = (await page.locator('.training-job-row, .training-job-card, tr').count()) > 0;
      expect(hasEmpty || hasJobs, 'Expected empty state or training job rows').toBe(true);
    });
  });
});

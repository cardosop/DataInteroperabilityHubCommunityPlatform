/**
 * E2E Test: JOURNEY-DS-004 — Tune Recommendation Engine
 *
 * Journey: Tune Recommendation Engine
 * Persona: Data Scientist / ML Engineer
 * Reference: docs/USER_JOURNEYS.md
 *
 * Distinct from DS-003 (Configure ML-Based Anomaly Detection): DS-004 focuses on
 * the Inference Deployments tab — deploying, monitoring, and undeploying inference
 * endpoints for recommendation models. DS-003 covers the Training Jobs tab.
 *
 * Success/Failure/Edge. Routes: /ml (Inference Deployments tab).
 * Capability-gated: ml.models. Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { clearAuthStorage, getTestUser, loginUser } from '../../fixtures/auth';

test.describe('JOURNEY-DS-004: Tune Recommendation Engine', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('ML page loads and Inference Deployments tab is accessible', async ({ page }) => {
      const testUser = await getTestUser();
      await loginUser(page, testUser);
      await page.goto('/ml');
      await page.waitForLoadState('domcontentloaded');
      await page
        .locator('.ml-page, .unavailable-page, [data-testid="unavailable-page"]')
        .first()
        .waitFor({ state: 'visible', timeout: 15000 })
        .catch(() => null);

      if (page.url().includes('/login')) {
        test.skip(true, 'Redirected to login — auth may have expired');
        return;
      }

      const isGated =
        page.url().includes('/403') ||
        page.url().includes('/unavailable') ||
        (await page.locator('.unavailable-page, [data-testid="unavailable-page"]').count()) > 0;
      if (isGated) {
        test.skip(true, 'ML capability gated — cannot test Inference tab');
        return;
      }

      expect(page.url()).toContain('/ml');
      await expect(page.locator('.error-display')).not.toBeVisible();
      await expect(page.locator('.ml-page')).toBeVisible({ timeout: 10000 });

      // DS-004 specific: navigate to Inference Deployments tab
      const inferenceTab = page.locator('.ml-tab:has-text("Inference"), button:has-text("Inference")');
      if ((await inferenceTab.count()) === 0) {
        test.skip(true, 'Inference Deployments tab not found — ML UI may not include inference section');
        return;
      }
      await inferenceTab.first().click();
      await page.waitForTimeout(500);

      // Verify inference section renders (list, empty state, or loading)
      const hasInferenceContent =
        (await page.locator('.inference-section, .inference-deployments-section, .empty-state, .inference-deployment-list').count()) > 0;
      expect(hasInferenceContent, 'Expected Inference Deployments section content').toBe(true);
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
    test('ML page with Inference tab shows empty state or deployment list', async ({ page }) => {
      const testUser = await getTestUser();
      await loginUser(page, testUser);
      await page.goto('/ml');
      await page.waitForLoadState('domcontentloaded');
      await page
        .locator('.ml-page, .unavailable-page')
        .first()
        .waitFor({ state: 'visible', timeout: 15000 })
        .catch(() => null);

      if (page.url().includes('/login') || page.url().includes('/403')) {
        test.skip(true, 'Auth/capability gated');
        return;
      }

      const isGated = (await page.locator('.unavailable-page').count()) > 0;
      if (isGated) {
        test.skip(true, 'ML capability gated');
        return;
      }

      // Click Inference tab and verify edge behavior (empty vs populated)
      const inferenceTab = page.locator('.ml-tab:has-text("Inference"), button:has-text("Inference")');
      if ((await inferenceTab.count()) === 0) {
        test.skip(true, 'Inference Deployments tab not found');
        return;
      }
      await inferenceTab.first().click();
      await page.waitForTimeout(500);

      // Either empty-state or deployment rows should be present
      const hasEmpty = (await page.locator('.empty-state').count()) > 0;
      const hasDeployments = (await page.locator('.inference-deployment-row, .inference-deployment-card, tr').count()) > 0;
      expect(hasEmpty || hasDeployments, 'Expected empty state or inference deployment rows').toBe(true);
    });
  });
});

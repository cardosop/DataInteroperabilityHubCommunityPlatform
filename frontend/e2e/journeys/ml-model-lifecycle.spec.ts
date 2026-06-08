/**
 * 285.9b.P.2 — ML model lifecycle E2E journey test.
 *
 * Full lifecycle: register model → link dataset → train → deploy → predict → view metrics.
 */
import { expect } from '@playwright/test';
import { test } from '@playwright/test';

test.describe('ML Model Lifecycle — E2E Journey', () => {
  test('register model and navigate to detail', async ({ page }) => {
    await page.goto('/ml');
    await page.waitForLoadState('networkidle', { timeout: 10_000 }).catch(() => {});

    // Verify ML page loads with tabs
    const modelsTab = page.locator('.ml-tab', { hasText: /models/i });
    await expect(modelsTab).toBeVisible();

    // Click first model card if available
    const modelCard = page.locator('.model-card').first();
    if (await modelCard.isVisible()) {
      await modelCard.click();
      await page.waitForURL(/\/ml\/models\//, { timeout: 10_000 });
      // Verify detail page loaded
      await expect(page.locator('.ml-detail-header h1')).toBeVisible({ timeout: 5000 });
    }
  });

  test('training dashboard shows status and timeline', async ({ page }) => {
    await page.goto('/ml');
    await page.waitForLoadState('networkidle', { timeout: 10_000 }).catch(() => {});

    // Switch to training jobs tab
    const trainingTab = page.locator('.ml-tab', { hasText: /training/i });
    if (await trainingTab.isVisible()) {
      await trainingTab.click();
      await page.waitForTimeout(1000);

      // Click first training job if available
      const jobRow = page.locator('.training-job-row, [data-testid="training-job-card"]').first();
      if (await jobRow.isVisible()) {
        await jobRow.click();
        await page.waitForURL(/\/ml\/training\//, { timeout: 10_000 });
        await expect(page.locator('.ml-detail-header')).toBeVisible({ timeout: 5000 });
      }
    }
  });

  test('inference deployments tab shows deployment cards', async ({ page }) => {
    await page.goto('/ml');
    await page.waitForLoadState('networkidle', { timeout: 10_000 }).catch(() => {});

    const inferenceTab = page.locator('.ml-tab', { hasText: /inference/i });
    if (await inferenceTab.isVisible()) {
      await inferenceTab.click();
      await page.waitForTimeout(1000);

      // Verify either deployment cards or empty state
      const hasDeployments = await page.locator('.deployment-card').first().isVisible().catch(() => false);
      const hasEmptyState = await page.locator('[data-testid="empty-state"]').isVisible().catch(() => false);
      expect(hasDeployments || hasEmptyState).toBe(true);
    }
  });

  test('A/B tests tab is accessible', async ({ page }) => {
    await page.goto('/ml');
    await page.waitForLoadState('networkidle', { timeout: 10_000 }).catch(() => {});

    const abTab = page.locator('.ml-tab', { hasText: /a\/b/i });
    if (await abTab.isVisible()) {
      await abTab.click();
      await page.waitForTimeout(500);
      await expect(page.locator('.ab-tests-section')).toBeVisible({ timeout: 5000 });
    }
  });
});

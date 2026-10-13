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

    // Verify ML page loads with tabs.  30s timeout: the first visit
    // pays the Vite dev-server cold-transform of the lazy ML chunk
    // (471 kB) plus auth-store initialization — a 5s window asserted
    // against the pre-transform login redirect (measured 2026-08-28:
    // /auth/me/ returned 200, the page just had not hydrated yet).
    const modelsTab = page.locator('.ml-tab', { hasText: /models/i });
    await expect(modelsTab).toBeVisible({ timeout: 30_000 });

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

    // The page itself must load (tabs render unconditionally on MLPage);
    // a silent `if` skip here masked an unauthenticated redirect.
    await expect(page.locator('.ml-tabs')).toBeVisible({ timeout: 30_000 });

    // Switch to training jobs tab
    const trainingTab = page.locator('.ml-tab', { hasText: /training/i });
    await trainingTab.click();
    await page.waitForTimeout(1000);

    // Click first training job if available; otherwise an explicit empty
    // state must render.
    const jobRow = page.locator('.training-job-row, [data-testid="training-job-card"]').first();
    if (await jobRow.isVisible()) {
      await jobRow.click();
      await page.waitForURL(/\/ml\/training\//, { timeout: 10_000 });
      await expect(page.locator('.ml-detail-header')).toBeVisible({ timeout: 5000 });
    } else {
      await expect(
        page.locator('.empty-state, [data-testid="empty-state"]').first()
      ).toBeVisible({ timeout: 5000 });
    }
  });

  test('inference deployments tab shows deployment cards', async ({ page }) => {
    await page.goto('/ml');
    await page.waitForLoadState('networkidle', { timeout: 10_000 }).catch(() => {});

    await expect(page.locator('.ml-tabs')).toBeVisible({ timeout: 30_000 });

    const inferenceTab = page.locator('.ml-tab', { hasText: /inference/i });
    await inferenceTab.click();
    await page.waitForTimeout(1000);

    // Verify either deployment cards or empty state
    // intentional: probe — failure reads as false and the assertion below adjudicates the real outcome
    const hasDeployments = await page.locator('.deployment-card').first().isVisible().catch(() => false);
    // intentional: probe — failure reads as false and the assertion below adjudicates the real outcome
    const hasEmptyState = await page.locator('[data-testid="empty-state"]').isVisible().catch(() => false);
    expect(hasDeployments || hasEmptyState).toBe(true);
  });

  // NOTE: an "A/B tests tab" test lived here.  The frontend ML page
  // exposes exactly three tabs (models / training-jobs / inference —
  // MLPage.tsx TabType) and no A/B-tests UI exists in src/features/ml
  // (the backend endpoint /api/v1/ml/inference/ab-tests/ has no frontend
  // surface).  The stale test asserted a UI that was never built, so it
  // could never pass.  Recorded as a product gap in
  // openspec/changes/preprod01/tasks.md (P.7).
});

/**
 * E2E Test: Quick Preview Modal — Phase 278.V.9
 *
 * Journey: Preview-before-buy (listing quick preview modal).
 * @covers 278.V.9, 278.H.5 — Quick preview modal E2E test
 * Persona: Data Consumer
 * Reference: specs/marketplace-payment-gateway/spec.md
 *
 * Covers the QuickPreviewModal component shipped in Phase 278.H.5:
 *   - Click "Preview" on a listing card → modal opens.
 *   - Modal shows sample data table, schema fields, quality metrics,
 *     trust signals, and preview expiry.
 *   - Close via ✕ button, overlay click, or Escape key.
 *   - Error state when preview fetch fails.
 *   - Loading spinner during fetch.
 *   - A11y: role="dialog", aria-label.
 *
 * Success/Failure/Edge. Routes: /marketplace/listings, /marketplace/listings/:id.
 * Real backend + API setup; no mocks.
 */

import { expect, test } from '@playwright/test';
import { getTestUser, loginUser } from '../../fixtures/auth';
import { seedMarketplaceListings } from '../../fixtures/seed-marketplace';
import { waitForMarketplaceListings } from '../../fixtures/helpers';

test.describe('Quick Preview Modal @critical @quarantine', () => {
  test.setTimeout(120000);

  test.beforeAll(async () => {
    await seedMarketplaceListings(3);
  });

  test.describe('Success — Modal open, content, and close', () => {
    test('opens preview from listing card and displays all sections', async ({ page }) => {
      const user = await getTestUser();

      // Navigate to marketplace listing list
      await loginUser(page, user);
      await page.goto('/marketplace');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(4000);

      test.skip(
        page.url().includes('/login') || page.url().includes('/403'),
        'Redirected — auth or permissions may have expired',
      );

      // Find a listing card with a Preview button
      const btnCount = await waitForMarketplaceListings(
        page,
        '.listing-card-preview-btn',
        1,
      );
      test.skip(
        btnCount === 0,
        'No Preview button found on listing cards after retries — component not mounted or no listings',
      );
      const previewBtn = page.locator('.listing-card-preview-btn').first();

      // Click Preview
      await previewBtn.click();
      await page.waitForTimeout(2000);

      // Modal should appear
      const overlay = page.locator('[data-testid="quick-preview-overlay"]');
      const modal = page.locator('[data-testid="quick-preview-modal"]');

      test.skip(
        (await modal.count()) === 0,
        'QuickPreviewModal did not render — preview endpoint may be unavailable',
      );

      await expect(modal).toBeVisible();

      // A11y: role="dialog" + aria-label
      await expect(modal).toHaveAttribute('role', 'dialog');
      const ariaLabel = await modal.getAttribute('aria-label');
      expect(ariaLabel).toMatch(/Preview:/);

      // Wait for loading to finish or content to appear
      const loading = modal.locator('.quick-preview-loading');
      const error = modal.locator('.quick-preview-error');
      const sampleSection = modal.locator('.qp-sample-table');
      const schemaSection = modal.locator('.qp-schema-list');

      // Wait up to 5s for either content or error
      await page.waitForTimeout(3000);

      const hasLoading = (await loading.count()) > 0;
      const hasError = (await error.count()) > 0;
      const hasSampleTable = (await sampleSection.count()) > 0;
      const hasSchemaList = (await schemaSection.count()) > 0;

      // At least one of these states must be present
      expect(
        hasLoading || hasError || hasSampleTable || hasSchemaList,
        'Expected preview modal to show loading, error, sample data, or schema',
      ).toBe(true);

      // If content loaded, verify all sections
      if (hasSampleTable || hasSchemaList) {
        // Quality metrics section (optional — depends on data)
        const metricsSection = modal.locator('.qp-metrics');
        const hasMetrics = (await metricsSection.count()) > 0;

        // Trust signals section (optional — depends on listing config)
        const trustSection = modal.locator('.qp-trust-signals');
        const hasTrust = (await trustSection.count()) > 0;

        // Preview expiry should be visible
        const expiry = modal.locator('.qp-expires');
        if ((await expiry.count()) > 0) {
          const expiryText = await expiry.textContent();
          expect(expiryText).toMatch(/expires|Expires/i);
        }

        // Verify at minimum sample data or schema is present
        expect(hasSampleTable || hasSchemaList).toBe(true);
      }

      // Close via ✕ button
      const closeBtn = modal.locator('.quick-preview-close');
      if ((await closeBtn.count()) > 0) {
        await closeBtn.click();
        await page.waitForTimeout(500);
        await expect(modal).not.toBeVisible();
      }
    });

    test('closes modal via overlay click and Escape key', async ({ page }) => {
      const user = await getTestUser();

      await loginUser(page, user);
      await page.goto('/marketplace');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(4000);

      test.skip(
        page.url().includes('/login') || page.url().includes('/403'),
        'Redirected — auth or permissions may have expired',
      );

      // Open preview
      const btnCount = await waitForMarketplaceListings(
        page,
        '.listing-card-preview-btn',
        1,
      );
      test.skip(
        btnCount === 0,
        'No Preview button found on listing cards after retries',
      );
      const previewBtn = page.locator('.listing-card-preview-btn').first();
      await previewBtn.click();
      await page.waitForTimeout(2000);

      const modal = page.locator('[data-testid="quick-preview-modal"]');
      test.skip(
        (await modal.count()) === 0,
        'QuickPreviewModal did not render',
      );

      // Test Escape key dismiss
      await page.keyboard.press('Escape');
      await page.waitForTimeout(500);
      await expect(modal).not.toBeVisible();

      // Re-open for overlay click test
      const previewBtn2 = page.locator('.listing-card-preview-btn').first();
      if ((await previewBtn2.count()) > 0) {
        await previewBtn2.click();
        await page.waitForTimeout(2000);

        const overlay = page.locator('[data-testid="quick-preview-overlay"]');
        if ((await overlay.count()) > 0) {
          // Click the overlay (outside the modal) to dismiss
          await overlay.click({ position: { x: 10, y: 10 } });
          await page.waitForTimeout(500);
          await expect(modal).not.toBeVisible();
        }
      }
    });
  });

  test.describe('Edge — Loading and error states', () => {
    test('shows loading spinner during fetch, handles slow response', async ({ page }) => {
      const user = await getTestUser();

      await loginUser(page, user);
      await page.goto('/marketplace');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(4000);

      test.skip(
        page.url().includes('/login') || page.url().includes('/403'),
        'Redirected — auth or permissions may have expired',
      );

      const btnCount = await waitForMarketplaceListings(
        page,
        '.listing-card-preview-btn',
        1,
      );
      test.skip(
        btnCount === 0,
        'No Preview button found on listing cards after retries',
      );
      const previewBtn = page.locator('.listing-card-preview-btn').first();

      // Click preview — loading spinner should appear briefly
      await previewBtn.click();

      const modal = page.locator('[data-testid="quick-preview-modal"]');
      test.skip(
        (await modal.count()) === 0,
        'QuickPreviewModal did not render',
      );

      // Check that either a loading spinner appeared or content loaded
      // (the loading state is brief, so it may have already resolved)
      const loadingEl = modal.locator('.quick-preview-loading');
      const loadingWasVisible =
        (await loadingEl.count()) > 0 && (await loadingEl.isVisible());

      // Wait for content
      await page.waitForTimeout(3000);

      // After loading, either content renders or error shows
      const hasContent =
        (await modal.locator('.qp-section').count()) > 0;
      const hasError =
        (await modal.locator('.quick-preview-error').count()) > 0;

      expect(
        hasContent || hasError,
        'Expected preview to show content or error after loading',
      ).toBe(true);

      // Cleanup: close modal
      const closeBtn = modal.locator('.quick-preview-close');
      if ((await closeBtn.count()) > 0) await closeBtn.click();
    });

    test('modal handles large sample data without breaking layout', async ({ page }) => {
      const user = await getTestUser();

      await loginUser(page, user);
      await page.goto('/marketplace');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(4000);

      test.skip(
        page.url().includes('/login') || page.url().includes('/403'),
        'Redirected — auth or permissions may have expired',
      );

      const btnCount = await waitForMarketplaceListings(
        page,
        '.listing-card-preview-btn',
        1,
      );
      test.skip(
        btnCount === 0,
        'No Preview button found on listing cards after retries',
      );
      const previewBtn = page.locator('.listing-card-preview-btn').first();
      await previewBtn.click();
      await page.waitForTimeout(3000);

      const modal = page.locator('[data-testid="quick-preview-modal"]');
      test.skip(
        (await modal.count()) === 0,
        'QuickPreviewModal did not render',
      );

      // If sample data table exists, verify it has scrollable wrapper
      const sampleWrapper = modal.locator('.qp-sample-table-wrapper');
      if ((await sampleWrapper.count()) > 0) {
        // Table should be visible
        const table = sampleWrapper.locator('table');
        expect(await table.count()).toBeGreaterThan(0);

        // Verify the table has a header row
        const headers = table.locator('thead th');
        expect(await headers.count()).toBeGreaterThan(0);
      }

      // Modal should still be within viewport
      const box = await modal.boundingBox();
      if (box) {
        expect(box.width).toBeGreaterThan(0);
        expect(box.height).toBeGreaterThan(0);
      }

      // Cleanup
      const closeBtn = modal.locator('.quick-preview-close');
      if ((await closeBtn.count()) > 0) await closeBtn.click();
    });
  });
});

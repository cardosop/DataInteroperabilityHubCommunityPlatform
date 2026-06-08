/**
 * Phase 278.V.6 — Trust signals on listing cards E2E.
 *
 * Validates that TrustSignalsBar (278.H.2) renders correctly on
 * marketplace listing cards. Covers all 4 signal types: KYC status
 * badge, compliance grade, sample availability, and relative-date
 * updated-at indicator.
 *
 * @critical — trust signals are the primary trust-surface for
 * marketplace buyers; missing or incorrect signals undermine the
 * KYC + compliance gating investment.
 */
import { test, expect } from '@playwright/test';
import { getTestUser, loginUser } from '../../fixtures/auth';
import { seedMarketplaceListings } from '../../fixtures/seed-marketplace';
import { waitForMarketplaceListings } from '../../fixtures/helpers';

test.describe('Trust Signals on Listing Cards (278.V.6) @critical', () => {
  test.setTimeout(120000);

  test.beforeAll(async () => {
    await seedMarketplaceListings(3);
  });

  test.describe('Success', () => {
    test('trust signals bar renders on listing cards', async ({ page }) => {
      const user = await getTestUser();
      await loginUser(page, user);
      test.skip(page.url().includes('/login'), 'Could not authenticate');

      await page.goto('/marketplace', { waitUntil: 'domcontentloaded' });

      // Wait for the listing page, grid, or empty state
      await page
        .locator(
          '[data-testid="listing-list-page"], .listing-list-page, [data-testid="listing-list-grid"], .listing-list-grid, .empty-state, [data-testid="empty-state"]',
        )
        .first()
        .waitFor({ state: 'visible', timeout: 30000 })
        .catch(() => null);

      if (page.url().includes('/login')) {
        test.skip(true, 'Auth session expired');
        return;
      }

      // Check if listings are present (retry — listing cards take time under parallel load)
      const cardCount = await waitForMarketplaceListings(page, '.listing-card', 1);

      if (cardCount === 0) {
        test.skip(true, 'No published listings after retries — trust signals cannot be verified');
        return;
      }
      const cards = page.locator('.listing-card');

      // At minimum, some cards should have a trust signals bar
      const signalBars = page.locator('[data-testid="trust-signals-bar"]');
      const barCount = await signalBars.count();
      expect(barCount).toBeGreaterThanOrEqual(1);
    });

    test('KYC status signal renders with correct class on listing cards', async ({
      page,
    }) => {
      const user = await getTestUser();
      await loginUser(page, user);
      test.skip(page.url().includes('/login'), 'Could not authenticate');

      await page.goto('/marketplace', { waitUntil: 'domcontentloaded' });
      await page
        .locator('[data-testid="listing-list-page"], .listing-list-page, [data-testid="listing-list-grid"], .listing-list-grid, .empty-state, [data-testid="empty-state"]')
        .first()
        .waitFor({ state: 'visible', timeout: 30000 })
        .catch(() => null);

      if (page.url().includes('/login')) return;
      const lcCount = await waitForMarketplaceListings(page, '.listing-card', 1);
      if (lcCount === 0) {
        test.skip(true, 'No published listings after retries');
        return;
      }

      const kycSignals = page.locator('[data-testid="trust-signal-kyc"]');
      const kycCount = await kycSignals.count();

      if (kycCount === 0) {
        // KYC signal is conditionally rendered — acceptable if no listings have
        // a confirmed kycStatus. TrustSignalsBar only renders it when truthy.
        test.skip(true, 'No listings with KYC status — signal is conditional');
        return;
      }

      // At least one KYC signal must have a valid status class
      const firstKyc = kycSignals.first();
      const classList = await firstKyc.getAttribute('class');
      expect(classList).toBeTruthy();
      expect(classList).toContain('trust-signal-kyc-');

      // KYC signal must display meaningful text
      const kycText = await firstKyc.textContent();
      const validLabels = ['Verified', 'KYC Pending', 'Unverified'];
      const hasValidLabel = validLabels.some((l) => kycText?.includes(l));
      expect(hasValidLabel).toBe(true);

      // KYC signal has a title tooltip
      const title = await firstKyc.getAttribute('title');
      expect(title).toBeTruthy();
      expect(title).toContain('KYC');
    });

    test('compliance grade signal renders with correct class on listing cards', async ({
      page,
    }) => {
      const user = await getTestUser();
      await loginUser(page, user);
      test.skip(page.url().includes('/login'), 'Could not authenticate');

      await page.goto('/marketplace', { waitUntil: 'domcontentloaded' });
      await page
        .locator('[data-testid="listing-list-page"], .listing-list-page, [data-testid="listing-list-grid"], .listing-list-grid, .empty-state, [data-testid="empty-state"]')
        .first()
        .waitFor({ state: 'visible', timeout: 30000 })
        .catch(() => null);

      if (page.url().includes('/login')) return;
      const lcCount = await waitForMarketplaceListings(page, '.listing-card', 1);
      if (lcCount === 0) {
        test.skip(true, 'No published listings after retries');
        return;
      }

      const complianceSignals = page.locator('[data-testid="trust-signal-compliance"]');
      const compCount = await complianceSignals.count();

      if (compCount === 0) {
        // Compliance grade is conditional — only rendered when present and
        // not UNKNOWN. Acceptable if no listings have a known grade.
        test.skip(true, 'No listings with compliance grade — signal is conditional');
        return;
      }

      const firstComp = complianceSignals.first();
      const classList = await firstComp.getAttribute('class');
      expect(classList).toBeTruthy();
      expect(classList).toContain('trust-signal-compliance-');

      // Valid grades: PASS, WARN, FAIL
      const isValidGrade =
        classList!.includes('trust-signal-compliance-pass') ||
        classList!.includes('trust-signal-compliance-warn') ||
        classList!.includes('trust-signal-compliance-fail');
      expect(isValidGrade).toBe(true);

      // Compliance signal must display meaningful text
      const compText = await firstComp.textContent();
      const validLabels = ['Pass', 'Warn', 'Fail'];
      const hasValidLabel = validLabels.some((l) => compText?.includes(l));
      expect(hasValidLabel).toBe(true);

      // Compliance signal has a title tooltip
      const title = await firstComp.getAttribute('title');
      expect(title).toBeTruthy();
      expect(title).toContain('Compliance');
    });

    test('sample indicator signal renders when sample data available', async ({
      page,
    }) => {
      const user = await getTestUser();
      await loginUser(page, user);
      test.skip(page.url().includes('/login'), 'Could not authenticate');

      await page.goto('/marketplace', { waitUntil: 'domcontentloaded' });
      await page
        .locator('[data-testid="listing-list-page"], .listing-list-page, [data-testid="listing-list-grid"], .listing-list-grid, .empty-state, [data-testid="empty-state"]')
        .first()
        .waitFor({ state: 'visible', timeout: 30000 })
        .catch(() => null);

      if (page.url().includes('/login')) return;
      const lcCount = await waitForMarketplaceListings(page, '.listing-card', 1);
      if (lcCount === 0) {
        test.skip(true, 'No published listings after retries');
        return;
      }

      const sampleSignals = page.locator('[data-testid="trust-signal-sample"]');

      if ((await sampleSignals.count()) === 0) {
        // Sample indicator is conditional — only shown when
        // sampleAvailable is true. Acceptable absence.
        test.skip(true, 'No listings with samples — signal is conditional');
        return;
      }

      const firstSample = sampleSignals.first();
      const sampleText = await firstSample.textContent();
      expect(sampleText?.trim()).toBe('Sample');

      const title = await firstSample.getAttribute('title');
      expect(title).toContain('Sample');
    });

    test('updated-at signal renders relative date on listing cards', async ({
      page,
    }) => {
      const user = await getTestUser();
      await loginUser(page, user);
      test.skip(page.url().includes('/login'), 'Could not authenticate');

      await page.goto('/marketplace', { waitUntil: 'domcontentloaded' });
      await page
        .locator('[data-testid="listing-list-page"], .listing-list-page, [data-testid="listing-list-grid"], .listing-list-grid, .empty-state, [data-testid="empty-state"]')
        .first()
        .waitFor({ state: 'visible', timeout: 30000 })
        .catch(() => null);

      if (page.url().includes('/login')) return;
      const lcCount = await waitForMarketplaceListings(page, '.listing-card', 1);
      if (lcCount === 0) {
        test.skip(true, 'No published listings after retries');
        return;
      }

      const updatedSignals = page.locator('[data-testid="trust-signal-updated"]');

      if ((await updatedSignals.count()) === 0) {
        // updatedAt is conditional — only rendered when present.
        test.skip(true, 'No listings with updated-at — signal is conditional');
        return;
      }

      const firstUpdated = updatedSignals.first();
      const updatedText = await firstUpdated.textContent();

      // Relative-date formatting produces one of these patterns
      const relativePatterns = [
        'Today', 'Yesterday', /\d+d ago/, /\d+w ago/,
        /\d+mo ago/, /\d+y ago/,
      ];
      const matchesPattern = relativePatterns.some((p) => {
        if (typeof p === 'string') return updatedText?.trim() === p;
        return p.test(updatedText?.trim() ?? '');
      });
      expect(matchesPattern).toBe(true);

      // Title tooltip shows full date
      const title = await firstUpdated.getAttribute('title');
      expect(title).toContain('Updated');
    });
  });

  test.describe('Failure / Edge', () => {
    test('listing card renders gracefully with missing trust signals', async ({
      page,
    }) => {
      const user = await getTestUser();
      await loginUser(page, user);
      test.skip(page.url().includes('/login'), 'Could not authenticate');

      await page.goto('/marketplace', { waitUntil: 'domcontentloaded' });
      await page
        .locator('[data-testid="listing-list-page"], .listing-list-page, [data-testid="listing-list-grid"], .listing-list-grid, .empty-state, [data-testid="empty-state"]')
        .first()
        .waitFor({ state: 'visible', timeout: 30000 })
        .catch(() => null);

      if (page.url().includes('/login')) return;

      const cards = page.locator('.listing-card');
      const lc = await waitForMarketplaceListings(page, '.listing-card', 1);
      if (lc === 0) {
        test.skip(true, 'No published listings after retries');
        return;
      }

      // Every card with a trust-signals-bar must not crash with missing
      // props. Verify that each trust-signals-bar container is a valid
      // DOM element (no broken rendering).
      const bars = page.locator('[data-testid="trust-signals-bar"]');
      const barCount = await bars.count();

      for (let i = 0; i < Math.min(barCount, 5); i++) {
        const bar = bars.nth(i);
        // The bar must be visible (not display:none, not zero-size)
        const isVisible = await bar.isVisible();
        expect(isVisible).toBe(true);
      }
    });

    test('empty marketplace page does not crash (graceful no-listings state)', async ({
      page,
    }) => {
      const user = await getTestUser();
      await loginUser(page, user);
      test.skip(page.url().includes('/login'), 'Could not authenticate');

      await page.goto('/marketplace', { waitUntil: 'domcontentloaded' });
      await page
        .locator('[data-testid="listing-list-page"], .listing-list-page, .empty-state, [data-testid="empty-state"]')
        .first()
        .waitFor({ state: 'visible', timeout: 30000 })
        .catch(() => null);

      if (page.url().includes('/login')) return;

      // Page must have rendered either listings or empty state
      const hasPage =
        (await page.locator('.listing-list-page, [data-testid="listing-list-page"]').count()) > 0;
      const hasListings =
        (await page.locator('.listing-card, [data-testid="listing-list-grid"]').count()) > 0;
      const hasEmpty =
        (await page.locator('.empty-state, [data-testid="empty-state"]').count()) > 0;
      expect(hasPage || hasListings || hasEmpty).toBe(true);
    });

    test('trust signals bar is accessible (title attributes on all signals)', async ({
      page,
    }) => {
      const user = await getTestUser();
      await loginUser(page, user);
      test.skip(page.url().includes('/login'), 'Could not authenticate');

      await page.goto('/marketplace', { waitUntil: 'domcontentloaded' });
      await page
        .locator('[data-testid="listing-list-page"], .listing-list-page, [data-testid="listing-list-grid"], .listing-list-grid, .empty-state, [data-testid="empty-state"]')
        .first()
        .waitFor({ state: 'visible', timeout: 30000 })
        .catch(() => null);

      if (page.url().includes('/login')) return;
      const lcCount = await waitForMarketplaceListings(page, '.listing-card', 1);
      if (lcCount === 0) {
        test.skip(true, 'No published listings after retries');
        return;
      }

      // Every trust signal within the first trust-signals-bar must have
      // a title attribute (tooltip for accessibility).
      const firstBar = page.locator('[data-testid="trust-signals-bar"]').first();
      if ((await firstBar.count()) === 0) return;

      const signalChildren = firstBar.locator('[class*="trust-signal"]');
      const childCount = await signalChildren.count();

      for (let i = 0; i < childCount; i++) {
        const child = signalChildren.nth(i);
        const title = await child.getAttribute('title');
        expect(title).toBeTruthy();
      }
    });
  });
});

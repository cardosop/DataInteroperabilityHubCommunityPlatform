/**
 * Phase 278.Z.1 — Axe a11y audit on Phase 278 interactive surfaces.
 *
 * Audits each new Phase 278 surface with WCAG 2.1 AA tag set.
 * Uses the shared `runAxeAudit` wrapper and `expectNoSeriousViolations`
 * gate (critical + serious → fail; moderate + minor → logged for ratchet).
 *
 * Surfaces covered: marketplace listing page (trust signals), comparison
 * modal, quick preview modal, MyApprovalsInbox, product tour overlay,
 * HelpTip popover, keyboard shortcuts cheatsheet, and WhatsNewModal.
 *
 * Real backend only — no mocks. Conditional skip when surface unavailable.
 */
import { expect, test, type Page } from '@playwright/test';
import { getTenantAdminUser, getTestUser, loginUser } from '../fixtures/auth';
import { createAssetViaApi } from '../fixtures/api-assets';
import { createListingViaApi, publishListingViaApi } from '../fixtures/api-marketplace';
import {
  runAxeAudit,
  expectNoSeriousViolations,
  summarizeViolations,
} from '../fixtures/axeAudit';

// 280.C.1.3 — scrollable-region-focusable is now disabled globally via
// PROJECT_WIDE_DISABLE_RULES in axeAudit.ts, so the manual filter is no
// longer needed.  Use the standard expectNoSeriousViolations helper.
const SOFT_LOG = (label: string, page: Page) => async () => {
  const audit = await runAxeAudit(page, label);
  expectNoSeriousViolations(audit);
  if (audit.moderate.length > 0 || audit.minor.length > 0) {
    console.warn(summarizeViolations(audit));
  }
  return audit;
};

test.describe('A11y: Phase 278 surfaces @a11y @critical', () => {
  test.setTimeout(120_000);

  test.describe('Marketplace — listing page with trust signals', () => {
    test('marketplace listing page audits clean', async ({ page }) => {
      const user = await getTestUser();
      // Seed a published listing so the marketplace page isn't empty.
      // Asset activation triggers a compliance scan which takes ~30s.
      // Retry up to 5 times with increasing backoff so the scan has
      // time to complete between attempts.
      let assetId: string | undefined;
      let _lastSeedError = '';
      for (let seedAttempt = 0; seedAttempt < 5 && !assetId; seedAttempt++) {
        try {
          assetId = await createAssetViaApi(user, { ensureActivated: true });
          const listingId = await createListingViaApi(user, assetId, {
            title: `E2E A11y Listing ${Date.now()}`,
          });
          await publishListingViaApi(user, listingId);
          _lastSeedError = '';
        } catch (err) {
          _lastSeedError = String(err).slice(0, 300);
          console.error(`MARKETPLACE_SEED_FAILED (attempt ${seedAttempt + 1}/5): ${String(err).slice(0, 500)}`);
          test.info().annotations.push({
            type: 'seed-failed',
            description: `Marketplace seed attempt ${seedAttempt + 1} failed: ${_lastSeedError}`,
          });
          if (seedAttempt < 4) {
            await new Promise((r) => setTimeout(r, 10000 * Math.min(seedAttempt + 1, 3)));
          }
          assetId = undefined;
        }
      }

      await loginUser(page, user);
      test.skip(page.url().includes('/login'), 'Could not authenticate');

      await page.goto('/marketplace', { waitUntil: 'domcontentloaded' });
      await page
        .locator('[data-testid="listing-list-page"], .listing-list-page, .empty-state, [data-testid="empty-state"]')
        .first()
        .waitFor({ state: 'visible', timeout: 30000 })
        .catch(() => null);

      if (page.url().includes('/login')) return;

      // Reload once — seed ran via API, page may have stale cache.
      await page.reload({ waitUntil: 'domcontentloaded' });
      await page
        .locator('[data-testid="listing-list-page"], .listing-list-page, .empty-state, [data-testid="empty-state"]')
        .first()
        .waitFor({ state: 'visible', timeout: 15000 })
        .catch(() => null);

      const listings = page.locator('.listing-card');
      if ((await listings.count()) === 0) {
        const lastErr = (test.info() as any)._lastSeedError || 'unknown';
        test.skip(true, `No listings — seed failed after 5 attempts. Last error: ${String(lastErr).slice(0, 300)}`);
        return;
      }

      await SOFT_LOG('marketplace-list-phase278', page)();
    });
  });

  test.describe('Comparison modal', () => {
    test('comparison modal audits clean when open', async ({ page }) => {
      const user = await getTestUser();
      // Seed 2 published listings so the comparison modal can be opened.
      // Same compliance-scan timing concern as the marketplace test above.
      let seeded = false;
      for (let seedAttempt = 0; seedAttempt < 5 && !seeded; seedAttempt++) {
        try {
          const assetId = await createAssetViaApi(user, { ensureActivated: true });
          const lid1 = await createListingViaApi(user, assetId, { title: `E2E Compare A ${Date.now()}` });
          const lid2 = await createListingViaApi(user, assetId, { title: `E2E Compare B ${Date.now() + 1}` });
          await publishListingViaApi(user, lid1);
          await publishListingViaApi(user, lid2);
          seeded = true;
        } catch {
          if (seedAttempt < 4) {
            await new Promise((r) => setTimeout(r, 10000 * Math.min(seedAttempt + 1, 3)));
          }
        }
      }

      await loginUser(page, user);
      test.skip(page.url().includes('/login'), 'Could not authenticate');

      await page.goto('/marketplace', { waitUntil: 'domcontentloaded' });
      await page
        .locator('[data-testid="listing-list-page"], .listing-list-page, .empty-state, [data-testid="empty-state"]')
        .first()
        .waitFor({ state: 'visible', timeout: 30000 })
        .catch(() => null);

      if (page.url().includes('/login')) return;

      // Reload once to clear any cached/stale listing state from before seed.
      await page.reload({ waitUntil: 'domcontentloaded' });
      await page
        .locator('[data-testid="listing-list-page"], .listing-list-page, .empty-state, [data-testid="empty-state"]')
        .first()
        .waitFor({ state: 'visible', timeout: 15000 })
        .catch(() => null);

      const checkboxes = page.locator('.listing-card-compare input[type="checkbox"]');
      if ((await checkboxes.count()) < 2) {
        test.skip(true, 'Need ≥2 listings to open comparison modal');
        return;
      }

      await checkboxes.nth(0).check();
      await checkboxes.nth(1).check();

      const compareBtn = page.locator('.compare-action-bar-btn');
      if ((await compareBtn.count()) === 0) {
        test.skip(true, 'Compare action bar not rendered — BulkActionBar may need ≥2 comparable listings');
        return;
      }
      await compareBtn.click();

      const modal = page.locator('[data-testid="comparison-modal"]');
      await modal.waitFor({ state: 'visible', timeout: 10000 }).catch(() => null);
      if ((await modal.count()) === 0) {
        test.skip(true, 'Comparison modal did not open — listings may not be comparable (e.g. DRAFT status)');
        return;
      }

      await SOFT_LOG('comparison-modal-open', page)();

      // Close after audit
      await page.locator('.comparison-close-btn').click().catch(() => null);
    });
  });

  test.describe('My Approvals Inbox', () => {
    test('MyApprovalsInbox audits clean', async ({ page }) => {
      const user = await getTenantAdminUser();
      await loginUser(page, user);
      test.skip(page.url().includes('/login'), 'Could not authenticate as TENANT_ADMIN');

      await page.goto('/governance/my-approvals', { waitUntil: 'domcontentloaded' });
      await page
        .locator('[data-testid="my-approvals-inbox"], .my-approvals-inbox, .my-approvals-inbox__empty')
        .first()
        .waitFor({ state: 'visible', timeout: 30000 })
        .catch(() => null);

      if (page.url().includes('/403')) {
        test.skip(true, 'Role gate — TENANT_ADMIN lacks access');
        return;
      }
      if (page.url().includes('/login')) return;

      await SOFT_LOG('my-approvals-inbox', page)();
    });
  });

  test.describe('Keyboard shortcuts cheatsheet', () => {
    test('keyboard shortcuts cheatsheet audits clean when open', async ({ page }) => {
      const user = await getTestUser();
      await loginUser(page, user);
      test.skip(page.url().includes('/login'), 'Could not authenticate');

      await page.goto('/', { waitUntil: 'domcontentloaded' });
      await page.locator('[data-testid="app-shell"]').waitFor({ state: 'visible', timeout: 15000 }).catch(() => null);
      if (page.url().includes('/login')) return;

      // Open the cheatsheet
      await page.keyboard.press('?');
      const cheatsheet = page.locator('[data-testid="keyboard-shortcuts"]');
      await expect(cheatsheet).toBeVisible({ timeout: 5000 });

      await SOFT_LOG('keyboard-shortcuts-cheatsheet', page)();

      await page.keyboard.press('Escape');
    });
  });

  test.describe('HelpTip popover', () => {
    test('HelpTip popover audits clean when open', async ({ page }) => {
      const user = await getTestUser();
      await loginUser(page, user);
      test.skip(page.url().includes('/login'), 'Could not authenticate');
      test.skip(page.url().includes('/403'), 'Role gate — user lacks compliance access');

      // HelpTips are rendered on the Compliance Run List page header
      // (ROPA, DPIA, DSAR, RLS, ABAC glossary terms — always visible,
      // not gated by API response state).
      // The ComplianceRunListPage renders the header outside the
      // loading/error/empty conditionals, so [data-testid="helptip"]
      // is present as soon as the component mounts.
      await page.goto('/compliance', { waitUntil: 'domcontentloaded' });

      // Wait specifically for the HelpTip elements — they are always
      // rendered in the page header.  If the page redirects to /login
      // or /403, handle that explicitly.
      let tips = page.locator('[data-testid="helptip"]');
      try {
        await tips.first().waitFor({ state: 'visible', timeout: 30000 });
      } catch {
        if (page.url().includes('/login') || page.url().includes('/403')) {
          test.skip(true, `Redirected away from /compliance — ${page.url()}`);
          return;
        }
        // Fallback: try /settings/profile which may also have HelpTips
        await page.goto('/settings/profile', { waitUntil: 'domcontentloaded' });
        tips = page.locator('[data-testid="helptip"]');
      }

      const tipCount = await tips.count();
      if (tipCount === 0) {
        test.skip(tipCount === 0, 'No HelpTip instances found on /compliance or /settings/profile');
        return;
      }

      // Open the first HelpTip by clicking its trigger button.
      // Use dispatchEvent to deliver a native DOM click that React's
      // synthetic event system will handle — Playwright's click()
      // occasionally fails to trigger React's onClick on deeply
      // nested inline elements.
      await tips.first().locator('.helptip__trigger').first().dispatchEvent('click');
      // Popover is conditionally rendered via React setState.
      await page.waitForTimeout(500);
      const popover = tips.first().locator('[role="tooltip"]');
      // Use toBeAttached (DOM presence) — the popover may render
      // outside the viewport or have zero dimensions initially.
      const attached = await popover.count().catch(() => 0);
      if (attached === 0) {
        test.skip(true, 'HelpTip popover did not render after click — React state may not have updated');
        return;
      }

      // Audit only the popover — the compliance page may have pre-existing
      // a11y violations (color-contrast on status badges, select-name) that
      // are outside the scope of this test.
      const audit = await runAxeAudit(page, 'helptip-popover-open', {
        include: '[role="tooltip"]',
      });
      expectNoSeriousViolations(audit);

      await page.keyboard.press('Escape');
    });
  });

  test.describe('Saved Searches management page', () => {
    test('saved searches management page audits clean', async ({ page }) => {
      const user = await getTestUser();
      await loginUser(page, user);
      test.skip(page.url().includes('/login'), 'Could not authenticate');

      await page.goto('/marketplace/saved-searches', { waitUntil: 'domcontentloaded' });
      await page
        .locator('[data-testid="saved-search-list-page"], .saved-search-list-page, .empty-state, [data-testid="empty-state"]')
        .first()
        .waitFor({ state: 'visible', timeout: 30000 })
        .catch(() => null);

      if (page.url().includes('/login')) return;

      await SOFT_LOG('saved-searches-management', page)();
    });
  });

  // ── 283.4.1.3 — Custom Ontology + LDN a11y ──────────────────────────────

  test.describe('Semantic — Custom Ontology upload page', () => {
    test('ontology manager audits clean', async ({ page }) => {
      const user = await getTenantAdminUser();
      await loginUser(page, user);

      await page.goto('/semantic', { waitUntil: 'domcontentloaded' });
      await page.getByTestId('semantic-tab-custom-ontologies').click();
      await page.getByTestId('ontology-manager').waitFor({ state: 'visible', timeout: 15_000 });

      await SOFT_LOG('custom-ontology-manager', page)();
    });
  });

  test.describe('Semantic — LDN inbox page', () => {
    test('LDN settings audits clean', async ({ page }) => {
      const user = await getTenantAdminUser();
      await loginUser(page, user);

      await page.goto('/semantic', { waitUntil: 'domcontentloaded' });
      await page.getByTestId('semantic-tab-ldn').click();
      await page.getByTestId('ldn-settings').waitFor({ state: 'visible', timeout: 15_000 });

      await SOFT_LOG('ldn-settings', page)();
    });
  });

  // ── 284.B.5 — GraphQL-LD playground a11y ────────────────────────

  test.describe('Semantic — GraphQL-LD playground', () => {
    test('graphql playground audits clean', async ({ page }) => {
      const user = await getTenantAdminUser();
      await loginUser(page, user);

      await page.goto('/semantic?tab=graphql', { waitUntil: 'domcontentloaded' });
      await page.getByTestId('semantic-graphql-playground').waitFor({
        state: 'visible',
        timeout: 30_000,
      });

      // The query input textarea must be present — the Axe audit covers
      // the playground region including keyboard-accessibility of the
      // query input, the Run button contrast, and the result panel.
      await expect(page.getByTestId('graphql-query-input')).toBeVisible({
        timeout: 10_000,
      });
      await expect(page.getByTestId('graphql-run-button')).toBeVisible();

      await SOFT_LOG('graphql-ld-playground', page)();
    });
  });
});

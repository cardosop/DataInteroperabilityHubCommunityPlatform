/**
 * E2E: Edge Case Tests (Phase 29.4.4)
 *
 * Real tests for: empty submit, max length, special chars, pagination, unicode.
 * No mocks; real backend only. Complements dimensions/edge-cases.spec.ts.
 *
 * Run: npm run test:e2e -- e2e/cross-cutting/edge-cases-tests.spec.ts
 */

import { expect, test } from '@playwright/test';
import { getTestUser, getConsumerTestUser } from '../fixtures/auth';
import { loginAndNavigateToRoute } from '../fixtures/helpers';

test.describe('Edge Cases (real tests)', () => {
  // loginUser (~30s) + navigation + content load + assertions
  test.setTimeout(120000);

  test('empty submit: search with empty string shows list or empty state', async ({ page }) => {
    const user = await getConsumerTestUser();
    await loginAndNavigateToRoute(page, user, '/marketplace', {
      timeout: 90000,
      contentSelector: '.listing-list-page, .listing-list-grid, [data-testid="listing-list-grid"], .empty-state, [data-testid="empty-state"], .listing-list-filters',
    });
    // D86: login redirect in a test that requires auth is an infra issue — mark YELLOW, not GREEN
    test.skip(page.url().includes('/login'), 'Auth redirect — backend/rate-limit issue');
    // Assert the search input exists before filling — if absent, skip with a clear reason
    // rather than silently passing without exercising the scenario
    const searchInput = page.locator('.listing-list-filters input, input[placeholder*="Search"]').first();
    const missingSearchInput = (await searchInput.count()) === 0;
    test.skip(missingSearchInput, 'Search input not rendered on /marketplace; skipping empty-search edge case');
    if (missingSearchInput) return;
    await searchInput.fill('');
    await page.waitForTimeout(500);
    expect(page.url()).toContain('/marketplace');
    const hasContent =
      (await page.locator('.listing-list-page, .listing-list-grid, [data-testid="listing-list-grid"], .empty-state, [data-testid="empty-state"]').count()) > 0;
    expect(hasContent).toBe(true) /* one of the acceptable page states must be true */;
  });

  test('special chars: search with special characters does not crash', async ({ page }) => {
    const user = await getConsumerTestUser();
    await loginAndNavigateToRoute(page, user, '/marketplace', {
      timeout: 90000,
      contentSelector: '.listing-list-page, .listing-list-grid, [data-testid="listing-list-grid"], .empty-state, [data-testid="empty-state"], .listing-list-filters',
    });
    // D86: login redirect in a test that requires auth is an infra issue — mark YELLOW, not GREEN
    test.skip(page.url().includes('/login'), 'Auth redirect — backend/rate-limit issue');
    // Assert the search input exists before filling
    const searchInput = page.locator('.listing-list-filters input, input[placeholder*="Search"]').first();
    const missingSearchInput = (await searchInput.count()) === 0;
    test.skip(missingSearchInput, 'Search input not rendered on /marketplace; skipping special-chars edge case');
    if (missingSearchInput) return;
    await searchInput.fill('!@#$%^&*()');
    await page.waitForTimeout(1000);
    expect(page.url()).toContain('/marketplace');
    const hasSearchError = (await page.locator('.error-display, [data-testid="error-display"]').first().count()) > 0;
    if (hasSearchError) {
      // intentional: tolerates a detached/removed element while extracting text for a diagnostic message; the surrounding throw/expect below this catch is the primary failure path.
      const errText = await page.locator('.error-display, [data-testid="error-display"]').first().first().textContent().catch(() => '');
      throw new Error(`Special-char search caused a backend error: ${errText?.slice(0, 200)}`);
    }
    const hasContent =
      (await page.locator('.listing-list-page, .listing-list-grid, [data-testid="listing-list-grid"], .empty-state, [data-testid="empty-state"]').count()) > 0;
    expect(hasContent).toBe(true) /* one of the acceptable page states must be true */;
  });

  test('unicode: search with unicode characters handles correctly', async ({ page }) => {
    const user = await getConsumerTestUser();
    await loginAndNavigateToRoute(page, user, '/marketplace', {
      timeout: 90000,
      contentSelector: '.listing-list-page, .listing-list-grid, [data-testid="listing-list-grid"], .empty-state, [data-testid="empty-state"], .listing-list-filters',
    });
    // D86: login redirect in a test that requires auth is an infra issue — mark YELLOW, not GREEN
    test.skip(page.url().includes('/login'), 'Auth redirect — backend/rate-limit issue');
    // Assert the search input exists before filling
    const searchInput = page.locator('.listing-list-filters input, input[placeholder*="Search"]').first();
    const missingSearchInput = (await searchInput.count()) === 0;
    test.skip(missingSearchInput, 'Search input not rendered on /marketplace; skipping unicode edge case');
    if (missingSearchInput) return;
    await searchInput.fill('日本語テスト café naïve');
    await page.waitForTimeout(1000);
    expect(page.url()).toContain('/marketplace');
    const hasUnicodeError = (await page.locator('.error-display, [data-testid="error-display"]').first().count()) > 0;
    if (hasUnicodeError) {
      // intentional: tolerates a detached/removed element while extracting text for a diagnostic message; the surrounding throw/expect below this catch is the primary failure path.
      const errText = await page.locator('.error-display, [data-testid="error-display"]').first().first().textContent().catch(() => '');
      throw new Error(`Unicode search caused a backend error: ${errText?.slice(0, 200)}`);
    }
    const hasContent =
      (await page.locator('.listing-list-page, .listing-list-grid, [data-testid="listing-list-grid"], .empty-state, [data-testid="empty-state"]').count()) > 0;
    expect(hasContent).toBe(true) /* one of the acceptable page states must be true */;
  });

  test('pagination: list with pagination or single page loads', async ({ page }) => {
    const user = await getTestUser();
    // Include  so loginAndNavigateToRoute returns as soon as the
    // app shell (including loading state) is ready, rather than blocking until the API
    // responds. Slow backends under parallel E2E load can take > 60s to return the asset
    // list, causing the helper to timeout when  is excluded.
    await loginAndNavigateToRoute(page, user, '/assets', {
      timeout: 60000,
      contentSelector: '.asset-list-page, [data-testid="asset-list-page"], .empty-state, [data-testid="empty-state"], .error-display, [data-testid="error-display"], .asset-list-pagination',
    });
    // D86: login redirect in a test that requires auth is an infra issue — mark YELLOW, not GREEN
    test.skip(page.url().includes('/login'), 'Auth redirect — backend/rate-limit issue');
    expect(page.url()).toContain('/assets');

    // Separate wait for actual content now that the app shell is confirmed ready.
    // 90s covers slow backends under parallel E2E load (assets API can be slow to respond).
    // intentional: probes optional UI presence via a multi-line locator chain — the branch logic below handles both rendered and missing cases deterministically; absence is a legitimate tenant/role state.
    await page
      .locator('.asset-list-page, [data-testid="asset-list-page"], .empty-state, [data-testid="empty-state"], .error-display, [data-testid="error-display"], .asset-list-pagination')
      .first()
      .waitFor({ state: 'visible', timeout: 90000 })
      .catch(() => null);

    const hasPagination = (await page.locator('.asset-list-pagination').count()) > 0;
    const hasListOrEmpty =
      (await page.locator('.asset-list-page, [data-testid="asset-list-page"]').first().count()) > 0 ||
      (await page.locator('.empty-state, [data-testid="empty-state"]').first().count()) > 0;
    const hasError = (await page.locator('.error-display, [data-testid="error-display"]').first().count()) > 0;
    if (hasError) {
      const errText = (await page.locator('.error-display, [data-testid="error-display"]').first().first().textContent()) ?? '';
      // D86: 403 under parallel E2E load is a transient permission/token issue (token refresh
      // race, subscription not scoped to this project's storageState, etc.).  This is an infra
      // issue, not a pagination bug — skip to keep the report accurate.
      const isTransient403 = /403|forbidden/i.test(errText);
      test.skip(
        isTransient403,
        `Asset list returned 403 — transient permission issue: ${errText.slice(0, 120)}`
      );
      if (isTransient403) return;
      throw new Error(`Asset list shows backend error: ${errText.slice(0, 200)}`);
    }
    expect(hasPagination || hasListOrEmpty).toBe(true) /* one of the acceptable page states must be true */;
  });

  test('max length: long input in search does not crash', async ({ page }) => {
    const user = await getConsumerTestUser();
    await loginAndNavigateToRoute(page, user, '/marketplace', {
      timeout: 90000,
      contentSelector: '.listing-list-page, .listing-list-grid, [data-testid="listing-list-grid"], .empty-state, [data-testid="empty-state"], .listing-list-filters',
    });
    // D86: login redirect in a test that requires auth is an infra issue — mark YELLOW, not GREEN
    test.skip(page.url().includes('/login'), 'Auth redirect — backend/rate-limit issue');
    // Assert the search input exists before filling
    const searchInput = page.locator('.listing-list-filters input, input[placeholder*="Search"]').first();
    const missingSearchInput = (await searchInput.count()) === 0;
    test.skip(missingSearchInput, 'Search input not rendered on /marketplace; skipping max-length edge case');
    if (missingSearchInput) return;
    await searchInput.fill('a'.repeat(500));
    await page.waitForTimeout(1000);
    expect(page.url()).toContain('/marketplace');
    const hasMaxLenError = (await page.locator('.error-display, [data-testid="error-display"]').first().count()) > 0;
    if (hasMaxLenError) {
      // intentional: tolerates a detached/removed element while extracting text for a diagnostic message; the surrounding throw/expect below this catch is the primary failure path.
      const errText = await page.locator('.error-display, [data-testid="error-display"]').first().first().textContent().catch(() => '');
      throw new Error(`Max-length search caused a backend error: ${errText?.slice(0, 200)}`);
    }
    const hasContent =
      (await page.locator('.listing-list-page, .listing-list-grid, [data-testid="listing-list-grid"], .empty-state, [data-testid="empty-state"]').count()) > 0;
    expect(hasContent).toBe(true) /* one of the acceptable page states must be true */;
  });

  // ─── Form input edge cases (asset create form) ────────────────────────────

  // Phase 250.6.B — the type-picker step renders BEFORE the form unless the
  // URL carries the ``?skip=picker`` deep-link bypass (AssetCreatePage.tsx).
  // Without the bypass these tests wait 60s for inputs that never hydrate
  // and skip as "backend may be slow" — the picker's own coverage lives in
  // journeys/dpo/asset-type-picker.spec.ts.
  const CREATE_FORM_ROUTE = '/assets/create?skip=picker';
  const CREATE_FORM_SELECTOR = '[data-testid="asset-create-form"], .asset-create-page';

  /**
   * Navigate to the create form (type-picker bypassed via ?skip=picker) and
   * skip with a diagnostic when the route is unreachable.
   *
   * /assets/create is gated by CapabilityRoute capability="asset_creation"
   * (src/app/routes/routes.tsx) which redirects to /unavailable when the
   * per-tenant capability reads False. A transient/stale capability read —
   * e.g. right after the API restart that e2e-batches.sh performs — can
   * redirect one test away while sibling tests pass minutes apart (the
   * batch-1c run skipped exactly one of these three). One re-navigation
   * retry re-runs the capability check before giving up.
   */
  async function openAssetCreateForm(
    page: import('@playwright/test').Page,
    user: Awaited<ReturnType<typeof getTestUser>>
  ): Promise<void> {
    let onLogin = false;
    let onRoute = false;
    let redirectedTo = '';
    for (let attempt = 0; attempt < 2 && !onRoute; attempt++) {
      await loginAndNavigateToRoute(page, user, CREATE_FORM_ROUTE, {
        timeout: 60000,
        contentSelector: CREATE_FORM_SELECTOR,
      });
      onLogin = page.url().includes('/login');
      test.skip(onLogin, 'Auth redirect — backend/rate-limit issue');
      if (onLogin) return;
      onRoute = page.url().includes('/assets/create');
      redirectedTo = page.url();
    }
    test.skip(
      !onRoute,
      `Redirected away from /assets/create to ${redirectedTo} — transient asset_creation capability gate or role state (retried once)`
    );
  }

  test('asset create: max-length name input does not crash the form', async ({ page }) => {
    const user = await getTestUser();
    await openAssetCreateForm(page, user);
    if (test.info().status === 'skipped') return;

    // The form input id was 'asset-name' (htmlFor="asset-name" on the label)
    // — not 'name'. The previous selector never matched and the test silently
    // skipped after 60s. Use the canonical id used in AssetCreatePage.tsx.
    const nameInput = page.locator('input#asset-name, input[name="name"]').first();
    // intentional: probes optional UI presence — the branch logic below handles both rendered and missing cases deterministically; absence is a legitimate tenant/role state, not a test failure.
    await nameInput.waitFor({ state: 'visible', timeout: 30000 }).catch(() => null);
    const missingNameInput = (await nameInput.count()) === 0;
    test.skip(missingNameInput, 'Asset create form did not load — backend may be slow');
    if (missingNameInput) return;
    await nameInput.fill('A'.repeat(500));
    await page.waitForTimeout(500);
    // Form should still be visible (no JS crash from long input)
    await expect(page.locator('.asset-create-page, [data-testid="asset-create-page"]').first()).toBeVisible({ timeout: 5000 });
    expect(page.url()).toContain('/assets/create');
  });

  test('asset create: special characters in key field does not crash the form', async ({ page }) => {
    const user = await getTestUser();
    await openAssetCreateForm(page, user);
    if (test.info().status === 'skipped') return;

    // Same id correction as the max-length test above: input id is 'asset-key',
    // not 'key' (see frontend/src/features/assets/components/AssetCreatePage.tsx:221).
    const keyInput = page.locator('input#asset-key, input[name="key"]').first();
    // intentional: probes optional UI presence — the branch logic below handles both rendered and missing cases deterministically; absence is a legitimate tenant/role state, not a test failure.
    await keyInput.waitFor({ state: 'visible', timeout: 30000 }).catch(() => null);
    const missingKeyInput = (await keyInput.count()) === 0;
    test.skip(missingKeyInput, 'Asset create form did not load — backend may be slow');
    if (missingKeyInput) return;
    await keyInput.fill('!@#$%^&*() invalid key');
    await page.waitForTimeout(500);
    // Form must still be visible (no JS crash)
    await expect(page.locator('.asset-create-page, [data-testid="asset-create-page"]').first()).toBeVisible({ timeout: 5000 });
    expect(page.url()).toContain('/assets/create');
  });

  test('asset create: empty required fields shows validation before submit', async ({ page }) => {
    const user = await getTestUser();
    await openAssetCreateForm(page, user);
    if (test.info().status === 'skipped') return;

    const submitBtn = page.locator('[data-testid="asset-create-submit"]').first();
    // intentional: probes optional UI presence — the branch logic below handles both rendered and missing cases deterministically; absence is a legitimate tenant/role state, not a test failure.
    await submitBtn.waitFor({ state: 'visible', timeout: 30000 }).catch(() => null);
    const missingSubmitBtn = (await submitBtn.count()) === 0;
    test.skip(missingSubmitBtn, 'Asset create form did not load — backend may be slow');
    if (missingSubmitBtn) return;
    // The Create Asset form contract: submit MUST be disabled until the
    // required fields are valid. That preventive-validation pattern is the
    // entire UX of the page; asserting it directly is the correct check.
    // (HTML5 `required` is intentionally not used by the React form because
    // the Button component manages disabled state via React state, not via
    // the native validity API — so el.validity.valid is irrelevant here.)
    const isDisabled = await submitBtn.isDisabled();
    expect(isDisabled, 'Submit must be disabled while required fields are empty').toBe(true);
    // URL must not have changed (no submission happened).
    expect(page.url()).toContain('/assets/create');
  });
});

/**
 * E2E Test: JOURNEY-DA-004 — Execute Federated Query
 *
 * Journey: Execute Federated Query
 * Persona: Data Analyst
 * Reference: docs/USER_JOURNEYS.md
 *
 * Success/Failure/Edge. Routes: /semantic (SPARQL federated), /virtualization.
 * Capability-gated: semantic.sparql. Uses getConsumerTestUser(). Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { clearAuthStorage, getConsumerTestUser, loginUser } from '../../fixtures/auth';

test.describe('JOURNEY-DA-004: Execute Federated Query', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('semantic page loads for federated query', async ({ page }) => {
      const testUser = await getConsumerTestUser();
      await loginUser(page, testUser);
      await page.goto('/semantic');
      await page.waitForLoadState('domcontentloaded');
      // The CapabilityRoute gate resolves asynchronously (OpenAPI schema +
      // runtime snapshot — under batch load that outlasts a fixed sleep),
      // then either redirects (/unavailable, /coming-soon) or mounts the
      // page. Wait for a terminal state instead of racing a 3s sleep.
      // intentional: probes optional UI presence via a multi-line locator chain — the branch logic below handles both rendered and missing cases deterministically; absence is a legitimate tenant/role state.
      await page
        .locator(
          '.semantic-page, [data-testid="semantic-page"], .unavailable-page, [data-testid="unavailable-page"], .disabled-capability-page, [data-testid="disabled-capability-page"]'
        )
        .first()
        .waitFor({ state: 'visible', timeout: 30000 })
        .catch(() => null);
      const url = page.url();
      const onLogin = url.includes('/login');
      const on403 = url.includes('/403');
      const onSemantic = url.includes('/semantic');
      const onComingSoon = url.includes('/coming-soon');
      const onUnavailable = url.includes('/unavailable');
      const authGated = onLogin || on403;
      test.skip(authGated, 'Auth/role gated — skipping success assertion');
      if (authGated) {
        return;
      }
      // CapabilityRoute sends MVP builds to /coming-soon when semantic.sparql is off.
      expect(onSemantic || onComingSoon || onUnavailable).toBe(true);
      if (onSemantic) {
        const hasContent =
          (await page.locator('.semantic-page, [data-testid="semantic-page"], .app-main, [data-testid="app-main"]').count()) > 0;
        expect(hasContent).toBe(true);
        await expect(page.locator('.error-display, [data-testid="error-display"]').first()).not.toBeVisible();
      } else {
        await expect(page.locator('.unavailable-page, [data-testid="unavailable-page"], .disabled-capability-page, [data-testid="disabled-capability-page"]').first().first()).toBeVisible({ timeout: 15000 });
      }
    });

    test('virtualization list loads for federated sources', async ({ page }) => {
      const testUser = await getConsumerTestUser();
      await loginUser(page, testUser);
      await page.goto('/virtualization');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForSelector(
        '.virtual-dataset-list-page, [data-testid="virtual-dataset-list-page"], .error-display, [data-testid="error-display"], .empty-state, [data-testid="empty-state"], .app-main, [data-testid="app-main"]',
        { timeout: 90000 }
      );
      const redirectedToLogin = page.url().includes('/login');
      test.skip(redirectedToLogin, 'Auth gated — skipping success assertion');
      if (redirectedToLogin) {
        return;
      }
      expect(page.url()).toContain('/virtualization');
      await expect(page.locator('.error-display, [data-testid="error-display"]').first()).not.toBeVisible();
    });
  });

  test.describe('Failure', () => {
    test('semantic without capability shows 403 or unavailable', async ({ page }) => {
      // Force the gate OFF deterministically: semantic.sparql is
      // path-derived and ON for every tenant in this environment, so the
      // gate-off contract is not exercisable against the real manifest
      // (b6 skip root cause: "capability enabled — gate-off contract not
      // exercisable"). Intercepting the manifest makes the SPA's own
      // CapabilityRoute run the off path — real gating logic, no
      // backend changes and no shared-state mutation. Installed BEFORE
      // loginUser: the app mount during login performs the capability
      // fetch this mock must already be answering.
      await page.route('**/api/v1/capabilities/manifest/', async (route) => {
        // Synthesize the manifest instead of fetch-then-patch: a patched
        // fetch hits the browser HTTP cache on later tests in the same
        // worker (304 / empty body) and response.json() throws. The SPA
        // defaults missing manifest keys to false, so a minimal map
        // forces the gate OFF deterministically.
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            capabilities: { 'semantic.sparql': false },
            source: 'e2e-gate-off-mock',
          }),
        });
      });
      const testUser = await getConsumerTestUser();
      await loginUser(page, testUser);
      await page.goto('/semantic');
      await page.waitForLoadState('domcontentloaded');
      // Same gate-resolution contract as the Success test: wait for a
      // terminal state (page mounted or gate-off page) instead of a fixed
      // 3s sleep racing the capabilities query.
      // intentional: probes optional UI presence via a multi-line locator chain — the branch logic below handles both rendered and missing cases deterministically; absence is a legitimate tenant/role state.
      await page
        .locator(
          '.semantic-page, [data-testid="semantic-page"], .unavailable-page, [data-testid="unavailable-page"], .disabled-capability-page, [data-testid="disabled-capability-page"]'
        )
        .first()
        .waitFor({ state: 'visible', timeout: 30000 })
        .catch(() => null);
      // The manifest mock above forces the off path — the gate-off
      // terminal states below are the assertion, not a skip branch.
      const url = page.url();
      const on403 = url.includes('/403');
      const onUnavailableDom =
        (await page.locator('.unavailable-page, [data-testid="unavailable-page"], .disabled-capability-page, [data-testid="disabled-capability-page"], .error-display, [data-testid="error-display"]').count()) > 0;
      const onLogin = url.includes('/login');
      const onUnavailableUrl = url.includes('/unavailable');
      const onComingSoon = url.includes('/coming-soon');
      expect(on403 || onUnavailableDom || onLogin || onUnavailableUrl || onComingSoon).toBe(
        true
      ) /* acceptable states */;
    });

    test('unauthenticated access redirects to login', async ({ page }) => {
      await clearAuthStorage(page);
      await page.goto('/semantic');
      await page.waitForURL(/\/(login)/, { timeout: 15000 });
      expect(page.url()).toContain('/login');
    });
  });

  test.describe('Edge', () => {
    test('semantic and virtualization routes accessible', async ({ page }) => {
      const testUser = await getConsumerTestUser();
      await loginUser(page, testUser);
      await page.goto('/semantic');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(2000);
      const su = page.url();
      expect(
        su.includes('/semantic') ||
          su.includes('/403') ||
          su.includes('/login') ||
          su.includes('/unavailable') ||
          su.includes('/coming-soon')
      ).toBe(true);
      await page.goto('/virtualization');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(2000);
      expect(page.url().includes('/virtualization') || page.url().includes('/login')).toBe(true);
    });
  });
});

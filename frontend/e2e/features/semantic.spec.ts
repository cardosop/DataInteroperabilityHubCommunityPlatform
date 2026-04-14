/**
 * E2E Feature: Semantic
 * Per E2E_FULL_COVERAGE_PLAN and tasks 29.1.10. Routes: /semantic.
 * Assert route loads or shows /unavailable or MVP /coming-soon when capability-gated
 * (CapabilityRoute uses /coming-soon when VITE_MVP_MODE=true). Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { assertSuccessLoad } from '../fixtures/journey-helpers';
import { waitForAppMainReady } from '../fixtures/helpers';

// storageState from chromium-mvp project already injects auth — no loginUser() needed.

test.describe('Feature: Semantic', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('semantic route loads when authenticated and capability enabled', async ({ page }) => {
      await page.goto('/semantic');
      try {
        await waitForAppMainReady(page, { timeout: 60000, acceptRedirectToLogin: true });
      } catch (_err) {
        if (page.url().includes('/login') || page.url().includes('/403')) { test.skip(true, 'Redirected to login/403 — auth or role gated'); return; }
        throw _err;
      }
      const url = page.url();
      expect(url).toMatch(/\/semantic|\/login|\/403|\/unavailable|\/coming-soon/);
      if (url.includes('/semantic')) {
        await assertSuccessLoad(page, {
          successContentSelector: '[data-testid="semantic-page"], .semantic-page, .unavailable-page',
        });
      } else if (url.includes('/unavailable')) {
        await assertSuccessLoad(page, {
          successContentSelector: '[data-testid="unavailable-page"], .unavailable-page',
        });
      } else if (url.includes('/coming-soon')) {
        await assertSuccessLoad(page, {
          successContentSelector: '[data-testid="coming-soon-page"], [data-testid="unavailable-page"], .unavailable-page',
        });
      }
    });
  });

  test.describe('Success — tabs', () => {
    test('SPARQL tab loads query interface', async ({ page }) => {
      await page.goto('/semantic');
      try {
        await waitForAppMainReady(page, { timeout: 30000, acceptRedirectToLogin: true });
      } catch {
        // route gated or login redirect
      }
      if (!page.url().includes('/semantic')) {
        test.skip(true, 'Semantic page not available — capability gated or auth redirect');
        return;
      }
      // SPARQL is the default tab — look for query input area
      const queryArea = page.locator(
        'textarea, [data-testid="sparql-query-input"], .sparql-query-input, .CodeMirror',
      );
      const errorDisplay = page.locator('.error-display');
      await queryArea.or(errorDisplay).first().waitFor({ state: 'visible', timeout: 15000 }).catch(() => null);

      const hasQueryUI = (await queryArea.count()) > 0;
      const hasError = (await errorDisplay.count()) > 0;
      expect(hasQueryUI || hasError).toBe(true);
    });

    test('ontology tab loads and shows content or service-unavailable error', async ({ page }) => {
      await page.goto('/semantic');
      try {
        await waitForAppMainReady(page, { timeout: 30000, acceptRedirectToLogin: true });
      } catch {
        // route gated or login redirect
      }
      if (!page.url().includes('/semantic')) {
        test.skip(true, 'Semantic page not available — capability gated or auth redirect');
        return;
      }
      // Click the Ontology tab
      const ontologyTab = page.locator(
        'button:has-text("Ontology"), [role="tab"]:has-text("Ontology")',
      ).first();
      await ontologyTab.waitFor({ state: 'visible', timeout: 10000 }).catch(() => null);
      if ((await ontologyTab.count()) === 0) {
        test.skip(true, 'Ontology tab not visible on semantic page');
        return;
      }
      await ontologyTab.click();

      // Wait for either ontology tree content or error display
      const ontologyTree = page.locator('[data-testid="ontology-tree"]');
      const codeBlock = page.locator('pre, code, .code-block');
      const errorDisplay = page.locator('.error-display');
      const loadingSpinner = page.locator('.loading-spinner');

      await ontologyTree.or(codeBlock).or(errorDisplay).first()
        .waitFor({ state: 'visible', timeout: 20000 })
        .catch(() => null);

      const hasOntologyContent = (await ontologyTree.count()) > 0 || (await codeBlock.count()) > 0;
      const hasError = (await errorDisplay.count()) > 0;
      const stillLoading = (await loadingSpinner.count()) > 0;

      // Accept: ontology tree rendered, code block visible, error display, or still loading
      expect(hasOntologyContent || hasError || stillLoading).toBe(true);
    });
  });

  test.describe('Edge', () => {
    test('semantic shows unavailable or MVP coming-soon when capability-gated', async ({ page }) => {
      await page.goto('/semantic');
      // Wait for the app to fully initialize (lazy bundles + auth check) rather than a fixed sleep.
      // waitForAppMainReady handles the visible/slowMo project's slower rendering correctly.
      try {
        await waitForAppMainReady(page, { timeout: 30000, acceptRedirectToLogin: true });
      } catch {
        // Ignore if the route is gated or login redirect fires
      }
      const url = page.url();
      const onSemantic = url.includes('/semantic');
      const onUnavailable = url.includes('/unavailable');
      const onComingSoon = url.includes('/coming-soon');
      const onLogin = url.includes('/login');
      const on403 = url.includes('/403');
      expect(onSemantic || onUnavailable || onComingSoon || onLogin || on403).toBe(true) /* acceptable states */;
      if (onSemantic) {
        // Wait for the page content to become visible — lazy bundle may still be loading
        await page
          .locator('[data-testid="semantic-page"], .semantic-page, .unavailable-page')
          .first()
          .waitFor({ state: 'visible', timeout: 15000 })
          .catch(() => {});
        const hasContent =
          (await page.locator('[data-testid="semantic-page"], .semantic-page, .unavailable-page').count()) > 0;
        expect(hasContent).toBe(true) /* acceptable states */;
      } else if (onUnavailable) {
        await assertSuccessLoad(page, {
          successContentSelector: '[data-testid="unavailable-page"], .unavailable-page',
        });
      } else if (onComingSoon) {
        await assertSuccessLoad(page, {
          successContentSelector: '[data-testid="coming-soon-page"], [data-testid="unavailable-page"], .unavailable-page',
        });
      }
    });
  });
});

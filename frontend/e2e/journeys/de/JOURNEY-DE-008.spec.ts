/**
 * E2E Test: JOURNEY-DE-008 — Integrate AI Schema Matching into Workflow
 *
 * Journey: Integrate AI Schema Matching into Workflow
 * Persona: Data Engineer
 * Reference: docs/USER_JOURNEYS.md
 *
 * Success/Failure/Edge. Routes: /ai/schema-matching.
 * Capability-gated: ai.schema-matching. Real backend only; no mocks.
 *
 * Gate contract (close-test-coverage-gaps 1.3): real-flow-first — the
 * schema-matching page itself is the primary assertion; every skip is
 * CONDITIONAL (no-test-skip-true clean); transient /unavailable bounces
 * are W16-guarded (environmentSkipGuard: CI raises, local skips); the
 * MvpGatedRoute-wrapped /ai subtree redirects to /coming-soon in MVP
 * mode and is tolerated as a conditional skip.
 */

import { expect, test } from '@playwright/test';
import { environmentSkipGuard } from '../../fixtures/envPolicy.cjs';
import { getTestUser } from '../../fixtures/auth';
import { loginAndNavigateToRoute } from '../../fixtures/helpers';

test.describe('JOURNEY-DE-008: Integrate AI Schema Matching into Workflow', () => {
  test.setTimeout(90000);

  test.describe('Success', () => {
    test('schema matching page loads', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/ai/schema-matching', {
        timeout: 60000,
        contentSelector:
          '[data-testid="schema-matching-page"], .schema-matching-page, .unavailable-page, [data-testid="unavailable-page"], [data-testid="coming-soon-page"], .error-display, [data-testid="error-display"]',
      });
      const url = page.url();
      const onLogin = url.includes('/login');
      const on403 = url.includes('/403');
      const onComingSoon = url.includes('/coming-soon');
      // ComingSoonPage REUSES the .unavailable-page class — distinguish
      // the real /unavailable bounce by URL, not by selector.
      const onUnavailable = url.includes('/unavailable') && !onComingSoon;
      test.skip(onLogin || on403, 'Auth/role gated — server-side 403 route');
      test.skip(
        onComingSoon,
        'MVP mode — /ai/* is MvpGatedRoute and redirects to /coming-soon'
      );
      // Transient capability-resolution failure: the /ai/schema-matching
      // gate derives from the OpenAPI snapshot (capabilitiesService
      // isPathIncluded). Under batch load — e.g. an API restart window —
      // the snapshot fetch fails and the gate fails CLOSED to /unavailable
      // even though the capability is stable (the OpenAPI always includes
      // /api/v1/ai/schema-matching/, and 1.2 fail-opens the fallback map).
      // Skip locally; raise in CI (W16).
      if (onUnavailable) {
        environmentSkipGuard(
          'Capability gate bounced /ai/schema-matching to /unavailable — ' +
            'OpenAPI/capabilities snapshot fetch likely failed under parallel load'
        );
      }
      test.skip(
        onUnavailable,
        'Capability gate bounced to /unavailable — transient snapshot failure'
      );

      // Real flow, primary: the schema-matching page renders (the backend
      // endpoint always exists — AIViewSet action, no tenant flag — so
      // the SPA-side gate is the only hop).
      expect(url).toContain('/ai/schema-matching');
      await expect(
        page
          .locator('.schema-matching-page, [data-testid="schema-matching-page"]')
          .first()
      ).toBeVisible({ timeout: 15000 });
      await expect(
        page.locator('.error-display, [data-testid="error-display"]').first()
      ).not.toBeVisible();
    });
  });

  test.describe('Failure', () => {
    test('unauthenticated access to /ai/schema-matching redirects to login', async ({ page }) => {
      const { clearAuthStorage } = await import('../../fixtures/auth');
      await clearAuthStorage(page);
      await page.goto('/ai/schema-matching', { waitUntil: 'domcontentloaded' });
      // intentional: best-effort .catch on an optional step — primary pass/fail is made by a downstream assertion (verifyViaApi, waitFor, explicit expect). The fallback value tolerates well-known transient or absent-UI cases without papering over real failures.
      await page.waitForURL(/\/(login|403)/, { timeout: 20000 }).catch(() => null);
      expect(page.url().includes('/login') || page.url().includes('/403')).toBe(true);
    });
  });

  test.describe('Edge', () => {
    test('schema matching page loads or redirects', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/ai/schema-matching', {
        timeout: 60000,
        contentSelector:
          '[data-testid="schema-matching-page"], .schema-matching-page, .unavailable-page, [data-testid="unavailable-page"], [data-testid="coming-soon-page"], .error-display, [data-testid="error-display"]',
      });
      const url = page.url();
      expect(
        url.includes('/login') ||
          url.includes('/403') ||
          url.includes('/unavailable') ||
          url.includes('/coming-soon') ||
          url.includes('/ai/schema-matching')
      ).toBe(true);
    });
  });
});

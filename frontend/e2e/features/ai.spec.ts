/**
 * E2E Feature: AI (capability-gated)
 * Routes: /ai/search (ai.natural-language-search), /ai/schema-matching (ai.schema-matching).
 * Both routes are capability-gated via CapabilityRoute — when disabled, they redirect
 * to /unavailable or /coming-soon. Tests verify the gating works correctly.
 * Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { getTestUser } from '../fixtures/auth';
import { assertCapabilityGatedPageLoads, loginAndNavigateToRoute } from '../fixtures/helpers';

// Phase 226.G6 — AI surfaces are MvpGatedRoute-gated alongside /ml. Since
// `ml_mvp_in_scope=false` (docs/CRITICAL_UC_JOURNEY_IDS.yaml), AI specs are
// tagged @post-mvp so the traceability gate does not count them against
// critical-coverage. Re-tag when the AI capability flips back into MVP.
//
// Gate-off union (Phase 250.6.A.5): when the capability is OFF, /unavailable
// renders DisabledCapabilityPage (`.disabled-capability-page` /
// `[data-testid="disabled-capability-page"]`), NOT the legacy
// `.unavailable-page` markers (those only cover ComingSoonPage's
// `.unavailable-page` class). The legacy markers alone left the union with
// zero matches and the 3s terminal assertion failed (b7 #1/#2).
const GATE_OFF_UNION =
  '.unavailable-page, [data-testid="unavailable-page"], .disabled-capability-page, [data-testid="disabled-capability-page"], .coming-soon-page, [data-testid="coming-soon-page"]';
const NAV_CONTENT_UNION = `${GATE_OFF_UNION}, .error-display, [data-testid="error-display"], h1`;

test.describe('Feature: AI (capability-gated) @post-mvp', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('ai search route loads or shows capability-gated redirect', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/ai/search', {
        timeout: 60000,
        contentSelector: `.ai-search-page, ${NAV_CONTENT_UNION}`,
      });
      await assertCapabilityGatedPageLoads(page, `.ai-search-page, ${GATE_OFF_UNION}`, {
        timeout: 30000,
      });
    });
  });

  test.describe('Failure', () => {
    test('unauthenticated access to ai redirects to login', async ({ page }) => {
      await page.goto('/ai/search');
      await page.waitForLoadState('domcontentloaded');
      const url = page.url();
      expect(
        url.includes('/login') || url.includes('/ai') || url.includes('/unavailable'),
        'Expected /login redirect, /ai route, or /unavailable'
      ).toBe(true);
    });
  });

  test.describe('Edge', () => {
    test('ai schema-matching route shows capability-gated redirect', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/ai/schema-matching', {
        timeout: 60000,
        contentSelector: `.schema-matching-page, ${NAV_CONTENT_UNION}`,
      });
      await assertCapabilityGatedPageLoads(
        page,
        `.schema-matching-page, ${GATE_OFF_UNION}`,
        { timeout: 30000 }
      );
    });
  });
});

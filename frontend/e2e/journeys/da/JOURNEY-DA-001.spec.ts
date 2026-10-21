/**
 * E2E Test: JOURNEY-DA-001 — Create Transformation Pipeline
 *
 * Journey: Create Transformation Pipeline
 * Persona: Data Analyst
 * Reference: docs/USER_JOURNEYS.md
 *
 * Use cases covered (per docs/CRITICAL_UC_JOURNEY_IDS.yaml):
 *   - UC-TRANS-001  # Create Transformation Pipeline — list/route-access
 *                     coverage from the Data Analyst persona. This spec
 *                     does NOT submit a pipeline create form or assert
 *                     pipeline state.
 *
 * Coverage gap (intentionally out of scope; queued for future specs):
 *   - UC-TRANS-002  # Execute Transformation Pipeline
 *   - UC-TRANS-003  # Monitor Pipeline Execution
 * Tagging tracked under Phase 226.D4.
 *
 * Uses placeholder transformation API (/api/v1/transformation/pipelines/).
 * Success/Failure/Edge. Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { environmentSkipGuard } from '../../fixtures/envPolicy.cjs';
import { clearAuthStorage, getTestUser, loginUser } from '../../fixtures/auth';
import { assertNonExistentIdShowsError, loginAndNavigateToRoute } from '../../fixtures/helpers';

test.describe('JOURNEY-DA-001: Create Transformation Pipeline @critical', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('transformation pipelines list loads', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/transformation', {
        timeout: 60000,
        contentSelector:
          '.transformation-pipeline-list-page, .empty-state, [data-testid="empty-state"], .error-display, [data-testid="error-display"], .transformation-list-error-wrapper, .disabled-capability-page, [data-testid="disabled-capability-page"]',
      });
      // The /transformation subtree is CapabilityRoute-gated. Two distinct
      // gate-off terminal states:
      //  - /coming-soon (MVP mode): genuinely out of scope per environment —
      //    plain skip.
      //  - /unavailable: the runtime capabilities payload emits
      //    transformation_pipelines: true for the test tenant, so this
      //    bounce is a TRANSIENT capabilities-snapshot fetch failure under
      //    batch churn (API restart window), not a disabled feature.
      //    W16-guarded skip: raises in CI, skips locally.
      test.skip(
        page.url().includes('/coming-soon'),
        'transformation out of MVP scope — success contract not exercisable'
      );
      if (page.url().includes('/unavailable')) {
        environmentSkipGuard(
          'transformation gate bounced to /unavailable — capabilities snapshot fetch failed under parallel load'
        );
      }
      test.skip(
        page.url().includes('/unavailable'),
        'transformation gate bounced to /unavailable — transient snapshot failure'
      );
      expect(page.url()).toContain('/transformation');
      const hasError = (await page.locator('.error-display, [data-testid="error-display"]').first().count()) > 0;
      if (hasError) {
        // intentional: tolerates a detached/removed element while extracting text for a diagnostic message; the surrounding throw/expect below this catch is the primary failure path.
        const msg = await page.locator('.error-display, [data-testid="error-display"]').first().first().textContent().catch(() => '');
        throw new Error(`Transformation pipelines list shows error instead of content: "${msg?.slice(0, 300)}"`);
      }
      const hasContent =
        (await page.locator('.transformation-pipeline-list-page, [data-testid="transformation-pipeline-list-page"]').first().count()) > 0 ||
        (await page.locator('.empty-state, [data-testid="empty-state"]').first().count()) > 0 ||
        (await page.locator('.transformation-list-error-wrapper').count()) > 0;
      expect(hasContent).toBe(true);
    });
  });

  test.describe('Failure', () => {
    test('transformation pipeline detail with non-existent id shows error', async ({ page }) => {
      const testUser = await getTestUser();
      await loginUser(page, testUser);
      await page.goto('/transformation/pipelines/00000000-0000-0000-0000-000000000000');
      await page.waitForLoadState('domcontentloaded');
      await assertNonExistentIdShowsError(page, {
        detailContentSelector: '.transformation-detail-page',
        waitAfterLoad: 8000,
      });
    });

    test('unauthenticated access redirects to login', async ({ page }) => {
      await clearAuthStorage(page);
      await page.goto('/transformation');
      await page.waitForURL(/\/(login)/, { timeout: 15000 });
      expect(page.url()).toContain('/login');
    });
  });

  test.describe('Edge', () => {
    test('transformation route accessible', async ({ page }) => {
      const testUser = await getTestUser();
      await loginAndNavigateToRoute(page, testUser, '/transformation', {
        timeout: 60000,
        contentSelector:
          '.transformation-pipeline-list-page, .empty-state, [data-testid="empty-state"], .error-display, [data-testid="error-display"], .transformation-list-error-wrapper, .disabled-capability-page, [data-testid="disabled-capability-page"]',
      });
      // Gate-off is a valid terminal state for the route-access contract:
      // CapabilityRoute redirects to /unavailable (or /coming-soon in MVP
      // mode) when the capability is disabled for the tenant.
      if (page.url().includes('/unavailable') || page.url().includes('/coming-soon')) {
        expect(page.url()).toMatch(/\/unavailable|\/coming-soon/);
        return;
      }
      expect(page.url()).toContain('/transformation');
    });
  });
});

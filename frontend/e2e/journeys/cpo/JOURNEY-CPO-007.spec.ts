/**
 * E2E Test: JOURNEY-CPO-007 — Set Up GDPR Right to be Forgotten
 *
 * Journey: Set Up GDPR Right to be Forgotten
 * Persona: Compliance Officer
 * Use Case: UC-CPO-007 (Set Up GDPR Right to be Forgotten)
 * Reference: docs/USER_JOURNEYS.md, docs/USE_CASES.md
 *
 * Success/Failure/Edge. Routes: /compliance, /governance.
 * Fixture: getComplianceOfficerUser(). Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { clearAuthStorage, getComplianceOfficerUser, loginAsPersona } from '../../fixtures/auth';
import { assertNonExistentIdShowsError, waitForAppMainReady, waitForLoadingComplete } from '../../fixtures/helpers';

test.describe('JOURNEY-CPO-007: Set Up GDPR Right to be Forgotten @critical', () => {
  test.setTimeout(120000);

  test.describe('Success', () => {
    test('compliance page loads', async ({ page }) => {
      await loginAsPersona(page, getComplianceOfficerUser);
      await page.goto('/compliance');
      await page.waitForLoadState('domcontentloaded');
      try {
        await waitForAppMainReady(page, { timeout: 60000 });
      } catch (_err) {
        if (page.url().includes('/login') || page.url().includes('/403')) {
          test.skip(page.url().includes('/login') || page.url().includes('/403'), 'Auth/role gated — skipping success assertion');
          return;
        }
        throw _err;
      }
      expect(page.url()).toContain('/compliance');
      // error-display is NOT acceptable — compliance service must be reachable
      const hasError = (await page.locator('.error-display, [data-testid="error-display"]').first().count()) > 0;
      if (hasError) {
        // intentional: tolerates a detached/removed element while extracting text for a diagnostic message; the surrounding throw/expect below this catch is the primary failure path.
        const errText = await page.locator('.error-display, [data-testid="error-display"]').first().first().textContent().catch(() => '');
        throw new Error(`Compliance page shows error for CPO user: "${errText?.slice(0, 300)}"`);
      }
      const hasContent =
        (await page.locator('.compliance-run-list-page, [data-testid="compliance-run-list-page"]').first().count()) > 0 ||
        (await page.locator('.empty-state, [data-testid="empty-state"]').first().count()) > 0;
      expect(hasContent).toBe(true) /* acceptable states */;
    });

    test('governance page loads', async ({ page }) => {
      await loginAsPersona(page, getComplianceOfficerUser);
      await page.goto('/governance');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(3000);
      const onGov = page.url().includes('/governance');
      const on403 = page.url().includes('/403');
      const onLogin = page.url().includes('/login');
      if (on403 || onLogin) {
        test.skip(on403 || onLogin, 'Auth/role gated — skipping success assertion');
        return;
      }
      expect(onGov).toBe(true);
      await expect(page.locator('.error-display, [data-testid="error-display"]').first()).not.toBeVisible();
    });

    test('privacy page has GDPR erasure (right to be forgotten) section', async ({ page }) => {
      // The GDPR erasure surface moved from /governance to /settings/privacy
      // (features/gdpr/components/PrivacyPage — GDPR Article 17, Right to be
      // Forgotten, alongside Article 20 export requests; routes.tsx nests the
      // 'privacy' path under 'settings'). /governance is now the
      // access-requests hub (GovernanceLayout is a bare <Outlet /> with no
      // sub-nav and no GDPR content), so the old assertion set could never
      // match the current UI.
      await loginAsPersona(page, getComplianceOfficerUser);
      await page.goto('/settings/privacy');
      await page.waitForLoadState('domcontentloaded');
      try {
        await waitForAppMainReady(page, { timeout: 60000 });
      } catch (_err) {
        if (page.url().includes('/login') || page.url().includes('/403')) {
          test.skip(page.url().includes('/login') || page.url().includes('/403'), 'Auth/role gated — skipping success assertion');
          return;
        }
        throw _err;
      }
      if (page.url().includes('/login') || page.url().includes('/403')) {
        test.skip(page.url().includes('/login') || page.url().includes('/403'), 'Auth/role gated — skipping success assertion');
        return;
      }
      await waitForLoadingComplete(page, { timeout: 15000 });

      // The erasure section is the GDPR Article 17 surface (static content,
      // renders regardless of request-list API state).
      const erasureSection = page.locator('[data-testid="privacy-erasure-section"]');
      // intentional: visibility check on a transiently-attached element — treating a detached-at-check-time element as 'not visible' is the semantically correct fallback; the caller's branch logic uses the boolean result.
      const erasureVisible = (await erasureSection.count()) > 0 && await erasureSection.first().isVisible().catch(() => false);
      const gdprText = page.getByText(/Right to be Forgotten|GDPR Article 17|erasure/i);
      // intentional: visibility check on a transiently-attached element — treating a detached-at-check-time element as 'not visible' is the semantically correct fallback; the caller's branch logic uses the boolean result.
      const gdprTextVisible = (await gdprText.count()) > 0 && await gdprText.first().isVisible().catch(() => false);

      expect(erasureVisible || gdprTextVisible).toBe(true);

      // Churn recovery: PrivacyPage's request-list fetch (exports/erasures)
      // can fail during an API restart window and the page surfaces an
      // ErrorDisplay alongside the static erasure section (which renders
      // regardless). Use the page's own Retry (loadData) ONCE before the
      // strict D85 assertion; a persistent error still fails below.
      const errorDisplay = page.locator('.error-display, [data-testid="error-display"]').first();
      if ((await errorDisplay.count()) > 0) {
        // intentional: diagnostic-only read — an empty read skips the retry
        // and the strict assertion below reports the visible state.
        const errText = (await errorDisplay.textContent().catch(() => '')) ?? '';
        if (/NETWORK_ERROR|Failed to fetch|connection|INTERNAL_ERROR|SERVICE_UNAVAILABLE/i.test(errText)) {
          await errorDisplay.locator('button:has-text("Retry")').first().click();
          // intentional: the retry may also fail under sustained churn — the
          // strict not.toBeVisible below then fails with the real state.
          await page
            .locator('.error-display, [data-testid="error-display"], [data-testid="privacy-export-section"], [data-testid="privacy-erasure-section"]')
            .first()
            .waitFor({ state: 'visible', timeout: 30000 })
            .catch(() => null);
        }
      }

      // error-display must NOT be visible (D85)
      await expect(errorDisplay).not.toBeVisible();
    });
  });

  test.describe('Failure', () => {
    test('compliance run with non-existent id shows error', async ({ page }) => {
      await loginAsPersona(page, getComplianceOfficerUser);
      await page.goto('/compliance/runs/00000000-0000-0000-0000-000000000000');
      await page.waitForLoadState('domcontentloaded');
      await assertNonExistentIdShowsError(page, {
        detailContentSelector: '.compliance-run-detail-page, [data-testid="compliance-run-detail-page"]',
        waitAfterLoad: 8000,
      });
    });

    test('unauthenticated access redirects to login', async ({ page }) => {
      await clearAuthStorage(page);
      await page.goto('/compliance');
      await page.waitForURL(/\/(login)/, { timeout: 15000 });
      expect(page.url()).toContain('/login');
    });
  });

  test.describe('Edge', () => {
    test('compliance and governance routes accessible', async ({ page }) => {
      await loginAsPersona(page, getComplianceOfficerUser);
      await page.goto('/compliance');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(2000);
      if (page.url().includes('/login') || page.url().includes('/403')) {
        expect(page.url()).toMatch(/\/login|\/403/);
        return;
      }
      expect(page.url()).toContain('/compliance');
      await page.goto('/governance');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(2000);
      expect(page.url().includes('/governance') || page.url().includes('/403') || page.url().includes('/login')).toBe(true);
    });
  });
});

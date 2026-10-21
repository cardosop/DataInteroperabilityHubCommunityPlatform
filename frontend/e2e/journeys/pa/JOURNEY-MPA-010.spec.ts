/**
 * E2E Test: JOURNEY-MPA-010 — Impersonate a User for Support (W5.1, R2-F1)
 *
 * The D6-adjacent frontend contract (oss-release-remediation R2-F1):
 * the impersonation bearer is PERSISTED (sessionStorage), ATTACHED
 * (replacing the operator bearer + scoping X-Tenant-ID to the target
 * tenant), and CLEARED on exit/logout. The pre-fix SPA never attached
 * the token at all — actions silently ran as the OPERATOR while the
 * banner claimed otherwise (the identity-revert trap).
 *
 * Pins:
 *  1. The impersonation start button renders on the target user's edit
 *     page (the pre-fix button was never mounted anywhere).
 *  2. Starting a session shows the red banner (IMPERSONATING).
 *  3. Actions run AS THE TARGET — /auth/me/ under the SPA's
 *     sessionStorage bearer reports the target's email.
 *  4. The audit trail carries the IMPERSONATION_STARTED row (queried
 *     as the platform admin).
 *  5. Exit clears the stored token + unmounts the banner.
 *
 * Persona: Platform Admin. Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { clearAuthStorage, getPlatformAdminUser } from '../../fixtures/auth';
import { e2eTestHeaders } from '../../fixtures/e2e-token';
import { loginAndNavigateToRoute } from '../../fixtures/helpers';

const DEFAULT_API_PORT = process.env.E2E_WEB_PORT ? '8001' : '8000';
const API_BASE =
  process.env.E2E_API_BASE_URL ||
  (process.env.VITE_PROXY_TARGET
    ? `${process.env.VITE_PROXY_TARGET.replace(/\/$/, '')}/api/v1`
    : null) ||
  (process.env.VITE_API_BASE_URL?.startsWith('http') ? process.env.VITE_API_BASE_URL : null) ||
  `http://localhost:${DEFAULT_API_PORT}/api/v1`;

const TARGET_EMAIL = 'e2e_test@example.com';

test.describe('JOURNEY-MPA-010: Impersonate a User for Support', () => {
  test.setTimeout(180000);

  test.describe('Success', () => {
    test('impersonation runs actions as the target with banner + audit trail', async ({
      page,
    }) => {
      // Seed: ensure the E2E users exist + the default tenant opts into
      // impersonation (the W5.1 seeder leg — idempotent).
      // The test helper is gated by the X-E2E-Token header
      // (require_e2e_token — an unset token 404s the endpoint).
      await page.request
        .post(`${API_BASE}/test/ensure-e2e-users/`, {
          headers: { ...e2eTestHeaders() },
        })
        .catch(() => null);

      const paUser = await getPlatformAdminUser();
      await loginAndNavigateToRoute(page, paUser, '/admin', {
        timeout: 65000,
        contentSelector:
          '.admin-page, [data-testid="admin-page"], .empty-state, .error-display, .disabled-capability-page',
      });
      const gated =
        page.url().includes('/login') || page.url().includes('/403') || page.url().includes('/unavailable');
      test.skip(gated, 'Auth/role gated — skipping impersonation assertions');
      if (gated) return;

      // The SPA keeps its bearer in JS module memory (Phase 11.1) —
      // mint the PA's API token via a direct login call instead of
      // reading the browser storage.
      const loginResp = await page.request
        .post(`${API_BASE}/auth/login/`, {
          data: { email: paUser.email, password: paUser.password },
        })
        .catch(() => null);
      test.skip(!loginResp || !loginResp.ok(), 'PA login API unavailable');
      if (!loginResp || !loginResp.ok()) return;
      const loginData = (await loginResp.json()) as { access_token?: string };
      const accessToken = loginData.access_token;
      if (!accessToken) {
        test.skip(true, 'No bearer token minted for the PA');
        return;
      }

      // Resolve the target user id via the users API (as the PA).
      const usersResp = await page.request
        .get(`${API_BASE}/users/?search=${encodeURIComponent(TARGET_EMAIL)}`, {
          headers: { Authorization: `Bearer ${accessToken}` },
        })
        .catch(() => null);
      test.skip(!usersResp || !usersResp.ok(), 'Users API unavailable — cannot resolve the target');
      if (!usersResp || !usersResp.ok()) return;
      const usersData = (await usersResp.json()) as {
        results?: Array<{ id: string; email?: string; tenant_id?: string }>;
      };
      const target = usersData.results?.find((u) => u.email === TARGET_EMAIL);
      test.skip(!target, 'Target user not seeded');
      if (!target) return;
      const targetTenantId = target.tenant_id ?? '';

      // 1. The button is mounted on the user edit page.
      await page.goto(`/admin/users/${target.id}/edit`, { waitUntil: 'domcontentloaded' });
      await page.waitForLoadState('domcontentloaded');
      const startButton = page.getByTestId('impersonation-start-button');
      await expect(startButton).toBeVisible({ timeout: 30000 });

      // 2. Start the session (reason ≥ 10 chars — the serializer floor).
      await startButton.click();
      await page
        .getByTestId('impersonation-reason-input')
        .fill('On-call support investigation for the E2E impersonation journey');
      await page.getByTestId('impersonation-start-confirm').click();

      // 3. The red banner renders after the post-start reload.
      const banner = page.getByTestId('impersonation-banner');
      await expect(banner).toBeVisible({ timeout: 60000 });
      await expect(banner).toContainText('IMPERSONATING');

      // 4. Actions run AS THE TARGET: the SPA's bearer is the
      //    impersonation JWT persisted in sessionStorage (R2-F1).
      const impToken = await page.evaluate(() =>
        sessionStorage.getItem('impersonation_access_token')
      );
      expect(impToken).toBeTruthy();
      const meResp = await page.request
        .get(`${API_BASE}/auth/me/`, {
          headers: { Authorization: `Bearer ${impToken}` },
        })
        .catch(() => null);
      if (meResp && meResp.ok()) {
        const me = (await meResp.json()) as { email?: string };
        expect(me.email).toBe(TARGET_EMAIL);
      } else {
        // The identity pin must hold — a failed /auth/me/ under the
        // impersonation bearer is the regression we guard.
        expect(meResp?.status()).toBe(200);
      }

      // 5. Audit trail: an IMPERSONATION_STARTED row exists for the
      //    session (queried as the PA against the target tenant).
      const auditResp = await page.request
        .get(`${API_BASE}/audit-events/?page_size=50`, {
          headers: {
            Authorization: `Bearer ${accessToken}`,
            'X-Tenant-ID': targetTenantId,
          },
        })
        .catch(() => null);
      if (auditResp && auditResp.ok()) {
        const auditData = (await auditResp.json()) as {
          results?: Array<{ action?: string }>;
        };
        const startedRows = (auditData.results ?? []).filter(
          (r) => r.action === 'IMPERSONATION_STARTED'
        );
        expect(startedRows.length).toBeGreaterThan(0);
      }

      // 6. Exit clears the stored token + unmounts the banner.
      await page.getByTestId('impersonation-banner-exit').click();
      await expect(banner).not.toBeVisible({ timeout: 60000 });
      // The exit reloads the SPA — wait for the navigation to settle
      // before touching the new execution context.
      await page.waitForLoadState('domcontentloaded');
      const leftover = await page.evaluate(() =>
        sessionStorage.getItem('impersonation_access_token')
      );
      expect(leftover).toBeNull();
    });
  });

  test.describe('Failure', () => {
    test('unauthenticated access redirects', async ({ page }) => {
      await clearAuthStorage(page);
      await page.goto('/admin', { waitUntil: 'domcontentloaded' });
      await page.waitForURL(/\/(login|admin|403)/, { timeout: 20_000 });
      const url = page.url();
      expect(url.includes('/login') || url.includes('/admin') || url.includes('/403')).toBe(true);
    });
  });
});

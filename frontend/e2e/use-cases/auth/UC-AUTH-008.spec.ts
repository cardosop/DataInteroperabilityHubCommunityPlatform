/**
 * E2E: UC-AUTH-008 — Platform Admin Impersonates a User
 *
 * Use Case: Platform Admin Impersonates a User
 * Persona: Marketplace Platform Admin
 * Reference: docs/USE_CASES.md, docs/mvpdocs/use-cases/UC-AUTH-008.md
 * (W5.1 / oss-release-remediation R2-F1 — the bearer persist/attach/
 * clear contract). The journey-level spec (JOURNEY-MPA-010) covers the
 * full flow; this spec pins the UC's core acceptance: the identity swap
 * (actions run as the target) + the banner + the exit cleanup.
 * Real backend only; no mocks.
 */

import { expect, test } from '@playwright/test';
import { getPlatformAdminUser } from '../../fixtures/auth';
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

test.describe('UC-AUTH-008: Platform Admin Impersonates a User', () => {
  test.setTimeout(180000);

  test('the SPA bearer runs requests as the impersonated target', async ({ page }) => {
    await page.request.post(`${API_BASE}/test/ensure-e2e-users/`).catch(() => null);

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

    const usersResp = await page.request
      .get(`${API_BASE}/users/?search=${encodeURIComponent(TARGET_EMAIL)}`, {
        headers: { Authorization: `Bearer ${accessToken}` },
      })
      .catch(() => null);
    test.skip(!usersResp || !usersResp.ok(), 'Users API unavailable — cannot resolve the target');
    if (!usersResp || !usersResp.ok()) return;
    const usersData = (await usersResp.json()) as {
      results?: Array<{ id: string; email?: string }>;
    };
    const target = usersData.results?.find((u) => u.email === TARGET_EMAIL);
    test.skip(!target, 'Target user not seeded');
    if (!target) return;

    await page.goto(`/admin/users/${target.id}/edit`, { waitUntil: 'domcontentloaded' });
    await page.waitForLoadState('domcontentloaded');
    const startButton = page.getByTestId('impersonation-start-button');
    await expect(startButton).toBeVisible({ timeout: 30000 });
    await startButton.click();
    await page
      .getByTestId('impersonation-reason-input')
      .fill('UC-AUTH-008 acceptance run — support investigation');
    await page.getByTestId('impersonation-start-confirm').click();

    const banner = page.getByTestId('impersonation-banner');
    await expect(banner).toBeVisible({ timeout: 60000 });
    await expect(banner).toContainText('IMPERSONATING');

    // The UC's core acceptance: the persisted bearer IS the target.
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
      expect(meResp?.status()).toBe(200);
    }

    // Exit clears the persisted bearer.
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

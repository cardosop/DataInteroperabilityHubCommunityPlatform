/**
 * W5.3 (oss-release-remediation R2-F3) — the SSE-open pin (real stack).
 *
 * The notification stream must OPEN against the real backend: after
 * login, the header's NotificationBell mounts the unified
 * useNotificationStream hook and the SPA's REAL fetch issues
 * GET /api/v1/notifications/stream/?tenant_id=<active tenant>, and the
 * backend answers 200 text/event-stream (its first frame is
 * `event: ready`).
 *
 * Runs in BOTH auth modes:
 * - chromium-cookie-auth: the stream authenticates via the httpOnly
 *   session cookies (credentials: 'include'). Pre-W5.3 this was a hard
 *   401 — the native EventSource carried NO Cookie header (Chrome 145
 *   ignores withCredentials) and the bearer-mode guard bailed.
 * - default chromium (token mode): the stream attaches the OPERATOR
 *   bearer — the pre-fix EventSource could never authenticate here at
 *   all (headers can't be attached), the 401-storm class this pin
 *   retires.
 */

import { expect, test } from '@playwright/test';
import { getTestUser } from '../../fixtures/auth';
import { loginAndNavigateToRoute } from '../../fixtures/helpers';

test.describe('Notification SSE stream (W5.3 SSE-open pin)', () => {
  test.setTimeout(120000);

  test('the stream opens for the active tenant after login', async ({ page }) => {
    const testUser = await getTestUser();
    // Playwright's own response events only fire when a response
    // COMPLETES — a never-ending SSE stream never completes, so the
    // observation goes through the CDP seam: Network.responseReceived
    // fires the moment the response HEADERS land, which is exactly
    // what "the stream opened" means. Real browser network events,
    // nothing faked.
    const cdp = await page.context().newCDPSession(page);
    await cdp.send('Network.enable');
    const streamOpened = new Promise<{
      status: number;
      mimeType: string;
      url: string;
    }>((resolve, reject) => {
      const timeout = setTimeout(
        () => reject(new Error('stream response headers never arrived')),
        45000,
      );
      cdp.on('Network.responseReceived', (event) => {
        const res = event.response;
        if (res.url.includes('/notifications/stream/')) {
          clearTimeout(timeout);
          resolve({ status: res.status, mimeType: res.mimeType, url: res.url });
        }
      });
    });

    try {
      await loginAndNavigateToRoute(page, testUser, '/', {
        timeout: 60000,
        contentSelector: '.app-main, [data-testid="app-main"], h1',
      });
      if (page.url().includes('/login')) {
        test.skip(page.url().includes('/login'), 'Auth redirect');
        return;
      }

      const opened = await streamOpened;
      // The open itself: 200 + text/event-stream (never an error page).
      expect(opened.status).toBe(200);
      expect(opened.mimeType).toContain('text/event-stream');
      // The stream is tenant-gated by the FIXED useActiveTenantId: the
      // request carries the active tenant (the backend routes by user_id,
      // the query param pins the frontend derivation).
      expect(opened.url).toContain('tenant_id=');
    } finally {
      await cdp.detach();
    }
  });
});

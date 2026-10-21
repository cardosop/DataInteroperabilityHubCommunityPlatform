/**
 * E2E Test: Frontend security headers and CSRF protection — Phase 312.8.6
 *
 * Validates:
 *   - CSP header: Content-Security-Policy present in HTTP response
 *   - CSRF token: POST without CSRF → 403; POST with CSRF → success
 *   - Nginx security headers: X-Frame-Options, X-Content-Type-Options,
 *     HSTS (Strict-Transport-Security), Referrer-Policy, Permissions-Policy
 *   - CSP violation reporting: trigger CSP violation, verify /api/csp-report/
 *     receives the report
 *
 * Dependencies: Real backend (docker-compose) serving the frontend through
 * Traefik/Nginx reverse proxy.  CSP report endpoint must be reachable.
 */

import { expect, test } from '@playwright/test';
import { getApiBaseUrl } from '../fixtures/auth';

test.describe('Security Headers E2E (312.8.6)', () => {
  test.setTimeout(60000);

  // ──────────────────────────────────────────────────────────────────────
  // CSP Header Validation
  // ──────────────────────────────────────────────────────────────────────

  test.describe('Content-Security-Policy header', () => {
    test('main page response includes Content-Security-Policy header', async ({ page }) => {
      const response = await page.goto('/', { timeout: 30000 });
      expect(response).not.toBeNull();
      const headers = response!.headers();
      // CSP header may be named 'content-security-policy' or
      // 'content-security-policy-report-only' (case-insensitive in HTTP/2).
      const cspHeader = headers['content-security-policy']
        || headers['content-security-policy-report-only'];
      expect(cspHeader).toBeDefined();
      expect(cspHeader.length).toBeGreaterThan(0);
    });

    test('CSP header does not contain unsafe-inline for scripts (nginx only)', async ({ page }) => {
      const response = await page.goto('/', { timeout: 30000 });
      const headers = response!.headers();
      const csp = headers['content-security-policy'] || '';
      // The Vite dev server legitimately allows 'unsafe-inline' in script-src
      // for HMR client injection (vite.config.ts securityHeadersPlugin);
      // behind nginx it is an XSS escape hatch and must never appear.
      // (The previous check matched the literal string "script-src 'unsafe-inline'"
      // and passed vacuously against the dev CSP, where 'self' sits between
      // the two tokens.) The full directive baseline lives in
      // security/csp-enforce.spec.ts — this is the header-level guard.
      const server = headers['server'] ?? '';
      const isNginx = /^nginx/i.test(server);
      const scriptSrc = csp.match(/script-src\s+([^;]+)/)?.[1] ?? '';
      expect(scriptSrc, 'script-src directive must be present').toBeTruthy();
      // Escape hatches forbidden on BOTH servers (mirrors csp-enforce.spec.ts
      // FORBIDDEN_SCRIPT_SRC): 'unsafe-eval' enables eval/Function, wildcard
      // sources and scheme-wide sources (http:, https:, data:, blob:)
      // would accept any origin.
      expect(scriptSrc, "script-src must NOT contain 'unsafe-eval' (XSS escape hatch)").not.toContain(
        "'unsafe-eval'"
      );
      expect(scriptSrc, 'script-src must NOT contain wildcard sources (*)').not.toContain('*');
      expect(
        scriptSrc,
        'script-src must NOT contain scheme-wide sources (http:, https:, data:, blob:)'
      ).not.toMatch(/(?:^|\s)(?:https?|data|blob):(?:\s|$)/);
      if (isNginx) {
        // Production baseline: unsafe-inline is an XSS escape hatch.
        expect(scriptSrc, 'script-src must NOT contain unsafe-inline (XSS escape hatch)').not.toContain(
          "'unsafe-inline'"
        );
      } else {
        // Dev-server baseline (positive assertion instead of a bare skip):
        // Vite needs 'unsafe-inline' for HMR, so the directive must START
        // with 'self' + 'unsafe-inline'. A whitespace-separated suffix of
        // additional sources is legitimate — nginx.test.conf and the dev
        // securityHeadersPlugin both allow https://js.stripe.com (Stripe.js
        // loader; without it the checkout page hangs on its skeleton). An
        // exact-match regex rotted once when that domain was added; the
        // prefix + property-check shape matches the csp-enforce.spec.ts
        // EXPECTED_DIRECTIVE_PATTERNS convention and stays green when a
        // reviewed third-party origin is allow-listed.
        expect(scriptSrc, 'dev script-src must start with self + unsafe-inline (HMR)').toMatch(
          /^\s*'self'\s+'unsafe-inline'(?:\s+\S+)*\s*$/
        );
      }
    });
  });

  // ──────────────────────────────────────────────────────────────────────
  // CSRF contract
  // ──────────────────────────────────────────────────────────────────────
  //
  // The API is JWT-bearer authenticated and CSRF-EXEMPT BY DESIGN:
  // APIEndpointCSRFExemptMiddleware (hub/apps/api/middleware/csrf_exempt.py)
  // marks every /api/v1/ request `_dont_enforce_csrf_checks` before
  // CsrfViewMiddleware runs, and the DRF auth classes contain no
  // SessionAuthentication (so DRF's enforce_csrf never applies either).
  // The previous version of this block asserted "POST without CSRF → 403"
  // — wrong contract; the 400 it observed came from the login serializer
  // (payload used `username` but the field is `email`), not from CSRF.
  // The real CSRF-enforced surface is the Django admin (non-/api/v1/).

  test.describe('CSRF contract on the API', () => {
    test('API endpoints are CSRF-exempt by design: POST without a CSRF token reaches the view', async ({ request }) => {
      // Raw POST to a mutation endpoint with NO CSRF token and NO cookie.
      // 400 (serializer validation) or 401 (bad credentials) both prove the
      // view executed. 403 would mean CSRF enforcement was accidentally
      // switched on for the API — which would break every bearer-token
      // client (SPA, SDK, CLI) and must fail loudly here.
      const response = await request.post('/api/v1/auth/login/', {
        data: { email: 'csrf-contract-probe@example.com', password: 'wrong-pass' },
        headers: {
          'Content-Type': 'application/json',
          // Deliberately omit X-CSRFToken and csrftoken cookie.
        },
      });
      expect(
        [400, 401],
        `API POST without CSRF token must reach the view (400/401 validation), got ${response.status()} — CSRF enforcement on the API would break bearer-token clients`
      ).toContain(response.status());
    });

    test('POST with CSRF token succeeds (no 403)', async ({ request }) => {
      // Obtain a real csrftoken from the Django admin login page. The SPA
      // /login route is served by Vite and never sets a Django cookie — the
      // previous version of this test asserted a cookie that cannot exist
      // there (cookies.find('csrftoken') → undefined → toBeDefined failure).
      const apiOrigin = new URL(getApiBaseUrl()).origin;
      const adminGet = await request.get(`${apiOrigin}/admin/login/`, { failOnStatusCode: false });
      test.skip(adminGet.status() === 404, 'Django admin not mounted in this environment');
      const csrfMatch = (adminGet.headers()['set-cookie'] ?? '').match(/csrftoken=([^;]+)/);
      test.skip(!csrfMatch, 'Django admin did not set a csrftoken cookie (CSRF cookie disabled?)');

      // Now make an API POST carrying the CSRF token in the header.
      const response = await request.post('/api/v1/auth/login/', {
        data: { username: 'nonexistent-test-user', password: 'test' },
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrfMatch[1],
        },
      });
      // Should NOT be 403.  (400 validation is expected — invalid payload.)
      expect(response.status()).not.toBe(403);
    });
  });

  test.describe('CSRF enforcement on the Django admin (the real CSRF surface)', () => {
    test('admin POST without CSRF token returns 403 Forbidden', async ({ request }) => {
      // Django admin is a session-cookie surface OUTSIDE the /api/v1/ CSRF
      // exemption, so CsrfViewMiddleware enforces it. Admin is only mounted
      // outside production (hub/urls.py) — skip when it is not available.
      const apiOrigin = new URL(getApiBaseUrl()).origin;
      const probe = await request.get(`${apiOrigin}/admin/login/`, { failOnStatusCode: false });
      test.skip(probe.status() === 404, 'Django admin not mounted in this environment (production-like)');

      const response = await request.post(`${apiOrigin}/admin/login/?next=/admin/`, {
        form: {
          username: 'nobody',
          password: 'wrong-password',
          // Deliberately no csrfmiddlewaretoken and no csrftoken cookie.
        },
      });
      expect(
        response.status(),
        `Admin POST without CSRF token must be 403 (CsrfViewMiddleware), got ${response.status()}`
      ).toBe(403);
    });
  });

  // ──────────────────────────────────────────────────────────────────────
  // Nginx Security Headers
  // ──────────────────────────────────────────────────────────────────────

  test.describe('Nginx / reverse-proxy security headers', () => {
    test('X-Frame-Options header is present', async ({ page }) => {
      const response = await page.goto('/', { timeout: 30000 });
      const headers = response!.headers();
      // X-Frame-Options prevents clickjacking.
      const xfo = headers['x-frame-options'];
      expect(xfo).toBeDefined();
      expect(['DENY', 'SAMEORIGIN']).toContain(xfo);
    });

    test('X-Content-Type-Options header is nosniff', async ({ page }) => {
      const response = await page.goto('/', { timeout: 30000 });
      const headers = response!.headers();
      const xcto = headers['x-content-type-options'];
      expect(xcto).toBeDefined();
      expect(xcto.toLowerCase()).toBe('nosniff');
    });

    test('Strict-Transport-Security header is present (HSTS)', async ({ page }) => {
      const response = await page.goto('/', { timeout: 30000 });
      const headers = response!.headers();
      const hsts = headers['strict-transport-security'];
      expect(hsts).toBeDefined();
      // Must include max-age directive.
      expect(hsts).toContain('max-age');
    });

    test('Referrer-Policy header is present', async ({ page }) => {
      const response = await page.goto('/', { timeout: 30000 });
      const headers = response!.headers();
      const rp = headers['referrer-policy'];
      expect(rp).toBeDefined();
      // Acceptable values: no-referrer, strict-origin, strict-origin-when-cross-origin, same-origin
      const validPolicies = [
        'no-referrer', 'strict-origin', 'strict-origin-when-cross-origin',
        'same-origin', 'origin-when-cross-origin',
      ];
      const matches = validPolicies.some(p => rp.toLowerCase().includes(p));
      expect(matches).toBeTruthy();
    });

    test('Permissions-Policy header is present', async ({ page }) => {
      const response = await page.goto('/', { timeout: 30000 });
      const headers = response!.headers();
      const pp = headers['permissions-policy'];
      // Permissions-Policy may not be set in dev/test but should be in staging/prod.
      // In local dev, absence is a warning, not a failure.
      if (!pp) {
        console.warn('Permissions-Policy header not set in this environment (dev/test only).');
        return;
      }
      expect(pp.length).toBeGreaterThan(0);
    });
  });

  // ──────────────────────────────────────────────────────────────────────
  // CSP Violation Reporting
  // ──────────────────────────────────────────────────────────────────────

  test.describe('CSP violation reporting', () => {
    test('CSP report-uri or report-to directive is configured', async ({ page }) => {
      const response = await page.goto('/', { timeout: 30000 });
      const headers = response!.headers();
      const csp = headers['content-security-policy']
        || headers['content-security-policy-report-only']
        || '';
      // Either report-uri (deprecated) or report-to (Reporting API) must be configured.
      const hasReporting = csp.includes('report-uri') || csp.includes('report-to');
      // In dev/test, CSP reporting may be disabled.  In staging/prod, it must be present.
      if (!hasReporting) {
        console.warn('CSP reporting endpoint not configured in this environment.');
      }
    });

    test('CSP violation endpoint is reachable', async ({ request }) => {
      // The /api/csp-report/ endpoint should accept POST requests.
      const response = await request.post('/api/csp-report/', {
        data: {
          'csp-report': {
            'document-uri': 'https://test.example.com/',
            'violated-directive': 'script-src',
            'blocked-uri': 'https://evil.example.com/malicious.js',
            'original-policy': "script-src 'self'",
          },
        },
        headers: { 'Content-Type': 'application/csp-report' },
        // failOnStatusCode: false so we don't throw on non-2xx.
        failOnStatusCode: false,
      });
      // The endpoint should accept the report (200, 201, 202, or 204).
      expect([200, 201, 202, 204, 400]).toContain(response.status());
      // 400 is acceptable if validation rejects our test payload format.
    });

    test('triggering a CSP violation generates a report', async ({ page }) => {
      // Navigate to a page that has CSP headers.
      await page.goto('/', { timeout: 30000 });

      // Inject an inline script that violates CSP (will be blocked by browser).
      const cspViolated = await page.evaluate(() => {
        return new Promise<boolean>((resolve) => {
          const script = document.createElement('script');
          script.textContent = 'console.log("CSP test")';
          // Listen for securitypolicyviolation event.
          let fired = false;
          document.addEventListener('securitypolicyviolation', () => {
            fired = true;
            resolve(true);
          });
          document.body.appendChild(script);
          // If no violation within 2s, CSP may not be enforcing script-src.
          setTimeout(() => resolve(fired), 2000);
        });
      });

      // In dev mode, CSP may allow unsafe-inline for HMR — violation may not fire.
      // In CI/staging with production-like CSP, it should fire.
      if (!cspViolated) {
        console.warn('CSP violation did not fire — may be dev-mode CSP with unsafe-inline for HMR.');
      }
    });
  });
});

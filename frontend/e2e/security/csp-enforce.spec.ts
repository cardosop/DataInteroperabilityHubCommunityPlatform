/**
 * E2E Security: CSP Enforce Mode (Phase 14 / task 7.7)
 *
 * Verifies that the nginx frontend sends `Content-Security-Policy` (enforce mode)
 * and NOT `Content-Security-Policy-Report-Only` on HTML responses.
 *
 * Tests use Playwright's `request` API so they hit the real nginx container
 * rather than the browser's network stack — this gives us the raw response
 * headers without any browser preprocessing.
 *
 * These tests do NOT require authentication: the root path `/` returns the
 * SPA shell with security headers before any auth check is performed.
 */

import { expect, test } from '@playwright/test';

const CSP_ENFORCE_HEADER = 'content-security-policy';
const CSP_REPORT_ONLY_HEADER = 'content-security-policy-report-only';

// Expected CSP directives — matches nginx.conf and nginx.test.conf, with the
// security baseline encoded as regex so environment-specific extensions are
// allowed without breaking the assertion.
//
// Why regex (not exact-match strings):
//   nginx.conf line 79 emits `connect-src 'self' ${API_HOST}` where `${API_HOST}`
//   is substituted by envsubst at container startup. On staging, ${API_HOST}
//   resolves to e.g. `https://api.stagingmeshant-internal.example.com`, so an exact-match
//   `connect-src 'self'` assertion would fail. The regex below requires the
//   directive PREFIX (`'self'`) but allows any whitespace-separated suffix.
//
// Each entry MUST satisfy:
//   - The required source list keywords (e.g. `'self'` for default-src)
//   - May be followed by ANY whitespace-separated additional sources
//   - Must terminate with `;` or end-of-string (so we don't accidentally
//     match a directive that starts with the same name but has wrong scope).
const EXPECTED_DIRECTIVE_PATTERNS: { name: string; pattern: RegExp }[] = [
  // Trailing `\s*` before the `;|$` accommodates the case where envsubst
  // expands an empty `${API_HOST}` into `connect-src 'self' ;` with a space
  // before the semicolon (nginx.conf:79). The regex must accept that exact
  // shape rather than fail on the legitimate same-origin-only configuration.
  { name: "default-src 'self'", pattern: /default-src\s+'self'(?:\s+[^;]+)?\s*(?:;|$)/ },
  { name: "script-src 'self'", pattern: /script-src\s+'self'(?:\s+[^;]+)?\s*(?:;|$)/ },
  { name: "style-src 'self' 'unsafe-inline'", pattern: /style-src\s+'self'\s+'unsafe-inline'(?:\s+[^;]+)?\s*(?:;|$)/ },
  { name: "img-src 'self' data: blob:", pattern: /img-src\s+'self'\s+data:\s+blob:(?:\s+[^;]+)?\s*(?:;|$)/ },
  { name: "connect-src 'self'", pattern: /connect-src\s+'self'(?:\s+[^;]+)?\s*(?:;|$)/ },
  { name: 'report-uri /api/csp-report/', pattern: /report-uri\s+\/api\/csp-report\/\s*(?:;|$)/ },
];

// Sources that MUST NEVER appear in script-src (security regression guards)
const FORBIDDEN_SCRIPT_SRC = ["'unsafe-eval'", "'unsafe-inline'"] as const;

test.describe('Security: CSP enforce mode (Phase 14 / task 7.7)', () => {
  // CSP headers are served by Nginx, not Vite dev server.
  // Skip the entire suite when running against Vite (dev mode).
  test.beforeEach(async ({ request }) => {
    const probe = await request.get('/');
    const server = probe.headers()['server'] ?? '';
    const hasCSP = !!probe.headers()[CSP_ENFORCE_HEADER];
    // Vite dev server identifies as empty or 'vite'; Nginx identifies as 'nginx/...'
    const isNginx = /nginx/i.test(server) || hasCSP;
    test.skip(!isNginx, 'CSP headers only present behind Nginx — Vite dev server does not serve them');
  });

  test('/ returns Content-Security-Policy (enforce), not Report-Only', async ({ request }) => {
    const response = await request.get('/');
    expect(response.ok()).toBeTruthy();

    const headers = response.headers();

    // Enforce header MUST be present
    expect(
      headers[CSP_ENFORCE_HEADER],
      'Expected Content-Security-Policy enforce header to be present',
    ).toBeTruthy();

    // Report-Only header MUST NOT be present (was the old mode)
    expect(
      headers[CSP_REPORT_ONLY_HEADER],
      'Expected Content-Security-Policy-Report-Only header to be absent (enforce mode active)',
    ).toBeFalsy();
  });

  test('CSP enforce header contains all required directives (env-agnostic)', async ({ request }) => {
    const response = await request.get('/');
    expect(response.ok()).toBeTruthy();

    const csp = response.headers()[CSP_ENFORCE_HEADER];
    expect(csp, 'Content-Security-Policy header must be present').toBeTruthy();

    // Use regex assertions so environment-specific source additions
    // (e.g. `${API_HOST}` in connect-src on staging, fonts.googleapis.com
    // in style-src in test) don't break the security baseline check.
    for (const { name, pattern } of EXPECTED_DIRECTIVE_PATTERNS) {
      expect(
        csp!,
        `CSP must contain directive matching: ${name} (regex: ${pattern})`,
      ).toMatch(pattern);
    }

    // Negative assertions: script-src must NEVER allow unsafe-eval or unsafe-inline.
    // These are XSS escape hatches and were the cause of the staging regression
    // we hit during Phase 213.A (Playwright's `page.waitForFunction` with a
    // string argument triggers eval()).
    const scriptSrcMatch = csp!.match(/script-src\s+([^;]+)/);
    expect(scriptSrcMatch, 'script-src directive must be present').toBeTruthy();
    const scriptSrcValue = scriptSrcMatch![1];
    for (const forbidden of FORBIDDEN_SCRIPT_SRC) {
      expect(
        scriptSrcValue,
        `script-src must NOT contain ${forbidden} (XSS escape hatch)`,
      ).not.toContain(forbidden);
    }
  });

  test('static asset responses do not include Report-Only CSP', async ({ request }) => {
    // Static assets are served by the ~*.(js|css|...) location block which
    // sets Cache-Control/X-Content-Type-Options but must not add a Report-Only
    // header that would shadow the enforce header on full-page navigations.
    //
    // We request a known static path; if it 404s (build not present) we skip —
    // the header configuration is static and not build-dependent.
    const response = await request.get('/assets/', { failOnStatusCode: false });
    const headers = response.headers();

    expect(
      headers[CSP_REPORT_ONLY_HEADER],
      'Static asset location must not send Report-Only CSP',
    ).toBeFalsy();
  });

  test('X-Frame-Options is DENY on root response', async ({ request }) => {
    // Sanity-check that security headers are present alongside CSP enforce.
    const response = await request.get('/');
    expect(response.headers()['x-frame-options']).toBe('DENY');
  });

  test('X-Content-Type-Options is nosniff on root response', async ({ request }) => {
    const response = await request.get('/');
    expect(response.headers()['x-content-type-options']).toBe('nosniff');
  });

  test('Strict-Transport-Security present on root response', async ({ request }) => {
    const response = await request.get('/');
    const hsts = response.headers()['strict-transport-security'];
    expect(hsts).toBeTruthy();
    expect(hsts).toContain('max-age=31536000');
    expect(hsts).toContain('includeSubDomains');
  });
});

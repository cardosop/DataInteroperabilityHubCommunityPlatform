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

// Expected CSP directives — matches nginx.conf and nginx.test.conf
// style-src includes fonts.googleapis.com for Google Fonts loaded in index.html.
// font-src includes fonts.gstatic.com for actual font file downloads.
// connect-src includes localhost:9010 for MinIO presigned uploads in test env.
const EXPECTED_DIRECTIVES = [
  "default-src 'self'",
  "script-src 'self'",
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: blob:",
  "connect-src 'self'",
  'report-uri /api/csp-report/',
];
// Note: style-src also allows https://fonts.googleapis.com, font-src allows
// https://fonts.gstatic.com, and connect-src allows http://localhost:9010 in
// test/dev. These are not asserted here because they are environment-specific
// additions; the core directives above are the security baseline.

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

  test('CSP enforce header contains all required directives', async ({ request }) => {
    const response = await request.get('/');
    expect(response.ok()).toBeTruthy();

    const csp = response.headers()[CSP_ENFORCE_HEADER];
    expect(csp, 'Content-Security-Policy header must be present').toBeTruthy();

    for (const directive of EXPECTED_DIRECTIVES) {
      expect(
        csp,
        `CSP must contain directive: ${directive}`,
      ).toContain(directive);
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

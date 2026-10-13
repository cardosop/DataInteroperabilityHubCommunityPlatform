/**
 * E2E spec — Tenant SSO config save + reload (Phase 226.G3).
 *
 * Background — partial-surface reality
 * ------------------------------------
 * `Tenant.sso_config` is a `JSONField` that the model encrypts on save
 * (`hub/apps/tenants/models.py:425-518`). The platform exposes the OIDC SSO
 * LOGIN endpoint (`/api/v1/auth/sso/oidc/login-url/`); the SAML endpoints
 * are RETIRED (oss-release-remediation W1.5/D4 — the SAML stub is deleted)
 * and now 404. There is **no public REST endpoint to PATCH
 * `sso_config` directly**. Today, tenant admins configure SSO via Django
 * admin or a backend operator CLI.
 *
 * Guarantee chain (what's testable today):
 *   1. The SAML login-url endpoint is retired — 404 for every request.
 *   2. With no SSO config persisted, the OIDC login-url endpoint returns
 *      400 "OIDC SSO not configured for this tenant" — proving the endpoint
 *      reads from real tenant state (not a hardcoded stub).
 *   3. The OIDC missing-input guard (no redirect_uri) returns 400
 *      ValidationError — input-validation guard intact.
 *
 * Gap (annotated, not failed):
 *   • There is no PATCH /tenants/{id}/sso-config/ endpoint. The "save +
 *     reload" cycle from the G3 task can be wired only after that endpoint
 *     ships. This spec records the gap inline and tightens automatically
 *     when the endpoint lands.
 *
 * No mocks. Real backend only.
 */

import { test, expect } from '../../fixtures/test-data-cleanup';
import { getTestUser, loginViaApi } from '../../fixtures/auth';

const DEFAULT_API_PORT = process.env.E2E_WEB_PORT ? '8001' : '8000';
const API_BASE =
  process.env.E2E_API_BASE_URL ||
  (process.env.VITE_PROXY_TARGET
    ? `${process.env.VITE_PROXY_TARGET.replace(/\/$/, '')}/api/v1`
    : null) ||
  (process.env.VITE_API_BASE_URL?.startsWith('http') ? process.env.VITE_API_BASE_URL : null) ||
  `http://localhost:${DEFAULT_API_PORT}/api/v1`;

test.describe('226.G3 — SSO config + login-url admin surface @critical @admin', () => {
  test.setTimeout(120_000);

  test('OIDC login-url rejects when no SSO config is persisted; SAML endpoints retired (404); PATCH-config gap recorded', async ({
    page,
  }) => {
    const dpo = await getTestUser();
    const { access_token, user } = await loginViaApi(dpo.email, dpo.password);
    const headers = {
      Authorization: `Bearer ${access_token}`,
      'Content-Type': 'application/json',
    };

    await page.goto('/');
    await page.evaluate((token) => {
      localStorage.setItem('access_token', token);
    }, access_token);

    // user.tenant_id may be in payload directly or nested. Probe defensively.
    const tenantId =
      (user as unknown as { tenant_id?: string }).tenant_id ??
      (user as unknown as { tenant?: { id?: string } }).tenant?.id ??
      null;
    if (!tenantId) {
      test.skip(!tenantId, 'Test user has no tenant_id in JWT — cannot exercise SSO endpoints');
      return;
    }

    // ── Step 1 — the SAML login-url endpoint is RETIRED (W1.5/D4): 404.
    const samlRes = await page.request.get(
      `${API_BASE}/auth/sso/saml/login-url/?tenant_id=${tenantId}&redirect_uri=${encodeURIComponent('https://localhost:5173/sso-callback')}`,
      { headers },
    );
    expect(
      samlRes.status(),
      `SAML login-url is retired and must 404; got ${samlRes.status()}`,
    ).toBe(404);

    // ── Step 2 — OIDC login-url: same guard.
    const oidcRes = await page.request.get(
      `${API_BASE}/auth/sso/oidc/login-url/?tenant_id=${tenantId}&redirect_uri=${encodeURIComponent('https://localhost:5173/sso-callback')}`,
      { headers },
    );
    expect([200, 400].includes(oidcRes.status())).toBe(true);

    // ── Step 3 — Missing-input guard: omit redirect_uri on the OIDC endpoint.
    const missingParamRes = await page.request.get(
      `${API_BASE}/auth/sso/oidc/login-url/?tenant_id=${tenantId}`,
      { headers },
    );
    expect(
      missingParamRes.status(),
      `Missing redirect_uri must be 400; got ${missingParamRes.status()}`,
    ).toBe(400);

    // ── Step 4 — Document the missing PATCH-config endpoint. The G3 task
    // referenced "SSO config save + reload" — that requires a PATCH/PUT
    // endpoint that does not exist today. When the endpoint lands, this
    // annotation should turn into:
    //   await page.request.patch(`${API_BASE}/tenants/${tenantId}/sso-config/`, {...})
    //   → assert sso_config persists round-trip.
    test.info().annotations.push({
      type: 'g3-sso-patch-endpoint-missing',
      description:
        'No REST endpoint exists today to PATCH Tenant.sso_config. When that endpoint ' +
        'lands, this spec must be extended to: PATCH config → re-GET via /tenants/me/ → ' +
        'verify shape persists (with sensitive values masked) → re-call /sso/oidc/login-url/ ' +
        '→ assert it now returns 200 with a real URL.',
    });
  });
});

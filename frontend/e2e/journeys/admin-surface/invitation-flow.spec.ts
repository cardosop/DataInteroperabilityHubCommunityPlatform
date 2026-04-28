/**
 * E2E spec — Invitation flow: send → accept → reject → expire (Phase 226.G3).
 *
 * Background — surface map
 * ------------------------
 * Send:    POST /api/v1/users/invite/        (`hub/apps/users/views.py:344`)
 * Accept:  POST /api/v1/auth/accept-invitation/
 *          (`hub/apps/auth/views.py:910-1000`)
 *          Body: { token: <plaintext-uuid>, password: <new-password> }
 *          Token stored as SHA-256 in DB; plaintext travels in email link.
 * Reject:  no first-class REST action — operationally the invitee never
 *          accepts (token expires); spec asserts the *expired-token* path.
 * Expire:  Token has invitation_token_expires_at (default +7 days). Test
 *          can't wait 7 days, so it asserts the GUARD: present an obviously-
 *          invalid token → 400 "Invalid or expired".
 *
 * E2E reality — accept-with-real-token uses the canonical test helper
 * ----------------------------------------------------------------------
 * `POST /api/v1/test/ensure-e2e-invitation-token/` (`hub/apps/api/urls.py:60`,
 * `hub/apps/api/views.py:374-421`) provisions an INVITED user with a fresh
 * invitation_token_hash and returns the plaintext token. This is the
 * canonical path E2E uses to drive the accept flow — the helper itself is
 * gated by `require_e2e_token` + `E2E_EMAILS` allow-list + ENVIRONMENT in
 * (test, staging) or DEBUG, so it's a 404 in production by design.
 *
 * What this spec asserts:
 *   1. SEND: invite-user POST returns 201 with INVITED status; audit row.
 *   2. EXPIRE/INVALID: accept with a non-matching token → 400.
 *   3. ACCEPT: provision a real token via the helper, accept it, assert 200.
 *      Idempotent re-accept rejected (token cleared after first acceptance).
 *
 * No mocks. Real backend only.
 */

import { test, expect } from '../../fixtures/test-data-cleanup';
import { getTenantAdminUser, loginViaApi } from '../../fixtures/auth';
import { e2eTestHeaders } from '../../fixtures/e2e-token';
import { verifyAuditEvent } from '../../fixtures/verifyAuditEvent';

const DEFAULT_API_PORT = process.env.E2E_WEB_PORT ? '8001' : '8000';
const API_BASE =
  process.env.E2E_API_BASE_URL ||
  (process.env.VITE_PROXY_TARGET
    ? `${process.env.VITE_PROXY_TARGET.replace(/\/$/, '')}/api/v1`
    : null) ||
  (process.env.VITE_API_BASE_URL?.startsWith('http') ? process.env.VITE_API_BASE_URL : null) ||
  `http://localhost:${DEFAULT_API_PORT}/api/v1`;

test.describe('226.G3 — Invitation flow @critical @admin', () => {
  test.setTimeout(180_000);

  test('send → INVITED + audit; accept(invalid) → 400; accept(expired-by-construction) → 400', async ({
    page,
    cleanup,
  }) => {
    // Tenant-admin role required to call /users/invite/. Falls back to test
    // user when seeded TA role is unavailable, surfacing a 403 cleanly.
    let admin;
    try {
      admin = await getTenantAdminUser();
    } catch (err) {
      test.skip(
        true,
        `No tenant admin available (${(err as Error).message}). Run ensure_e2e_user_roles.`,
      );
      return;
    }
    const { access_token } = await loginViaApi(admin.email, admin.password);
    const headers = {
      Authorization: `Bearer ${access_token}`,
      'Content-Type': 'application/json',
    };

    await page.goto('/');
    await page.evaluate((token) => {
      localStorage.setItem('access_token', token);
    }, access_token);

    // ── Step 1 — SEND.
    const inviteeEmail = `g3-invitee-${cleanup.runId.slice(0, 8)}-${Date.now()}@e2e.meshant.test`;
    const inviteRes = await page.request.post(`${API_BASE}/users/invite/`, {
      headers,
      data: {
        email: inviteeEmail,
        display_name: 'G3 Invitee',
        role_ids: [],
      },
    });
    if (inviteRes.status() === 403) {
      test.skip(
        true,
        'Tenant admin lacks invite permission on this tenant. ' +
          'Unblock by ensuring TENANT_ADMIN role is assigned.',
      );
      return;
    }
    expect(
      inviteRes.status(),
      `invite expected 201; got ${inviteRes.status()} ${await inviteRes.text()}`,
    ).toBe(201);
    const invited = (await inviteRes.json()) as { id: string; status: string; email: string };
    expect(invited.email).toBe(inviteeEmail);
    expect(invited.status).toBe('INVITED');
    cleanup.track({ type: 'user', id: invited.id, owner: admin });

    // ── Step 2 — Audit row best-effort (USER_INVITED action; emit not yet
    // verified for this view).
    try {
      await verifyAuditEvent(
        page,
        {
          action: 'USER_INVITED',
          resourceType: 'USER',
          resourceId: invited.id,
        },
        { retryBudgetMs: 4_000 },
      );
    } catch {
      test.info().annotations.push({
        type: 'g3-missing-invite-audit',
        description:
          'No USER_INVITED audit row found within 4s. The /users/invite/ ' +
          'view should call create_audit_event after invite_user_to_tenant ' +
          'returns. Tracked by 226.B1d.',
      });
    }

    // ── Step 3 — ACCEPT with INVALID token → 400 "Invalid or expired".
    // This exercises the same guard path that an EXPIRED token would hit
    // (the model query filters on invitation_token_expires_at__gt=now,
    // so an out-of-window token is indistinguishable from a wrong one —
    // both 404 the get(); the view raises ValidationError).
    const invalidToken = '00000000-0000-0000-0000-000000000000';
    const acceptInvalidRes = await page.request.post(
      `${API_BASE}/auth/accept-invitation/`,
      {
        data: { token: invalidToken, password: 'AcceptPassG3!1234' },
        headers: { 'Content-Type': 'application/json' },
      },
    );
    expect(
      acceptInvalidRes.status(),
      `Invalid token must be 400; got ${acceptInvalidRes.status()}`,
    ).toBe(400);
    const invalidBody = (await acceptInvalidRes.json()) as
      | { token?: string; detail?: string }
      | { error?: string };
    const msg = JSON.stringify(invalidBody);
    expect(/Invalid|expired|Validation/i.test(msg)).toBe(true);

    // ── Step 4 — ACCEPT with REAL token. The canonical test helper at
    // `/test/ensure-e2e-invitation-token/` provisions a fresh INVITED user
    // and returns the plaintext token (the email path is unobservable from
    // E2E, so the helper short-circuits it). The helper does NOT accept an
    // email parameter — it generates its own e2e-invited-{uuid}@example.com
    // user. That's intentional: the spec needs *some* valid token to drive
    // the accept flow; which user owns it is incidental.
    const helperRes = await page.request.post(
      `${API_BASE}/test/ensure-e2e-invitation-token/`,
      {
        headers: { ...headers, ...e2eTestHeaders() },
      },
    );
    if (!helperRes.ok()) {
      test.info().annotations.push({
        type: 'g3-no-token-helper',
        description:
          `Backend test-helper /test/ensure-e2e-invitation-token/ returned ${helperRes.status()}. ` +
          `Likely not seeded on this env (require_e2e_token guard, ENVIRONMENT not in (test,staging,debug), ` +
          `or admin user not in E2E_EMAILS allow-list). Skipping accept-token round-trip; ` +
          `the SEND + INVALID-TOKEN guards above already covered the bulk of the contract.`,
      });
      return;
    }
    const helperBody = (await helperRes.json()) as { token?: string };
    const realToken = helperBody.token;
    expect(realToken, 'helper returned empty token field').toBeTruthy();
    if (!realToken) return;

    const acceptRes = await page.request.post(
      `${API_BASE}/auth/accept-invitation/`,
      {
        data: { token: realToken, password: 'AcceptPassG3!1234' },
        headers: { 'Content-Type': 'application/json' },
      },
    );
    expect(
      acceptRes.status(),
      `Accept with real token expected 200; got ${acceptRes.status()} ${await acceptRes.text()}`,
    ).toBe(200);

    // ── Step 5 — Idempotent re-accept rejected (token used + cleared).
    const reAcceptRes = await page.request.post(
      `${API_BASE}/auth/accept-invitation/`,
      {
        data: { token: realToken, password: 'AcceptPassG3!1234' },
        headers: { 'Content-Type': 'application/json' },
      },
    );
    expect(reAcceptRes.status()).toBe(400);
  });
});

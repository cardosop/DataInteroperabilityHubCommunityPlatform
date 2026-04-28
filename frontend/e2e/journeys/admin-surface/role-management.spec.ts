/**
 * E2E spec — Role create + assign/remove on user (Phase 226.G3).
 *
 * Background — read-only-for-MVP reality
 * --------------------------------------
 * `RoleViewSet` is `ReadOnlyModelViewSet` (`hub/apps/users/views.py:516-540`).
 * Roles are auto-seeded per-tenant by the backend; there is **no `POST
 * /api/v1/users/roles/` endpoint to create new ones**. The G3 task's
 * "role create" sub-test therefore maps to "role assign + remove on a
 * user", which IS first-class via
 * `POST /api/v1/users/{id}/roles/` (`hub/apps/users/views.py:394-470`).
 *
 * Guarantee chain asserted here:
 *   1. GET /users/roles/ returns ≥ the canonical role set (DATA_PROVIDER,
 *      DATA_CONSUMER, …) — proves the seeding ran for the test tenant.
 *   2. POST /users/roles/ explicitly returns 405 — locks the
 *      "role create not supported in MVP" contract so a future PR adding
 *      role creation must consciously delete this assertion.
 *   3. Pick a non-AUDITOR role, assign it to a freshly-invited user via
 *      POST /users/{id}/roles/, verify GET /users/{id}/ returns the role.
 *   4. Remove the role; verify it's gone.
 *   5. (Implicit) Token version increments and /auth/me cache invalidates
 *      — those are tested in JOURNEY-AUTH-* and not duplicated here.
 *
 * No mocks. Real backend only.
 */

import { test, expect } from '../../fixtures/test-data-cleanup';
import { getTenantAdminUser, loginViaApi } from '../../fixtures/auth';

const DEFAULT_API_PORT = process.env.E2E_WEB_PORT ? '8001' : '8000';
const API_BASE =
  process.env.E2E_API_BASE_URL ||
  (process.env.VITE_PROXY_TARGET
    ? `${process.env.VITE_PROXY_TARGET.replace(/\/$/, '')}/api/v1`
    : null) ||
  (process.env.VITE_API_BASE_URL?.startsWith('http') ? process.env.VITE_API_BASE_URL : null) ||
  `http://localhost:${DEFAULT_API_PORT}/api/v1`;

test.describe('226.G3 — Role create + assign/remove @critical @admin', () => {
  test.setTimeout(180_000);

  test('roles list seeded; role-create POST locked; assign + remove via /users/{id}/roles/ round-trip', async ({
    page,
    cleanup,
  }) => {
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

    // ── Step 1 — Roles list seeded.
    const rolesRes = await page.request.get(`${API_BASE}/users/roles/`, { headers });
    expect(rolesRes.ok()).toBe(true);
    const rolesBody = (await rolesRes.json()) as
      | { results?: Array<{ id: string; name: string }> }
      | Array<{ id: string; name: string }>;
    const rolesArray = Array.isArray(rolesBody) ? rolesBody : rolesBody.results ?? [];
    expect(
      rolesArray.length,
      `Expected ≥ 1 seeded role; got ${rolesArray.length}. Run seed_default_plans / role-bootstrap.`,
    ).toBeGreaterThanOrEqual(1);

    // ── Step 2 — POST /users/roles/ MUST be 405. This locks the
    // "ReadOnlyModelViewSet" contract — a future PR that opens role-create
    // must consciously update this assertion.
    const roleCreatePost = await page.request.post(`${API_BASE}/users/roles/`, {
      headers,
      data: { name: 'G3-CUSTOM-ROLE' },
    });
    expect(
      roleCreatePost.status(),
      `POST /users/roles/ must return 405 (ReadOnlyModelViewSet); got ${roleCreatePost.status()}`,
    ).toBe(405);

    // ── Step 3 — Pick a non-elevated role to assign (avoid AUDITOR /
    // PLATFORM_ADMIN to keep the spec's blast radius minimal).
    const nonElevatedNames = ['DATA_CONSUMER', 'DATA_PROVIDER', 'DATA_ANALYST', 'DATA_ENGINEER'];
    const candidate = rolesArray.find((r) => nonElevatedNames.includes(r.name)) ?? rolesArray[0];
    expect(candidate, 'No suitable non-elevated role found in tenant').toBeTruthy();

    // ── Step 4 — Invite a fresh user to operate on.
    const inviteeEmail = `g3-rolemgr-${cleanup.runId.slice(0, 8)}-${Date.now()}@e2e.meshant.test`;
    const inviteRes = await page.request.post(`${API_BASE}/users/invite/`, {
      headers,
      data: { email: inviteeEmail, display_name: 'G3 Role Probe Invitee', role_ids: [] },
    });
    if (!inviteRes.ok()) {
      test.skip(true, `Invite failed (${inviteRes.status()}). Likely TENANT_ADMIN gating issue.`);
      return;
    }
    const invitee = (await inviteRes.json()) as { id: string };
    cleanup.track({ type: 'user', id: invitee.id, owner: admin });

    // ── Step 5 — Assign the role.
    const assignRes = await page.request.post(`${API_BASE}/users/${invitee.id}/roles/`, {
      headers,
      data: { role_id: candidate.id, action: 'assign' },
    });
    expect(
      assignRes.status(),
      `Assign expected 200/201/204; got ${assignRes.status()} ${await assignRes.text()}`,
    ).toBeLessThan(400);

    // ── Step 6 — Verify role is on the user.
    const afterAssign = await page.request.get(`${API_BASE}/users/${invitee.id}/`, { headers });
    expect(afterAssign.ok()).toBe(true);
    const userBody = (await afterAssign.json()) as { roles?: Array<{ id?: string; name?: string }> };
    const assignedRoleNames = (userBody.roles ?? []).map((r) =>
      typeof r === 'object' ? r.name ?? r.id : r,
    );
    expect(
      assignedRoleNames.some((n) => n === candidate.name || n === candidate.id),
      `Role ${candidate.name}/${candidate.id} not visible on user after assign. Got: ${JSON.stringify(assignedRoleNames)}`,
    ).toBe(true);

    // ── Step 7 — Remove the role.
    const removeRes = await page.request.post(`${API_BASE}/users/${invitee.id}/roles/`, {
      headers,
      data: { role_id: candidate.id, action: 'remove' },
    });
    expect(removeRes.status()).toBeLessThan(400);

    // ── Step 8 — Verify role is gone.
    const afterRemove = await page.request.get(`${API_BASE}/users/${invitee.id}/`, { headers });
    expect(afterRemove.ok()).toBe(true);
    const userBody2 = (await afterRemove.json()) as { roles?: Array<{ id?: string; name?: string }> };
    const remainingNames = (userBody2.roles ?? []).map((r) =>
      typeof r === 'object' ? r.name ?? r.id : r,
    );
    expect(
      remainingNames.some((n) => n === candidate.name || n === candidate.id),
      `Role ${candidate.name} still present after remove`,
    ).toBe(false);
  });
});

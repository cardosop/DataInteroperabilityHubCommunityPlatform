/**
 * E2E API helpers for user management (invite, accept invitation, role assignment, user lookup).
 * Follows the same pattern as api-assets.ts — real backend only, no mocks.
 */

import type { TestUser } from '../setup/create-test-user';

const DEFAULT_API_PORT = process.env.E2E_WEB_PORT ? '8001' : '8000';
let API_BASE_URL =
  process.env.E2E_API_BASE_URL ||
  (process.env.VITE_PROXY_TARGET
    ? `${process.env.VITE_PROXY_TARGET.replace(/\/$/, '')}/api/v1`
    : null) ||
  `http://localhost:${DEFAULT_API_PORT}/api/v1`;

function isTransientConnectionError(err: unknown): boolean {
  const msg = err instanceof Error ? err.message : String(err);
  if (/fetch failed|terminated|network/i.test(msg)) return true;
  const cause = err && typeof err === 'object' && (err as { cause?: unknown }).cause;
  if (cause && typeof cause === 'object') {
    const c = cause as { code?: string; message?: string };
    if (c.code === 'ECONNRESET' || c.code === 'UND_ERR_SOCKET') return true;
    if (typeof c.message === 'string' && /other side closed|socket hang up/i.test(c.message))
      return true;
  }
  return false;
}

const RETRIES = 3;
const RETRY_DELAYS_MS = [2000, 4000, 6000];

async function loginViaApiUsers(user: TestUser): Promise<string> {
  for (let r = 0; r < RETRIES; r++) {
    try {
      const response = await fetch(`${API_BASE_URL}/auth/login/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: user.email, password: user.password }),
      });
      if (!response.ok) {
        const body = await response.text().catch(() => '');
        throw new Error(`Login failed: ${response.status} ${body}`);
      }
      const data = (await response.json()) as { access_token?: string };
      if (!data.access_token) throw new Error('Login response missing access_token');
      return data.access_token;
    } catch (err) {
      if (r < RETRIES - 1 && isTransientConnectionError(err)) {
        await new Promise((resolve) => setTimeout(resolve, RETRY_DELAYS_MS[r]));
        continue;
      }
      throw err;
    }
  }
  throw new Error('loginViaApiUsers: exhausted retries');
}

/**
 * Invite a user to the current tenant. Calls POST /auth/invite/ or
 * POST /admin/users/invite/ depending on the API shape.
 * Returns the new user's ID (and invitation token if the API exposes it).
 */
export async function inviteUserViaApi(
  adminUser: TestUser,
  email: string,
  role: string
): Promise<{ userId: string; invitationToken?: string }> {
  const token = await loginViaApiUsers(adminUser);
  const headers = {
    'Content-Type': 'application/json',
    Authorization: `Bearer ${token}`,
  };

  // Try primary invite endpoint
  const inviteEndpoints = ['/auth/invite/', '/admin/users/invite/', '/users/invite/'];
  let lastError: unknown;

  for (const endpoint of inviteEndpoints) {
    const resp = await fetch(`${API_BASE_URL}${endpoint}`, {
      method: 'POST',
      headers,
      body: JSON.stringify({ email, role }),
    });
    if (resp.status === 404) continue; // Try next endpoint
    if (!resp.ok) {
      const body = await resp.text().catch(() => '');
      lastError = new Error(`Invite user failed: ${resp.status} ${body}`);
      continue;
    }
    const data = (await resp.json()) as {
      id?: string;
      user_id?: string;
      invitation_token?: string;
      token?: string;
    };
    const userId = data.id || data.user_id;
    if (!userId) throw new Error('Invite response missing user id');
    return { userId, invitationToken: data.invitation_token || data.token };
  }

  // Fallback: create user directly via admin API
  const createResp = await fetch(`${API_BASE_URL}/admin/users/`, {
    method: 'POST',
    headers,
    body: JSON.stringify({ email, role, password: 'TempPass123!' }),
  });
  if (!createResp.ok) {
    const body = await createResp.text().catch(() => '');
    throw lastError || new Error(`Create user fallback failed: ${createResp.status} ${body}`);
  }
  const data = (await createResp.json()) as { id?: string };
  if (!data.id) throw new Error('Create user response missing id');
  return { userId: data.id };
}

/**
 * Accept an invitation using the token from the invitation flow.
 * First tries GET /test/get-invitation-token/?email=... (test-env endpoint)
 * to avoid requiring a real email server.
 * Falls back to POST /auth/accept-invitation/ with the provided token.
 */
export async function acceptInvitationViaApi(
  tokenOrEmail: string,
  password: string
): Promise<void> {
  let inviteToken = tokenOrEmail;

  // If tokenOrEmail looks like an email address, try the test endpoint to get the token
  if (tokenOrEmail.includes('@')) {
    const testTokenResp = await fetch(
      `${API_BASE_URL}/test/get-invitation-token/?email=${encodeURIComponent(tokenOrEmail)}`
    ).catch(() => null);
    if (testTokenResp && testTokenResp.ok) {
      const data = (await testTokenResp.json()) as { token?: string };
      if (data.token) inviteToken = data.token;
    }
  }

  const endpoints = ['/auth/accept-invitation/', '/auth/activate/'];
  for (const endpoint of endpoints) {
    const resp = await fetch(`${API_BASE_URL}${endpoint}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ token: inviteToken, password }),
    });
    if (resp.status === 404) continue;
    if (!resp.ok) {
      const body = await resp.text().catch(() => '');
      throw new Error(`Accept invitation failed: ${resp.status} ${body}`);
    }
    return;
  }
  throw new Error('acceptInvitationViaApi: no valid endpoint found');
}

/**
 * Assign roles to a user. Calls PATCH /admin/users/{userId}/ with { roles }.
 * Verifies 200 response.
 */
export async function assignRolesViaApi(
  adminUser: TestUser,
  userId: string,
  roles: string[]
): Promise<void> {
  const token = await loginViaApiUsers(adminUser);
  const headers = {
    'Content-Type': 'application/json',
    Authorization: `Bearer ${token}`,
  };

  const endpoints = [`/admin/users/${userId}/`, `/users/${userId}/`];
  for (const endpoint of endpoints) {
    const resp = await fetch(`${API_BASE_URL}${endpoint}`, {
      method: 'PATCH',
      headers,
      body: JSON.stringify({ roles }),
    });
    if (resp.status === 404) continue;
    if (!resp.ok) {
      const body = await resp.text().catch(() => '');
      throw new Error(`assignRolesViaApi failed: ${resp.status} ${body}`);
    }
    return;
  }
  throw new Error('assignRolesViaApi: no valid endpoint found');
}

/**
 * Get a user by email from the admin API.
 * Returns { id, email, roles }.
 */
export async function getUserByEmailViaApi(
  adminUser: TestUser,
  email: string
): Promise<{ id: string; email: string; roles: string[] }> {
  const token = await loginViaApiUsers(adminUser);
  const headers = { Authorization: `Bearer ${token}` };

  const endpoints = [
    `/admin/users/?email=${encodeURIComponent(email)}`,
    `/users/?email=${encodeURIComponent(email)}`,
  ];

  for (const endpoint of endpoints) {
    const resp = await fetch(`${API_BASE_URL}${endpoint}`, { headers });
    if (resp.status === 404) continue;
    if (!resp.ok) continue;
    const data = (await resp.json()) as
      | { results?: Array<{ id?: string; email?: string; roles?: string[] }> }
      | Array<{ id?: string; email?: string; roles?: string[] }>;
    const users = Array.isArray(data) ? data : data.results ?? [];
    const found = users.find((u) => u.email === email);
    if (found?.id) {
      return {
        id: found.id,
        email: found.email ?? email,
        roles: found.roles ?? [],
      };
    }
  }
  throw new Error(`getUserByEmailViaApi: user with email ${email} not found`);
}

/**
 * Get the current user from GET /auth/me/.
 * Returns { id, email, tenant_id, roles }.
 */
export async function getMeViaApi(
  user: TestUser
): Promise<{ id: string; email: string; tenant_id: string; roles: string[] }> {
  const token = await loginViaApiUsers(user);
  const resp = await fetch(`${API_BASE_URL}/auth/me/`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!resp.ok) {
    const body = await resp.text().catch(() => '');
    throw new Error(`getMeViaApi failed: ${resp.status} ${body}`);
  }
  const data = (await resp.json()) as {
    id?: string;
    email?: string;
    tenant_id?: string;
    roles?: string[];
  };
  if (!data.id) throw new Error('getMeViaApi: response missing id');
  return {
    id: data.id,
    email: data.email ?? user.email,
    tenant_id: data.tenant_id ?? '',
    roles: data.roles ?? [],
  };
}

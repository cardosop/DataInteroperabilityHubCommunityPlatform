/**
 * W5.1 (oss-release-remediation R2-F1) — impersonation bearer plumbing.
 *
 * The impersonation contract (Phase 235.4 backend): the SPA swaps the
 * Authorization bearer to the short-lived impersonation JWT (minted as
 * the TARGET with the ``impersonation_session_id`` claim) and scopes
 * X-Tenant-ID to the IMPERSONATED tenant — otherwise actions never run
 * as the target. The pre-fix client stored the token in memory only
 * and never attached it (the designed-but-never-wired class).
 *
 * Pins (real client, stubbed fetch — the client.test.ts convention):
 *
 * * ``setImpersonationToken`` persists to sessionStorage (the R2-F1
 *   persistence contract — survives reloads, dies with the tab).
 * * a fresh client reads the persisted token on construction (the
 *   first request after reload already runs as the target).
 * * ``_buildHeaders`` sends the impersonation bearer INSTEAD of the
 *   operator token, scoped to the impersonated tenant's X-Tenant-ID.
 * * anonymous endpoints (login/register/...) never receive the
 *   impersonation bearer (the stale-bearer 401 trap).
 * * ``clearTokens`` clears the impersonation token + storage (logout
 *   must never leak the capability into the next session).
 */

import { beforeEach, describe, expect, it, vi } from 'vitest';

import { ApiClient } from './client';

const IMP_TOKEN = 'imp.jwt.token';
const IMP_TENANT = '11111111-1111-1111-1111-111111111111';
const OP_TOKEN = 'operator.jwt.token';
const OP_TENANT = '22222222-2222-2222-2222-222222222222';

function mockFetchResponse(body: unknown, status = 200, headers: Record<string, string> = {}) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json', ...headers },
  });
}

describe('ApiClient impersonation (W5.1)', () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    vi.clearAllMocks();
    sessionStorage.clear();
    localStorage.clear();
    fetchMock = vi.fn().mockResolvedValue(mockFetchResponse({ ok: true }));
    vi.stubGlobal('fetch', fetchMock);
    Object.defineProperty(document, 'cookie', { writable: true, value: '' });
  });

  function lastRequestHeaders(): Headers {
    const call = fetchMock.mock.calls.at(-1) as [string, RequestInit] | undefined;
    const init = call?.[1] ?? {};
    return new Headers(init.headers as HeadersInit);
  }

  it('persists the impersonation token to sessionStorage', () => {
    const client = new ApiClient();
    client.setImpersonationToken(IMP_TOKEN, IMP_TENANT);

    expect(sessionStorage.getItem('impersonation_access_token')).toBe(IMP_TOKEN);
    expect(sessionStorage.getItem('impersonation_tenant_id')).toBe(IMP_TENANT);
    expect(client.getImpersonationToken()).toBe(IMP_TOKEN);
  });

  it('a fresh client reads the persisted token on construction', () => {
    sessionStorage.setItem('impersonation_access_token', IMP_TOKEN);
    sessionStorage.setItem('impersonation_tenant_id', IMP_TENANT);

    const client = new ApiClient();

    expect(client.getImpersonationToken()).toBe(IMP_TOKEN);
  });

  it('attaches the impersonation bearer instead of the operator token', async () => {
    const client = new ApiClient();
    client.setAccessToken(OP_TOKEN);
    client.setTenantIdGetter(() => OP_TENANT);
    client.setImpersonationToken(IMP_TOKEN, IMP_TENANT);

    await client.getClient().get('assets/');

    expect(lastRequestHeaders().get('Authorization')).toBe(`Bearer ${IMP_TOKEN}`);
  });

  it('scopes X-Tenant-ID to the impersonated tenant', async () => {
    const client = new ApiClient();
    client.setAccessToken(OP_TOKEN);
    client.setTenantIdGetter(() => OP_TENANT);
    client.setImpersonationToken(IMP_TOKEN, IMP_TENANT);

    await client.getClient().get('assets/');

    expect(lastRequestHeaders().get('X-Tenant-ID')).toBe(IMP_TENANT);
  });

  it('never attaches the impersonation bearer to anonymous endpoints', async () => {
    const client = new ApiClient();
    client.setAccessToken(OP_TOKEN);
    client.setImpersonationToken(IMP_TOKEN, IMP_TENANT);

    await client.getClient().post('/auth/login/', { email: 'a@b.c', password: 'x' });

    expect(lastRequestHeaders().get('Authorization')).toBeNull();
  });

  it('clearTokens clears the impersonation token and its storage', () => {
    const client = new ApiClient();
    client.setImpersonationToken(IMP_TOKEN, IMP_TENANT);

    client.clearTokens();

    expect(client.getImpersonationToken()).toBeNull();
    expect(sessionStorage.getItem('impersonation_access_token')).toBeNull();
    expect(sessionStorage.getItem('impersonation_tenant_id')).toBeNull();
  });

  it('clearSession-equivalent null write removes the storage keys', () => {
    const client = new ApiClient();
    client.setImpersonationToken(IMP_TOKEN, IMP_TENANT);

    client.setImpersonationToken(null);

    expect(client.getImpersonationToken()).toBeNull();
    expect(sessionStorage.getItem('impersonation_access_token')).toBeNull();
  });
});

/**
 * W5.1 (oss-release-remediation R2-F1) — impersonation service wire
 * contract.
 *
 * The backend registers ``POST /admin/impersonate/`` (body:
 * ``{user_id, reason, max_minutes?}`` — reason is REQUIRED, min 10
 * chars) and ``POST /admin/impersonate/exit/`` (body:
 * ``{session_id}``). The pre-fix service called a nonexistent
 * ``/admin/impersonate/start/`` URL without the reason, and the exit
 * call sent NO session_id — both requests could only 400/404, so no
 * impersonation could ever start or end from the SPA.
 *
 * Pins: real service methods against a stubbed fetch (the
 * client.test.ts convention) — the URL + JSON body are the contract.
 */

import { beforeEach, describe, expect, it, vi } from 'vitest';

import { adminService } from './adminService';

function mockFetchResponse(body: unknown, status = 200, headers: Record<string, string> = {}) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json', ...headers },
  });
}

describe('adminService impersonation (W5.1)', () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    vi.clearAllMocks();
    sessionStorage.clear();
    fetchMock = vi.fn().mockResolvedValue(mockFetchResponse({ ok: true }));
    vi.stubGlobal('fetch', fetchMock);
    Object.defineProperty(document, 'cookie', { writable: true, value: '' });
  });

  it('start posts to /admin/impersonate/ with the reason', async () => {
    await adminService.startImpersonation('user-1', 'support session for the on-call');

    const [url, init] = fetchMock.mock.calls.at(-1) as [string, { body?: string }];
    expect(String(url)).toContain('/admin/impersonate/');
    expect(String(url)).not.toContain('/start/');
    expect(JSON.parse(init.body ?? '{}')).toEqual({
      user_id: 'user-1',
      reason: 'support session for the on-call',
    });
  });

  it('start forwards max_minutes when provided', async () => {
    await adminService.startImpersonation('user-1', 'support session for the on-call', 30);

    const [, init] = fetchMock.mock.calls.at(-1) as [string, { body?: string }];
    expect(JSON.parse(init.body ?? '{}')).toEqual({
      user_id: 'user-1',
      reason: 'support session for the on-call',
      max_minutes: 30,
    });
  });

  it('exit posts the session_id in the body', async () => {
    await adminService.exitImpersonation('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa');

    const [url, init] = fetchMock.mock.calls.at(-1) as [string, { body?: string }];
    expect(String(url)).toContain('/admin/impersonate/exit/');
    expect(JSON.parse(init.body ?? '{}')).toEqual({
      session_id: 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
    });
  });
});

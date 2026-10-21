/**
 * authService.listSessions — response-shape normalization (Phase 1.5).
 *
 * ``SessionListPage`` stores the raw payload and calls ``sessions.map``;
 * a non-array response (proxy error envelope, schema drift) crashed the
 * render with "sessions.map is not a function" — the ``tenants.find``
 * class. The backend returns a bare array today; normalization at the
 * service boundary keeps it that way for any 200-response shape.
 */
import { afterEach, describe, expect, it, vi } from 'vitest';

vi.mock('../../../shared/api/client');

import { apiClient } from '../../../shared/api/client';
import { authService } from './authService';

describe('authService.listSessions', () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it('returns the payload when it is an array', async () => {
    const sessions = [{ id: 's1', created_at: '2026-01-01' }];
    vi.mocked(apiClient.getClient().get).mockResolvedValue({
      data: sessions,
    } as never);

    await expect(authService.listSessions()).resolves.toEqual(sessions);
  });

  it('normalizes a non-array payload to []', async () => {
    vi.mocked(apiClient.getClient().get).mockResolvedValue({
      data: { error: 'proxy exploded' },
    } as never);

    await expect(authService.listSessions()).resolves.toEqual([]);
  });

  it('normalizes undefined payload to []', async () => {
    vi.mocked(apiClient.getClient().get).mockResolvedValue({
      data: undefined,
    } as never);

    await expect(authService.listSessions()).resolves.toEqual([]);
  });
});

/**
 * Vitest auto-mock for shared API client — Phase 209.
 *
 * When a test file does `vi.mock('../../shared/api/client')` (path varies by depth),
 * Vitest auto-resolves this __mocks__/client.ts file.
 *
 * Response shape: { data: {} } — matches ApiResponse<T> so existing test assertions
 * that check `response.data` continue to work unchanged.
 *
 * Tests override individual mocks via:
 *   vi.mocked(apiClient.getClient().get).mockResolvedValue({ data: { results: [] } });
 */

import { vi } from 'vitest';

const mockHttpClient = {
  get: vi.fn().mockResolvedValue({ data: {}, status: 200, headers: {} }),
  post: vi.fn().mockResolvedValue({ data: {}, status: 200, headers: {} }),
  put: vi.fn().mockResolvedValue({ data: {}, status: 200, headers: {} }),
  patch: vi.fn().mockResolvedValue({ data: {}, status: 200, headers: {} }),
  delete: vi.fn().mockResolvedValue({ data: {}, status: 200, headers: {} }),
  defaults: { baseURL: '/api/v1' },
};

export const apiClient = {
  getClient: vi.fn(() => mockHttpClient),
  getAccessToken: vi.fn(() => null),
  setAccessToken: vi.fn(),
  setRefreshToken: vi.fn(),
  clearTokens: vi.fn(),
  setTenantIdGetter: vi.fn(),
};

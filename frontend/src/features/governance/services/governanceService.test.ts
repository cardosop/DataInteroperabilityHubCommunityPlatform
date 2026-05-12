/**
 * governanceService tests — Phase 105
 */
import type { HttpClient } from '../../../shared/types/api';
import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../../../shared/api/client');

import { apiClient } from '../../../shared/api/client';
import { governanceService } from './governanceService';

describe('governanceService', () => {
  let mock: HttpClient;

  beforeEach(() => {
    vi.clearAllMocks();
    mock = apiClient.getClient();
  });

  it('list calls GET on correct URL', async () => {
    vi.mocked(mock.get).mockResolvedValue({ data: { results: [] } });
    await governanceService.list();
    expect(vi.mocked(mock.get)).toHaveBeenCalled();
    const url = vi.mocked(mock.get).mock.calls[0][0] as string;
    expect(url).toContain('governance/access-requests');
  });

  it('getById calls GET on correct URL', async () => {
    vi.mocked(mock.get).mockResolvedValue({ data: { results: [] } });
    await governanceService.getById();
    expect(vi.mocked(mock.get)).toHaveBeenCalled();
    const url = vi.mocked(mock.get).mock.calls[0][0] as string;
    expect(url).toContain('governance/access-requests');
  });

  it('create calls POST on correct URL', async () => {
    vi.mocked(mock.post).mockResolvedValue({ data: { id: 'new-id' } });
    await governanceService.create({ name: 'test' } as never);
    expect(vi.mocked(mock.post)).toHaveBeenCalled();
    const url = vi.mocked(mock.post).mock.calls[0][0] as string;
    expect(url).toContain('governance/access-requests');
  });

  it('handles network error gracefully', async () => {
    vi.mocked(mock.get).mockRejectedValue(new Error('Network Error'));
    await expect(governanceService.list()).rejects.toThrow('Network Error');
  });

});

  // Phase 277.3.3 — governance error-state tests.
  describe('governance error handling', () => {
    it('handles 403 ABAC_POLICY_DENIED', async () => {
      vi.mocked(mock.post).mockRejectedValue({
        status: 403,
        data: {
          error: {
            code: 'ABAC_POLICY_DENIED',
            message: 'ABAC policy denied approval.',
            http_status: 403,
            details: { policy_id: 'policy-uuid' },
          },
        },
      });
      await expect(
        governanceService.approve('ar-1'),
      ).rejects.toMatchObject({ status: 403 });
    });

    it('handles 422 COMPLIANCE_RUN_REQUIRED', async () => {
      vi.mocked(mock.post).mockRejectedValue({
        status: 422,
        data: {
          error: {
            code: 'COMPLIANCE_RUN_REQUIRED',
            message: 'A compliance scan is required.',
            http_status: 422,
          },
        },
      });
      await expect(
        governanceService.approve('ar-1'),
      ).rejects.toMatchObject({ status: 422 });
    });
  });

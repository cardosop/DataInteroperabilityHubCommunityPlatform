/**
 * listingService tests — Phase 105
 */
import type { HttpClient } from '../../../shared/types/api';
import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../../../shared/api/client');

import { apiClient } from '../../../shared/api/client';
import { listingService } from './listingService';

describe('listingService', () => {
  let mock: HttpClient;

  beforeEach(() => {
    vi.clearAllMocks();
    mock = apiClient.getClient();
  });

  it('list calls GET on correct URL', async () => {
    vi.mocked(mock.get).mockResolvedValue({ data: { results: [] } });
    await listingService.list();
    expect(vi.mocked(mock.get)).toHaveBeenCalled();
    const url = vi.mocked(mock.get).mock.calls[0][0] as string;
    expect(url).toContain('marketplace/listings');
  });

  it('getById calls GET on correct URL', async () => {
    vi.mocked(mock.get).mockResolvedValue({ data: { results: [] } });
    await listingService.getById();
    expect(vi.mocked(mock.get)).toHaveBeenCalled();
    const url = vi.mocked(mock.get).mock.calls[0][0] as string;
    expect(url).toContain('marketplace/listings');
  });

  it('create calls POST on correct URL', async () => {
    vi.mocked(mock.post).mockResolvedValue({ data: { id: 'new-id' } });
    await listingService.create({ name: 'test' } as never);
    expect(vi.mocked(mock.post)).toHaveBeenCalled();
    const url = vi.mocked(mock.post).mock.calls[0][0] as string;
    expect(url).toContain('marketplace/listings');
  });

  it('handles network error gracefully', async () => {
    vi.mocked(mock.get).mockRejectedValue(new Error('Network Error'));
    await expect(listingService.list()).rejects.toThrow('Network Error');
  });

});

  // Phase 277.3.1 — compliance threshold error-state tests.
  describe('compliance error handling', () => {
    it('handles 422 COMPLIANCE_THRESHOLD_EXCEEDED', async () => {
      const errorBody = {
        error: {
          code: 'COMPLIANCE_THRESHOLD_EXCEEDED',
          message: 'Risk level HIGH exceeds tenant threshold MEDIUM.',
          http_status: 422,
          details: { risk_level: 'HIGH', threshold: 'MEDIUM' },
        },
      };
      vi.mocked(mock.post).mockRejectedValue({
        status: 422,
        data: errorBody,
      });
      await expect(
        listingService.publish('listing-1'),
      ).rejects.toMatchObject({ status: 422 });
    });

    it('handles 422 COMPLIANCE_RUN_REQUIRED', async () => {
      const errorBody = {
        error: {
          code: 'COMPLIANCE_RUN_REQUIRED',
          message: 'A compliance scan is required before publishing.',
          http_status: 422,
          details: {},
        },
      };
      vi.mocked(mock.post).mockRejectedValue({
        status: 422,
        data: errorBody,
      });
      await expect(
        listingService.publish('listing-1'),
      ).rejects.toMatchObject({ status: 422 });
    });
  });

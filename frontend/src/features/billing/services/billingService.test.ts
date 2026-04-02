/**
 * billingService tests — Phase 105
 */
import type { HttpClient } from '../../../shared/types/api';
import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../../../shared/api/client');

import { apiClient } from '../../../shared/api/client';
import { billingService } from './billingService';

describe('billingService', () => {
  let mock: HttpClient;

  beforeEach(() => {
    vi.clearAllMocks();
    mock = apiClient.getClient();
  });

  it('getSubscription calls GET on correct URL', async () => {
    vi.mocked(mock.get).mockResolvedValue({ data: { results: [] } });
    await billingService.getCurrentSubscription();
    expect(vi.mocked(mock.get)).toHaveBeenCalled();
    const url = vi.mocked(mock.get).mock.calls[0][0] as string;
    expect(url).toContain('billing/subscription');
  });

  it('handles network error gracefully', async () => {
    vi.mocked(mock.get).mockRejectedValue(new Error('Network Error'));
    await expect(billingService.getCurrentSubscription()).rejects.toThrow('Network Error');
  });

});

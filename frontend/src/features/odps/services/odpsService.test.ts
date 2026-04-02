/**
 * odpsService tests — Phase 105
 */
import type { HttpClient } from '../../../shared/types/api';
import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../../../shared/api/client');

import { apiClient } from '../../../shared/api/client';
import { odpsService } from './odpsService';

describe('odpsService', () => {
  let mock: HttpClient;

  beforeEach(() => {
    vi.clearAllMocks();
    mock = apiClient.getClient();
  });

  it('createProduct calls POST on correct URL', async () => {
    vi.mocked(mock.post).mockResolvedValue({ data: { id: 'new' } });
    await odpsService.createProduct({original_raw: '{}', original_format: 'JSON'} as never);
    expect(vi.mocked(mock.post)).toHaveBeenCalled();
    const url = vi.mocked(mock.post).mock.calls[0][0] as string;
    expect(url).toContain('contracts');
  });

  it('handles network error gracefully', async () => {
    vi.mocked(mock.post).mockRejectedValue(new Error('Network Error'));
    await expect(odpsService.createProduct({original_raw: '{}', original_format: 'JSON'} as never)).rejects.toThrow('Network Error');
  });

});

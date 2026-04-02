/**
 * jobService tests — Phase 105
 */
import type { HttpClient } from '../../../shared/types/api';
import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../../../shared/api/client');

import { apiClient } from '../../../shared/api/client';
import { jobService } from './jobService';

describe('jobService', () => {
  let mock: HttpClient;

  beforeEach(() => {
    vi.clearAllMocks();
    mock = apiClient.getClient();
  });

  it('list calls GET on correct URL', async () => {
    vi.mocked(mock.get).mockResolvedValue({ data: { results: [] } });
    await jobService.list();
    expect(vi.mocked(mock.get)).toHaveBeenCalled();
    const url = vi.mocked(mock.get).mock.calls[0][0] as string;
    expect(url).toContain('jobs');
  });

  it('getById calls GET on correct URL', async () => {
    vi.mocked(mock.get).mockResolvedValue({ data: { results: [] } });
    await jobService.getById();
    expect(vi.mocked(mock.get)).toHaveBeenCalled();
    const url = vi.mocked(mock.get).mock.calls[0][0] as string;
    expect(url).toContain('jobs');
  });

  it('handles network error gracefully', async () => {
    vi.mocked(mock.get).mockRejectedValue(new Error('Network Error'));
    await expect(jobService.list()).rejects.toThrow('Network Error');
  });

});

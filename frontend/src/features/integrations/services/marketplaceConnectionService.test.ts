/**
 * marketplaceConnectionService tests — Phase 105
 */
import type { HttpClient } from '../../../shared/types/api';
import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../../../shared/api/client');

import { apiClient } from '../../../shared/api/client';
import { marketplaceConnectionService } from './marketplaceConnectionService';

describe('marketplaceConnectionService', () => {
  let mock: HttpClient;

  beforeEach(() => {
    vi.clearAllMocks();
    mock = apiClient.getClient();
  });

  it('list calls GET on correct URL', async () => {
    vi.mocked(mock.get).mockResolvedValue({ data: { results: [] } });
    await marketplaceConnectionService.list();
    expect(vi.mocked(mock.get)).toHaveBeenCalled();
    const url = vi.mocked(mock.get).mock.calls[0][0] as string;
    expect(url).toContain('integrations/marketplace/connections');
  });

  it('getById calls GET on correct URL', async () => {
    vi.mocked(mock.get).mockResolvedValue({ data: { results: [] } });
    await marketplaceConnectionService.getById();
    expect(vi.mocked(mock.get)).toHaveBeenCalled();
    const url = vi.mocked(mock.get).mock.calls[0][0] as string;
    expect(url).toContain('integrations/marketplace/connections');
  });

  it('create calls POST on correct URL', async () => {
    vi.mocked(mock.post).mockResolvedValue({ data: { id: 'new-id' } });
    await marketplaceConnectionService.create({ name: 'test' } as never);
    expect(vi.mocked(mock.post)).toHaveBeenCalled();
    const url = vi.mocked(mock.post).mock.calls[0][0] as string;
    expect(url).toContain('integrations/marketplace/connections');
  });

  it('delete calls DELETE on correct URL', async () => {
    vi.mocked(mock.delete).mockResolvedValue({ status: 204 });
    await marketplaceConnectionService.delete('test-id');
    expect(vi.mocked(mock.delete)).toHaveBeenCalled();
    const url = vi.mocked(mock.delete).mock.calls[0][0] as string;
    expect(url).toContain('integrations/marketplace/connections');
  });

  it('handles network error gracefully', async () => {
    vi.mocked(mock.get).mockRejectedValue(new Error('Network Error'));
    await expect(marketplaceConnectionService.list()).rejects.toThrow('Network Error');
  });

});

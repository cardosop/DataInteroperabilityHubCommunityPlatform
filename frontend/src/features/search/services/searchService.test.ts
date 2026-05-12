/**
 * searchService tests — Phase 105 + 273.1.5 canonical endpoint update
 * + 273.1.7 response-shape parity test
 */
import type { HttpClient } from '../../../shared/types/api';
import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../../../shared/api/client');

import { apiClient } from '../../../shared/api/client';
import { searchService } from './searchService';

describe('searchService', () => {
  let mock: HttpClient;

  beforeEach(() => {
    vi.clearAllMocks();
    mock = apiClient.getClient();
  });

  it('calls the canonical /search/ endpoint with types param', async () => {
    vi.mocked(mock.get).mockResolvedValue({ data: { results: [] } });
    await searchService.search('test query');
    expect(vi.mocked(mock.get)).toHaveBeenCalled();
    const url = vi.mocked(mock.get).mock.calls[0][0] as string;
    // Phase 273.1.5 — canonical endpoint is /search/, NOT /api/v1/search/search/
    expect(url).toContain('search/?');
    expect(url).toContain('q=test+query');
    expect(url).toContain('types=assets,contracts');
  });

  it('maps ALL scope to assets,contracts types', async () => {
    vi.mocked(mock.get).mockResolvedValue({ data: { results: [] } });
    await searchService.search('test', { type: 'ALL' });
    const url = vi.mocked(mock.get).mock.calls[0][0] as string;
    expect(url).toContain('types=assets%2Ccontracts');
  });

  it('maps ASSET scope to assets type', async () => {
    vi.mocked(mock.get).mockResolvedValue({ data: { results: [] } });
    await searchService.search('test', { type: 'ASSET' });
    const url = vi.mocked(mock.get).mock.calls[0][0] as string;
    expect(url).toContain('types=assets');
  });

  it('maps CONTRACT scope to contracts type', async () => {
    vi.mocked(mock.get).mockResolvedValue({ data: { results: [] } });
    await searchService.search('test', { type: 'CONTRACT' });
    const url = vi.mocked(mock.get).mock.calls[0][0] as string;
    expect(url).toContain('types=contracts');
  });

  it('handles network error gracefully', async () => {
    vi.mocked(mock.get).mockRejectedValue(new Error('Network Error'));
    await expect(searchService.search('test query')).rejects.toThrow('Network Error');
  });

  // Phase 273.1.7 — response-shape parity
  it('deserialised payload matches SearchPage consumption shape', async () => {
    const fixture = {
      results: [
        { type: 'asset', id: 'uuid-1', name: 'Test Asset', rank: 1.0 },
        { type: 'contract', id: 'uuid-2', name: 'Test Contract', rank: 0.8 },
      ],
    };
    vi.mocked(mock.get).mockResolvedValue({ data: fixture });
    const data = await searchService.search('test');
    expect(data).toEqual(fixture);
    expect(Array.isArray(data.results)).toBe(true);
    expect(data.results.length).toBe(2);
    expect(data.results[0]).toHaveProperty('type');
    expect(data.results[0]).toHaveProperty('id');
    expect(data.results[0]).toHaveProperty('name');
    expect(data.results[0]).toHaveProperty('rank');
  });
});

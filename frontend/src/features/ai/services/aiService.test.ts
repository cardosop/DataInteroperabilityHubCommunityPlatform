/**
 * aiService tests — Phase 105
 */
import type { HttpClient } from '../../../shared/types/api';
import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../../../shared/api/client');

import { apiClient } from '../../../shared/api/client';
import { aiService } from './aiService';

describe('aiService', () => {
  let mock: HttpClient;

  beforeEach(() => {
    vi.clearAllMocks();
    mock = apiClient.getClient();
  });

  it('naturalLanguageSearch calls POST on correct URL', async () => {
    vi.mocked(mock.post).mockResolvedValue({ data: { id: 'new-id' } });
    await aiService.naturalLanguageSearch({ name: 'test' } as never);
    expect(vi.mocked(mock.post)).toHaveBeenCalled();
    const url = vi.mocked(mock.post).mock.calls[0][0] as string;
    expect(url).toContain('ai');
  });

  it('handles network error gracefully', async () => {
    vi.mocked(mock.post).mockRejectedValue(new Error('Network Error'));
    await expect(aiService.naturalLanguageSearch({query: 'test'} as never)).rejects.toThrow('Network Error');
  });

});

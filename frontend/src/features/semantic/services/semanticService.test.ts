/**
 * semanticService tests — Phase 105
 */
import type { HttpClient } from '../../../shared/types/api';
import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../../../shared/api/client');

import { apiClient } from '../../../shared/api/client';
import { semanticService } from './semanticService';

describe('semanticService', () => {
  let mock: HttpClient;

  beforeEach(() => {
    vi.clearAllMocks();
    mock = apiClient.getClient();
  });

  it('query calls POST on correct URL', async () => {
    vi.mocked(mock.post).mockResolvedValue({ data: { id: 'new-id' } });
    await semanticService.querySPARQL({ name: 'test' } as never);
    expect(vi.mocked(mock.post)).toHaveBeenCalled();
    const url = vi.mocked(mock.post).mock.calls[0][0] as string;
    expect(url).toContain('semantic');
  });

  it('handles network error gracefully', async () => {
    vi.mocked(mock.post).mockRejectedValue(new Error('Network Error'));
    await expect(semanticService.querySPARQL({query: 'SELECT'} as never)).rejects.toThrow('Network Error');
  });

});

  // Phase 277.3.4 — semantic feature flag error test.
  it('handles 403 SEMANTIC_FEATURE_DISABLED', async () => {
    vi.mocked(mock.post).mockRejectedValue({
      status: 403,
      data: {
        error: {
          code: 'SEMANTIC_FEATURE_DISABLED',
          message: "Semantic feature 'sparql' is disabled for this tenant.",
          http_status: 403,
          details: { action: 'sparql' },
        },
      },
    });
    await expect(
      semanticService.querySPARQL({ query: 'SELECT * { ?s ?p ?o }', format: 'json' }),
    ).rejects.toMatchObject({ status: 403 });
  });

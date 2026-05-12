/**
 * assetService tests — Phase 105
 */
import type { HttpClient } from '../../../shared/types/api';
import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../../../shared/api/client');

import { apiClient } from '../../../shared/api/client';
import { assetService } from './assetService';

describe('assetService', () => {
  let mock: HttpClient;

  beforeEach(() => {
    vi.clearAllMocks();
    mock = apiClient.getClient();
  });

  it('list calls GET on correct URL', async () => {
    vi.mocked(mock.get).mockResolvedValue({ data: { results: [] } });
    await assetService.list();
    expect(vi.mocked(mock.get)).toHaveBeenCalled();
    const url = vi.mocked(mock.get).mock.calls[0][0] as string;
    expect(url).toContain('assets');
  });

  it('getById calls GET on correct URL', async () => {
    vi.mocked(mock.get).mockResolvedValue({ data: { results: [] } });
    await assetService.getById();
    expect(vi.mocked(mock.get)).toHaveBeenCalled();
    const url = vi.mocked(mock.get).mock.calls[0][0] as string;
    expect(url).toContain('assets');
  });

  it('create calls POST on correct URL', async () => {
    vi.mocked(mock.post).mockResolvedValue({ data: { id: 'new-id' } });
    await assetService.create({ name: 'test' } as never);
    expect(vi.mocked(mock.post)).toHaveBeenCalled();
    const url = vi.mocked(mock.post).mock.calls[0][0] as string;
    expect(url).toContain('assets');
  });

  it('update calls PATCH on correct URL', async () => {
    vi.mocked(mock.patch).mockResolvedValue({ data: { id: 'test-id' } });
    await assetService.update('test-id', { name: 'updated' } as never);
    expect(vi.mocked(mock.patch)).toHaveBeenCalled();
    const url = vi.mocked(mock.patch).mock.calls[0][0] as string;
    expect(url).toContain('assets');
  });

  it('update sends If-Match header when provided', async () => {
    vi.mocked(mock.patch).mockResolvedValue({ data: { id: 'test-id' } });
    await assetService.update('test-id', { name: 'updated' } as never, { ifMatch: '7' });
    expect(vi.mocked(mock.patch)).toHaveBeenCalled();
    const config = vi.mocked(mock.patch).mock.calls[0][2] as { headers?: Record<string, string> };
    expect(config.headers?.['If-Match']).toBe('7');
  });

  it('delete calls DELETE on correct URL', async () => {
    vi.mocked(mock.delete).mockResolvedValue({ status: 204 });
    await assetService.delete('test-id');
    expect(vi.mocked(mock.delete)).toHaveBeenCalled();
    const url = vi.mocked(mock.delete).mock.calls[0][0] as string;
    expect(url).toContain('assets');
  });

  it('handles network error gracefully', async () => {
    vi.mocked(mock.get).mockRejectedValue(new Error('Network Error'));
    await expect(assetService.list()).rejects.toThrow('Network Error');
  });

});

  // Phase 277.3.2 — compliance activation error-state tests.
  describe('activation compliance errors', () => {
    it('handles 409 COMPLIANCE_SCAN_PENDING with Retry-After', async () => {
      const error = {
        status: 409,
        data: {
          error: { code: 'COMPLIANCE_SCAN_PENDING', message: 'Scan pending', http_status: 409 },
        },
        headers: new Map([['retry-after', '30']]),
      };
      vi.mocked(mock.post).mockRejectedValue(error);
      await expect(
        assetService.activate('asset-1', 1),
      ).rejects.toMatchObject({ status: 409 });
    });

    it('handles 422 COMPLIANCE_SCAN_FAILED', async () => {
      vi.mocked(mock.post).mockRejectedValue({
        status: 422,
        data: { error: { code: 'COMPLIANCE_SCAN_FAILED', http_status: 422 } },
      });
      await expect(
        assetService.activate('asset-1', 1),
      ).rejects.toMatchObject({ status: 422 });
    });

    it('handles 422 COMPLIANCE_NOT_ALLOWED_TO_STORE', async () => {
      vi.mocked(mock.post).mockRejectedValue({
        status: 422,
        data: { error: { code: 'COMPLIANCE_NOT_ALLOWED_TO_STORE', http_status: 422 } },
      });
      await expect(
        assetService.activate('asset-1', 1),
      ).rejects.toMatchObject({ status: 422 });
    });
  });

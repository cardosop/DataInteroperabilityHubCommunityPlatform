/**
 * auditService tests — Phase 105
 */
import type { HttpClient } from '../../../shared/types/api';
import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../../../shared/api/client');

import { apiClient } from '../../../shared/api/client';
import { auditService } from './auditService';

describe('auditService', () => {
  let mock: HttpClient;

  beforeEach(() => {
    vi.clearAllMocks();
    mock = apiClient.getClient();
  });

  it('list calls GET on correct URL', async () => {
    vi.mocked(mock.get).mockResolvedValue({ data: { results: [] } });
    await auditService.list();
    expect(vi.mocked(mock.get)).toHaveBeenCalled();
    const url = vi.mocked(mock.get).mock.calls[0][0] as string;
    expect(url).toContain('audit/audit-events');
  });

  it('handles network error gracefully', async () => {
    vi.mocked(mock.get).mockRejectedValue(new Error('Network Error'));
    await expect(auditService.list()).rejects.toThrow('Network Error');
  });

  // W5.4 (R2-F5) — wire-shape pins for the real pagination work: the page
  // parameters must travel on the wire (the pre-W5.4 /audit page had a
  // hardcoded page 1 with console.log button stubs).
  it('propagates the page parameter on the wire', async () => {
    vi.mocked(mock.get).mockResolvedValue({ data: { results: [] } });
    await auditService.list({ page: 3 });
    const url = vi.mocked(mock.get).mock.calls[0][0] as string;
    expect(url).toMatch(/page=3\b/);
  });

  it('propagates the page_size parameter on the wire', async () => {
    vi.mocked(mock.get).mockResolvedValue({ data: { results: [] } });
    await auditService.list({ page_size: 50 });
    const url = vi.mocked(mock.get).mock.calls[0][0] as string;
    expect(url).toMatch(/page_size=50\b/);
  });

  it('propagates page and page_size together on the wire', async () => {
    vi.mocked(mock.get).mockResolvedValue({ data: { results: [] } });
    await auditService.list({ page: 2, page_size: 20 });
    const url = vi.mocked(mock.get).mock.calls[0][0] as string;
    expect(url).toMatch(/page=2\b/);
    expect(url).toMatch(/page_size=20\b/);
  });
});

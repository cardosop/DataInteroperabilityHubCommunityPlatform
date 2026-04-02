/**
 * Compliance Service Tests — fixed to match actual complianceService API
 */

import type { HttpClient } from '../../../shared/types/api';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { ComplianceRun } from '../../../shared/types/compliance';

vi.mock('../../../shared/api/client');

import { apiClient } from '../../../shared/api/client';
import { complianceService } from './complianceService';

const MOCK_RUN: ComplianceRun = {
  id: 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee',
  tenant: 'tenant-1',
  job: 'job-1',
  status: 'PENDING',
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
} as ComplianceRun;

describe('complianceService', () => {
  let mock: HttpClient;

  beforeEach(() => {
    vi.clearAllMocks();
    mock = apiClient.getClient();
  });

  describe('list', () => {
    it('fetches compliance runs with filters', async () => {
      vi.mocked(mock.get).mockResolvedValue({
        data: { count: 1, results: [MOCK_RUN] },
      });
      const result = await complianceService.list({ page: 1, status: 'PENDING' });
      expect(vi.mocked(mock.get)).toHaveBeenCalled();
      const url = vi.mocked(mock.get).mock.calls[0][0] as string;
      expect(url).toContain('compliance/runs/');
      expect(url).toContain('page=1');
      expect(url).toContain('status=PENDING');
      expect(result.results).toHaveLength(1);
    });

    it('fetches compliance runs without filters', async () => {
      vi.mocked(mock.get).mockResolvedValue({
        data: { count: 0, results: [] },
      });
      const result = await complianceService.list();
      expect(vi.mocked(mock.get)).toHaveBeenCalled();
      const url = vi.mocked(mock.get).mock.calls[0][0] as string;
      expect(url).toContain('compliance/runs/');
      expect(result.count).toBe(0);
    });
  });

  describe('getById', () => {
    it('fetches a compliance run by ID', async () => {
      vi.mocked(mock.get).mockResolvedValue({ data: MOCK_RUN });
      const result = await complianceService.getById(MOCK_RUN.id);
      const url = vi.mocked(mock.get).mock.calls[0][0] as string;
      expect(url).toContain(`compliance/runs/${MOCK_RUN.id}/`);
      expect(result.id).toBe(MOCK_RUN.id);
    });
  });

  describe('getResults', () => {
    it('fetches compliance run results', async () => {
      const mockResults = { checks: [], summary: {} };
      vi.mocked(mock.get).mockResolvedValue({ data: mockResults });
      const result = await complianceService.getResults(MOCK_RUN.id);
      const url = vi.mocked(mock.get).mock.calls[0][0] as string;
      expect(url).toContain(`compliance/runs/${MOCK_RUN.id}/results/`);
      expect(result).toEqual(mockResults);
    });
  });

  describe('create', () => {
    it('creates a compliance run', async () => {
      vi.mocked(mock.post).mockResolvedValue({ data: MOCK_RUN });
      const result = await complianceService.create({ asset_id: 'asset-1' } as never);
      const url = vi.mocked(mock.post).mock.calls[0][0] as string;
      expect(url).toContain('compliance/runs/');
      expect(result.id).toBe(MOCK_RUN.id);
    });
  });

  describe('cancel', () => {
    it('cancels a compliance run', async () => {
      const cancelled = { ...MOCK_RUN, status: 'CANCELLED' };
      vi.mocked(mock.post).mockResolvedValue({ data: cancelled });
      const result = await complianceService.cancel(MOCK_RUN.id);
      const url = vi.mocked(mock.post).mock.calls[0][0] as string;
      expect(url).toContain(`compliance/runs/${MOCK_RUN.id}/cancel/`);
      expect(result.status).toBe('CANCELLED');
    });
  });

  describe('delete', () => {
    it('deletes a compliance run', async () => {
      vi.mocked(mock.delete).mockResolvedValue({ status: 204 });
      await complianceService.delete(MOCK_RUN.id);
      const url = vi.mocked(mock.delete).mock.calls[0][0] as string;
      expect(url).toContain(`compliance/runs/${MOCK_RUN.id}/`);
    });
  });

  it('handles network error', async () => {
    vi.mocked(mock.get).mockRejectedValue(new Error('Network Error'));
    await expect(complianceService.list()).rejects.toThrow('Network Error');
  });
});

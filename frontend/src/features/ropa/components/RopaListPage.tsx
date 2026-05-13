/**
 * Phase 277.B.028 — RoPA standalone page for DPO persona.
 * Replaces 276.B.103 stub with real data fetching.
 */
import { useCallback, useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Button } from '../../../shared/components/Button';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { EmptyState } from '../../../shared/components/EmptyState';
import { DetailPageSkeleton } from '../../../shared/components/skeletons/DetailPageSkeleton';
import { apiClient } from '../../../shared/api/client';
import type { RopaGenerationRow } from '../../tenants/services/ropaService';
import './RopaListPage.css';

const ROPA_BASE = 'ropa/generations';

function useRopaGenerations() {
  return useQuery<RopaGenerationRow[]>({
    queryKey: ['ropa', 'generations'],
    queryFn: async () => {
      const resp = await apiClient.getClient().get<{ results: RopaGenerationRow[] }>(`${ROPA_BASE}/`);
      return resp.data.results || [];
    },
  });
}

function useGenerateRopa() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: { regulation: string }) => {
      const resp = await apiClient.getClient().post<RopaGenerationRow>(`${ROPA_BASE}/`, body);
      return resp.data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['ropa', 'generations'] }),
  });
}

export function RopaListPage() {
  const { data: generations, isLoading, error, refetch } = useRopaGenerations();
  const generateMutation = useGenerateRopa();
  const [selectedRegulation, setSelectedRegulation] = useState('GDPR');

  const handleGenerate = useCallback(async () => {
    await generateMutation.mutateAsync({ regulation: selectedRegulation });
    refetch();
  }, [generateMutation, refetch, selectedRegulation]);

  if (isLoading) return <DetailPageSkeleton />;
  if (error) return <ErrorDisplay error={error} title="Failed to load RoPA records" onRetry={() => refetch()} />;

  return (
    <div className="ropa-list-page" data-testid="ropa-list">
      <h1>Record of Processing Activities</h1>
      <p className="ropa-subtitle">Generate and review processing records per GDPR Article 30.</p>

      <div className="ropa-generate-bar">
        <select value={selectedRegulation} onChange={(e) => setSelectedRegulation(e.target.value)} data-testid="ropa-regulation-select">
          <option value="GDPR">GDPR</option>
          <option value="UK_GDPR">UK GDPR</option>
          <option value="LGPD">LGPD</option>
          <option value="CCPA">CCPA</option>
        </select>
        <Button variant="primary" onClick={handleGenerate} loading={generateMutation.isPending} data-testid="ropa-generate-btn">
          Generate RoPA
        </Button>
      </div>

      {(!generations || generations.length === 0) ? (
        <EmptyState title="No processing records yet" description="Generate your first Record of Processing Activities." />
      ) : (
        <table className="ropa-table" data-testid="ropa-table">
          <thead><tr><th>Regulation</th><th>Format</th><th>Status</th><th>Generated</th><th>Actions</th></tr></thead>
          <tbody>
            {generations.map((gen: RopaGenerationRow) => (
              <tr key={gen.id} data-testid={`ropa-row-${gen.id}`}>
                <td>{gen.regulation}</td><td>{gen.output_format}</td>
                <td><span className={`ropa-status ${gen.status.toLowerCase()}`}>{gen.status}</span></td>
                <td>{new Date(gen.created_at).toLocaleDateString()}</td>
                <td>{gen.status === 'COMPLETED' && (
                  <Button variant="ghost" onClick={() => window.open(`/api/v1/${ROPA_BASE}/${gen.id}/download/`, '_blank')}>Download</Button>
                )}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

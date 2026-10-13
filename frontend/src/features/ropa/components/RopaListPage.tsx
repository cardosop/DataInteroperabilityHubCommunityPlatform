/**
 * Phase 277.B.028 — RoPA standalone page for DPO persona.
 * Replaces 276.B.103 stub with real data fetching.
 *
 * 276.B.104 — RoPA lifecycle: each record can be annotated (edit step,
 * PATCH notes into summary_json) and retired (delete step).
 */
import { Fragment, useCallback, useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Button } from '../../../shared/components/Button';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { EmptyState } from '../../../shared/components/EmptyState';
import { DetailPageSkeleton } from '../../../shared/components/skeletons/DetailPageSkeleton';
import {
  ropaService,
  type RopaGenerationRow,
} from '../../tenants/services/ropaService';
import './RopaListPage.css';

function useRopaGenerations() {
  return useQuery<RopaGenerationRow[]>({
    queryKey: ['ropa', 'generations'],
    queryFn: async () => {
      const data = await ropaService.listGenerations();
      return data.results || [];
    },
  });
}

function useGenerateRopa() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: { regulation: string }) =>
      ropaService.generate(body.regulation, 'json').then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['ropa', 'generations'] }),
  });
}

/** 276.B.104 — edit step: persist a DPO note on the record's summary_json. */
function useUpdateRopaNote() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (vars: { id: string; summaryJson: Record<string, unknown> }) =>
      ropaService.updateMetadata(vars.id, vars.summaryJson),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['ropa', 'generations'] }),
  });
}

/** 276.B.104 — retire step: delete the record. */
function useRemoveRopa() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => ropaService.remove(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['ropa', 'generations'] }),
  });
}

export function RopaListPage() {
  const { data: generations, isLoading, error, refetch } = useRopaGenerations();
  const generateMutation = useGenerateRopa();
  const noteMutation = useUpdateRopaNote();
  const removeMutation = useRemoveRopa();
  const [selectedRegulation, setSelectedRegulation] = useState('GDPR');
  const [editingNoteId, setEditingNoteId] = useState<string | null>(null);
  const [noteDraft, setNoteDraft] = useState('');
  const [confirmingDeleteId, setConfirmingDeleteId] = useState<string | null>(null);

  const handleGenerate = useCallback(async () => {
    await generateMutation.mutateAsync({ regulation: selectedRegulation });
    refetch();
  }, [generateMutation, refetch, selectedRegulation]);

  const handleSaveNote = useCallback(
    async (gen: RopaGenerationRow) => {
      const merged = { ...(gen.summary_json ?? {}), notes: noteDraft.trim() };
      await noteMutation.mutateAsync({ id: gen.id, summaryJson: merged });
      setEditingNoteId(null);
      setNoteDraft('');
    },
    [noteMutation, noteDraft],
  );

  const handleRetire = useCallback(
    async (id: string) => {
      await removeMutation.mutateAsync(id);
      setConfirmingDeleteId(null);
    },
    [removeMutation],
  );

  if (isLoading) return <DetailPageSkeleton />;
  if (error) return <ErrorDisplay error={error} title="Failed to load RoPA records" onRetry={() => refetch()} />;

  return (
    <div className="ropa-list-page" data-testid="ropa-list">
      <h1>Record of Processing Activities</h1>
      <p className="ropa-subtitle">Generate and review processing records per GDPR Article 30.</p>

      <div className="ropa-generate-bar">
        <select
          value={selectedRegulation}
          onChange={(e) => setSelectedRegulation(e.target.value)}
          data-testid="ropa-regulation-select"
          aria-label="Select regulation"
        >
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
        <EmptyState title="No processing records yet" message="Generate your first Record of Processing Activities." />
      ) : (
        <table className="ropa-table" data-testid="ropa-table">
          <thead><tr><th>Regulation</th><th>Format</th><th>Status</th><th>Generated</th><th>Notes</th><th>Actions</th></tr></thead>
          <tbody>
            {generations.map((gen: RopaGenerationRow) => (
              <Fragment key={gen.id}>
                <tr data-testid={`ropa-row-${gen.id}`}>
                  <td>{gen.regulation}</td><td>{gen.output_format}</td>
                  <td><span className={`ropa-status ${gen.status.toLowerCase()}`}>{gen.status}</span></td>
                  <td>{new Date(gen.created_at).toLocaleDateString()}</td>
                  <td>
                    <span data-testid={`ropa-note-text-${gen.id}`}>
                      {(gen.summary_json?.notes as string | undefined) || '-'}
                    </span>
                  </td>
                  <td className="ropa-row-actions">
                    {gen.status === 'COMPLETED' && (
                      <Button variant="ghost" onClick={() => window.open(`/api/v1/ropa/generations/${gen.id}/download/`, '_blank')}>Download</Button>
                    )}
                    <Button
                      variant="ghost"
                      data-testid={`ropa-note-btn-${gen.id}`}
                      onClick={() => {
                        setEditingNoteId(editingNoteId === gen.id ? null : gen.id);
                        setNoteDraft((gen.summary_json?.notes as string | undefined) ?? '');
                      }}
                    >
                      {(gen.summary_json?.notes as string | undefined) ? 'Edit note' : 'Add note'}
                    </Button>
                    {confirmingDeleteId === gen.id ? (
                      <>
                        <Button
                          variant="danger"
                          data-testid={`ropa-delete-confirm-${gen.id}`}
                          loading={removeMutation.isPending}
                          onClick={() => handleRetire(gen.id)}
                        >
                          Confirm
                        </Button>
                        <Button variant="ghost" onClick={() => setConfirmingDeleteId(null)}>Cancel</Button>
                      </>
                    ) : (
                      <Button
                        variant="ghost"
                        data-testid={`ropa-delete-btn-${gen.id}`}
                        onClick={() => setConfirmingDeleteId(gen.id)}
                      >
                        Retire
                      </Button>
                    )}
                  </td>
                </tr>
                {editingNoteId === gen.id && (
                  <tr className="ropa-note-editor-row" data-testid={`ropa-note-editor-${gen.id}`}>
                    <td colSpan={6}>
                      <input
                        data-testid={`ropa-note-input-${gen.id}`}
                        value={noteDraft}
                        onChange={(e) => setNoteDraft(e.target.value)}
                        placeholder="Add a note for this record (e.g. reviewed with legal)"
                        aria-label="Note for this record"
                      />
                      <Button
                        variant="primary"
                        data-testid={`ropa-note-save-${gen.id}`}
                        loading={noteMutation.isPending}
                        onClick={() => handleSaveNote(gen)}
                      >
                        Save note
                      </Button>
                      <Button variant="ghost" onClick={() => setEditingNoteId(null)}>Cancel</Button>
                    </td>
                  </tr>
                )}
              </Fragment>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

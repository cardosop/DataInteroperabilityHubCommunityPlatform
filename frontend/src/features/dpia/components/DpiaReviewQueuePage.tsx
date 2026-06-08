/**
 * Phase 232.5 — DPO review queue (default: IN_REVIEW + REQUIRES_CONSULTATION).
 */
import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '../../../shared/components/Button';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { useCapabilities } from '../../../shared/hooks/useCapabilities';
import { dpiaService, type DpiaRow } from '../services/dpiaService';
import { normalizeError, type ApiError } from '../../../shared/utils/errorUtils';

export function DpiaReviewQueuePage() {
  const navigate = useNavigate();
  const { isCapabilityAvailable } = useCapabilities();
  const enabled = isCapabilityAvailable('compliance_dpia');
  const [rows, setRows] = useState<DpiaRow[]>([]);
  const [error, setError] = useState<ApiError | null>(null);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    if (!enabled) return;
    setLoading(true);
    setError(null);
    try {
      const inReview = await dpiaService.list({ status: 'IN_REVIEW' });
      const consult = await dpiaService.list({ status: 'REQUIRES_CONSULTATION' });
      const merged = [...(inReview.results || []), ...(consult.results || [])];
      merged.sort((a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime());
      setRows(merged);
    } catch (e) {
      setError(normalizeError(e));
    } finally {
      setLoading(false);
    }
  }, [enabled]);

  useEffect(() => {
    void load();
  }, [load]);

  if (!enabled) {
    return <p>DPIA is not enabled for this tenant.</p>;
  }

  return (
    <div data-testid="dpia-review-queue">
      <h2>DPIA review queue</h2>
      <p className="tenant-settings-description">Assessments awaiting DPO / legal review.</p>
      <Button type="button" variant="secondary" onClick={() => void load()} disabled={loading}>
        Refresh
      </Button>
      {rows.length === 0 && !loading ? <p>No items in queue.</p> : null}
      <table className="tenant-table-lite" style={{ marginTop: 16 }}>
        <thead>
          <tr>
            <th>Title</th>
            <th>Status</th>
            <th>Updated</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.id}>
              <td>{r.title}</td>
              <td>{r.status}</td>
              <td>{new Date(r.updated_at).toLocaleString()}</td>
              <td>
                <Button type="button" variant="primary" onClick={() => navigate(`/governance/dpia/${r.id}/review`)}>
                  Review
                </Button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {error ? <ErrorDisplay error={error} /> : null}
    </div>
  );
}

/**
 * Phase 232.5 — DPO decision surface + version diff.
 */
import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { Button } from '../../../shared/components/Button';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { Banner } from '../../../shared/components/Banner';
import { useCapabilities } from '../../../shared/hooks/useCapabilities';
import { dpiaService, type DpiaRow } from '../services/dpiaService';
import { normalizeError, type ApiError } from '../../../shared/utils/errorUtils';

export function DpiaReviewPage() {
  const { dpiaId } = useParams<{ dpiaId: string }>();
  const navigate = useNavigate();
  const { isCapabilityAvailable } = useCapabilities();
  const enabled = isCapabilityAvailable('compliance_dpia');
  const [row, setRow] = useState<DpiaRow | null>(null);
  const [diff, setDiff] = useState<Awaited<ReturnType<typeof dpiaService.diff>> | null>(null);
  const [outcome, setOutcome] = useState<'APPROVED' | 'REJECTED' | 'REQUIRES_CONSULTATION'>('APPROVED');
  const [riskResidual, setRiskResidual] = useState<'LOW' | 'MEDIUM' | 'HIGH'>('LOW');
  const [dpoSummary, setDpoSummary] = useState('');
  const [error, setError] = useState<ApiError | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!enabled || !dpiaId) return;
    let cancelled = false;
    (async () => {
      try {
        const d = await dpiaService.get(dpiaId);
        if (cancelled) return;
        setRow(d);
        try {
          const df = await dpiaService.diff(dpiaId);
          if (!cancelled) setDiff(df);
        } catch {
          setDiff(null);
        }
      } catch (e) {
        setError(normalizeError(e));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [dpiaId, enabled]);

  if (!enabled) {
    return <Banner variant="warning">DPIA capability is off for this tenant.</Banner>;
  }
  if (!row) {
    return error ? <ErrorDisplay error={error} /> : <p>Loading…</p>;
  }

  const onSubmitReview = async () => {
    setBusy(true);
    setError(null);
    try {
      await dpiaService.review(row.id, {
        outcome,
        risk_residual: riskResidual,
        dpo_summary: dpoSummary,
      });
      navigate('/governance/dpia/review-queue');
    } catch (e) {
      setError(normalizeError(e));
    } finally {
      setBusy(false);
    }
  };

  const onConsultDone = async (approve: boolean) => {
    setBusy(true);
    setError(null);
    try {
      await dpiaService.completeConsultation(row.id, approve);
      navigate('/governance/dpia/review-queue');
    } catch (e) {
      setError(normalizeError(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div data-testid="dpia-review-page">
      <h2>Review: {row.title}</h2>
      <p>
        Status: <strong>{row.status}</strong> — v{row.version}
      </p>

      {diff && diff.changed_keys?.length ? (
        <div className="tenant-form-group">
          <h3>Wizard diff vs previous version</h3>
          <table className="tenant-table-lite">
            <thead>
              <tr>
                <th>Field</th>
                <th>Before</th>
                <th>After</th>
              </tr>
            </thead>
            <tbody>
              {diff.changed_keys.map((c) => (
                <tr key={c.field}>
                  <td>{c.field}</td>
                  <td>
                    <pre style={{ margin: 0, whiteSpace: 'pre-wrap' }}>{JSON.stringify(c.before, null, 2)}</pre>
                  </td>
                  <td>
                    <pre style={{ margin: 0, whiteSpace: 'pre-wrap' }}>{JSON.stringify(c.after, null, 2)}</pre>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}

      {row.status === 'REQUIRES_CONSULTATION' ? (
        <div className="tenant-form-group">
          <p>Consultation outcome for supervisory follow-up / Art. 36 path.</p>
          <Button type="button" variant="primary" loading={busy} onClick={() => void onConsultDone(true)}>
            Approve after consultation
          </Button>{' '}
          <Button type="button" variant="secondary" loading={busy} onClick={() => void onConsultDone(false)}>
            Return to review
          </Button>
        </div>
      ) : (
        <div className="tenant-form-group">
          <label htmlFor="dpia-outcome">Decision</label>
          <select
            id="dpia-outcome"
            value={outcome}
            onChange={(e) =>
              setOutcome(e.target.value as typeof outcome)
            }
          >
            <option value="APPROVED">Approved</option>
            <option value="REJECTED">Rejected</option>
            <option value="REQUIRES_CONSULTATION">Requires consultation (manual)</option>
          </select>
          <label htmlFor="dpia-resid">Residual risk</label>
          <select
            id="dpia-resid"
            value={riskResidual}
            onChange={(e) => setRiskResidual(e.target.value as typeof riskResidual)}
          >
            <option value="LOW">LOW</option>
            <option value="MEDIUM">MEDIUM</option>
            <option value="HIGH">HIGH</option>
          </select>
          <label htmlFor="dpia-dpo">DPO summary</label>
          <textarea id="dpia-dpo" rows={5} style={{ width: '100%', maxWidth: 640 }} value={dpoSummary} onChange={(e) => setDpoSummary(e.target.value)} />
          <Button type="button" variant="primary" loading={busy} onClick={() => void onSubmitReview()}>
            Submit decision
          </Button>
        </div>
      )}

      {error ? <ErrorDisplay error={error} /> : null}
    </div>
  );
}

/**
 * Phase 232.5 — DPIA multi-step wizard (draft → submit).
 */
import { useEffect, useState } from 'react';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { Button } from '../../../shared/components/Button';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { Banner } from '../../../shared/components/Banner';
import { useCapabilities } from '../../../shared/hooks/useCapabilities';
import { dpiaService, type DpiaRow } from '../services/dpiaService';
import { normalizeError, type ApiError } from '../../../shared/utils/errorUtils';

const STEPS = ['Basics', 'Processing', 'Risks & measures', 'Review'] as const;

export function DpiaWizardPage() {
  const { dpiaId } = useParams<{ dpiaId: string }>();
  const isNew = dpiaId === 'new';
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { isCapabilityAvailable } = useCapabilities();
  const enabled = isCapabilityAvailable('compliance_dpia');

  const [draftId, setDraftId] = useState<string | null>(null);
  const [step, setStep] = useState(0);
  const [row, setRow] = useState<DpiaRow | null>(null);
  const [title, setTitle] = useState('');
  const [regime, setRegime] = useState('GDPR');
  const [assetId, setAssetId] = useState('');
  const [processingNarrative, setProcessingNarrative] = useState('');
  const [riskNarrative, setRiskNarrative] = useState('');
  const [mitigations, setMitigations] = useState('');
  const [error, setError] = useState<ApiError | null>(null);
  const [busy, setBusy] = useState(false);

  const recordId = isNew ? draftId : dpiaId;

  useEffect(() => {
    const a = searchParams.get('asset');
    if (a) setAssetId(a);
  }, [searchParams]);

  useEffect(() => {
    if (!enabled || isNew || !dpiaId || dpiaId === 'new') return;
    let cancelled = false;
    (async () => {
      try {
        const d = await dpiaService.get(dpiaId);
        if (cancelled) return;
        setRow(d);
        setTitle(d.title);
        setRegime(d.regime);
        setAssetId(d.asset ?? '');
        const p = (d.wizard_payload || {}) as Record<string, unknown>;
        setProcessingNarrative(String(p.processing_narrative ?? ''));
        setRiskNarrative(String(p.risk_narrative ?? ''));
        setMitigations(String(p.mitigations ?? ''));
      } catch (e) {
        setError(normalizeError(e));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [dpiaId, enabled, isNew]);

  if (!enabled) {
    return (
      <Banner variant="warning">
        DPIA is disabled for this tenant. Enable <strong>compliance_dpia_enabled</strong> in tenant feature flags.
      </Banner>
    );
  }

  const persistPayload = async (): Promise<DpiaRow> => {
    const wizard_payload = {
      processing_narrative: processingNarrative,
      risk_narrative: riskNarrative,
      mitigations,
      last_step: step,
    };
    if (isNew) {
      if (!recordId) {
        const created = await dpiaService.create({
          title: title || 'Untitled DPIA',
          regime,
          asset: assetId.trim() || null,
          wizard_payload,
        });
        setDraftId(created.id);
        setRow(created);
        return created;
      }
      const updated = await dpiaService.patch(recordId, { title, wizard_payload });
      setRow(updated);
      return updated;
    }
    const updated = await dpiaService.patch(dpiaId!, { title, wizard_payload });
    setRow(updated);
    return updated;
  };

  const onNext = async () => {
    setError(null);
    setBusy(true);
    try {
      await persistPayload();
      setStep((s) => Math.min(s + 1, STEPS.length - 1));
    } catch (e) {
      setError(normalizeError(e));
    } finally {
      setBusy(false);
    }
  };

  const onBack = () => setStep((s) => Math.max(0, s - 1));

  const onSubmit = async () => {
    setError(null);
    setBusy(true);
    try {
      const latest = await persistPayload();
      await dpiaService.submit(latest.id);
      navigate('/governance/dpia/review-queue');
    } catch (e) {
      setError(normalizeError(e));
    } finally {
      setBusy(false);
    }
  };

  const canFinalSubmit = Boolean(recordId && (title.trim() || row));

  return (
    <div className="tenant-form-group" data-testid="dpia-wizard">
      <h2>DPIA wizard</h2>
      <p className="tenant-settings-description">
        Steps: {STEPS.join(' → ')} — {STEPS[step]}
      </p>

      {step === 0 && (
        <div className="tenant-form-group">
          <label htmlFor="dpia-title">Title</label>
          <input
            id="dpia-title"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            style={{ width: '100%', maxWidth: 480 }}
          />
          <label htmlFor="dpia-regime">Regime</label>
          <select id="dpia-regime" value={regime} onChange={(e) => setRegime(e.target.value)}>
            <option value="GDPR">GDPR</option>
            <option value="LGPD">LGPD</option>
            <option value="CCPA">CCPA</option>
          </select>
          <label htmlFor="dpia-asset">Linked asset ID (optional)</label>
          <input
            id="dpia-asset"
            value={assetId}
            onChange={(e) => setAssetId(e.target.value)}
            placeholder="UUID"
            style={{ width: '100%', maxWidth: 480 }}
          />
        </div>
      )}

      {step === 1 && (
        <div className="tenant-form-group">
          <label htmlFor="dpia-proc">Processing narrative</label>
          <textarea
            id="dpia-proc"
            rows={8}
            style={{ width: '100%', maxWidth: 640 }}
            value={processingNarrative}
            onChange={(e) => setProcessingNarrative(e.target.value)}
          />
        </div>
      )}

      {step === 2 && (
        <div className="tenant-form-group">
          <label htmlFor="dpia-risk">Inherent / residual risks</label>
          <textarea
            id="dpia-risk"
            rows={6}
            style={{ width: '100%', maxWidth: 640 }}
            value={riskNarrative}
            onChange={(e) => setRiskNarrative(e.target.value)}
          />
          <label htmlFor="dpia-mit">Mitigations</label>
          <textarea
            id="dpia-mit"
            rows={6}
            style={{ width: '100%', maxWidth: 640 }}
            value={mitigations}
            onChange={(e) => setMitigations(e.target.value)}
          />
        </div>
      )}

      {step === 3 && (
        <div className="tenant-form-group">
          <p>
            <strong>Summary</strong>
          </p>
          <ul>
            <li>Title: {title || '(empty)'}</li>
            <li>Regime: {regime}</li>
            <li>Asset: {assetId || '—'}</li>
          </ul>
          <p>
            Submitting moves this DPIA to <strong>IN_REVIEW</strong> for the DPO queue.
          </p>
        </div>
      )}

      <div style={{ display: 'flex', gap: 8, marginTop: 16 }}>
        <Button type="button" variant="secondary" onClick={onBack} disabled={step === 0 || busy}>
          Back
        </Button>
        {step < STEPS.length - 1 ? (
          <Button type="button" variant="primary" onClick={() => void onNext()} loading={busy}>
            Next
          </Button>
        ) : (
          <Button
            type="button"
            variant="primary"
            onClick={() => void onSubmit()}
            loading={busy}
            disabled={!canFinalSubmit}
          >
            Submit for review
          </Button>
        )}
      </div>

      {error ? <ErrorDisplay error={error} /> : null}
    </div>
  );
}

/**
 * Phase 232.4 — RoPA panel (Tenant Settings → Compliance tab)
 */
import { useCallback, useEffect, useState } from 'react';
import { Button } from '../../../shared/components/Button';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { useCapabilities } from '../../../shared/hooks/useCapabilities';
import { ropaService, type RopaGenerationRow } from '../services/ropaService';
import { normalizeError, type ApiError } from '../../../shared/utils/errorUtils';

const FORMATS = ['json', 'csv', 'pdf', 'docx'] as const;

export function RopaCompliancePanel() {
  const { isCapabilityAvailable } = useCapabilities();
  const enabled = isCapabilityAvailable('compliance_ropa');
  const [preview, setPreview] = useState<Awaited<ReturnType<typeof ropaService.preview>> | null>(null);
  const [rows, setRows] = useState<RopaGenerationRow[]>([]);
  const [regulation, setRegulation] = useState('GDPR');
  const [loadingPreview, setLoadingPreview] = useState(false);
  const [busyFmt, setBusyFmt] = useState<string | null>(null);
  const [error, setError] = useState<ApiError | null>(null);

  const loadHistory = useCallback(async () => {
    const data = await ropaService.listGenerations();
    setRows(Array.isArray(data.results) ? data.results : []);
  }, []);

  const refreshPreview = useCallback(async () => {
    setLoadingPreview(true);
    setError(null);
    try {
      const p = await ropaService.preview(regulation);
      setPreview(p);
    } catch (e) {
      setError(normalizeError(e));
    } finally {
      setLoadingPreview(false);
    }
  }, [regulation]);

  useEffect(() => {
    if (!enabled) return;
    loadHistory().catch((e) => setError(normalizeError(e)));
  }, [enabled, loadHistory]);

  useEffect(() => {
    if (!enabled) return;
    refreshPreview().catch(() => {});
  }, [enabled, refreshPreview]);

  const onGenerate = async (format: string) => {
    setBusyFmt(format);
    setError(null);
    try {
      await ropaService.generate(regulation, format);
      await loadHistory();
      await refreshPreview();
    } catch (e) {
      setError(normalizeError(e));
    } finally {
      setBusyFmt(null);
    }
  };

  const onDownload = async (id: string) => {
    setError(null);
    try {
      const { download_url: url } = await ropaService.downloadUrl(id);
      window.open(url, '_blank', 'noopener,noreferrer');
    } catch (e) {
      setError(normalizeError(e));
    }
  };

  if (!enabled) {
    return (
      <div className="tenant-form-group" data-testid="ropa-compliance-disabled">
        <p className="tenant-settings-description">
          RoPA generation is disabled for this tenant. Enable{' '}
          <strong>compliance_ropa_enabled</strong> via Tenant admin feature flags,
          then reload.
        </p>
      </div>
    );
  }

  return (
    <section className="tenant-form-group" data-testid="ropa-compliance-panel">
      <h3 className="tenant-settings-subheading">RoPA register (Article 30)</h3>
      <p className="tenant-settings-description">
        Preview completeness gaps derived from catalogued assets and linked retention policies.
      </p>

      <div className="tenant-form-group">
        <label htmlFor="ropa-regulation">Regulation focus</label>
        <select
          id="ropa-regulation"
          value={regulation}
          onChange={(e) => setRegulation(e.target.value)}
        >
          <option value="GDPR">GDPR</option>
          <option value="LGPD">LGPD</option>
          <option value="CCPA">CCPA</option>
        </select>
        <Button type="button" variant="secondary" onClick={() => refreshPreview()} disabled={loadingPreview}>
          {loadingPreview ? 'Refreshing…' : 'Refresh preview'}
        </Button>
      </div>

      {preview && (
        <div className="tenant-form-group">
          <p>
            <strong>Gaps detected:</strong> {preview.summary?.gap_count ?? preview.gaps?.length ?? 0}{' '}
            (cache hit: {preview.cache_hit ? 'yes' : 'no'})
          </p>
          <ul className="ropa-gap-list">
            {(preview.gaps ?? []).slice(0, 25).map((g) => (
              <li key={`${g.code}-${g.asset_key}`}>
                <strong>{g.code}</strong> — {g.asset_key}: {g.message}
                {g.fix_path ? (
                  <>
                    {' '}
                    <a href={g.fix_path}>Open fix target</a>
                  </>
                ) : null}
              </li>
            ))}
          </ul>
          {(preview.gaps?.length ?? 0) > 25 && (
            <p className="tenant-settings-description">Showing first 25 gaps; export full list via JSON/CSV.</p>
          )}
        </div>
      )}

      <div className="tenant-form-group">
        <span className="tenant-settings-description">Generate register</span>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
          {FORMATS.map((f) => (
            <Button
              key={f}
              type="button"
              variant="secondary"
              disabled={busyFmt !== null}
              loading={busyFmt === f}
              onClick={() => onGenerate(f)}
            >
              {f.toUpperCase()}
            </Button>
          ))}
        </div>
      </div>

      <div className="tenant-form-group">
        <h4>History</h4>
        {rows.length === 0 ? (
          <p>No generations yet.</p>
        ) : (
          <table className="tenant-table-lite">
            <thead>
              <tr>
                <th>Created</th>
                <th>Format</th>
                <th>Status</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.id}>
                  <td>{new Date(r.created_at).toLocaleString()}</td>
                  <td>{r.output_format}</td>
                  <td>{r.status}</td>
                  <td>
                    <Button
                      type="button"
                      variant="secondary"
                      disabled={r.status !== 'COMPLETED'}
                      onClick={() => onDownload(r.id)}
                    >
                      Download
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {error ? <ErrorDisplay error={error} /> : null}
    </section>
  );
}

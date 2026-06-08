/**
 * Phase 278.H.5 — Quick preview modal triggered from listing cards.
 *
 * Shows sample data, schema, quality metrics, and trust signals in a
 * compact modal — the "preview-before-buy" primary CTA.
 */
import { useState, useEffect, useRef, useCallback } from 'react';
import { listingService } from '../services/listingService';
import type { ListingPreview } from '../../../shared/types/marketplace';
import { LoadingSpinner } from '../../../shared/components/LoadingSpinner';
import {
  emitUxActivationEvent,
  type PreviewDetail,
} from '../../../shared/telemetry/uxActivationTelemetry';
import './QuickPreviewModal.css';

interface QuickPreviewModalProps {
  listingId: string;
  listingTitle: string;
  onClose: () => void;
}

export function QuickPreviewModal({ listingId, listingTitle, onClose }: QuickPreviewModalProps) {
  const [preview, setPreview] = useState<ListingPreview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const mountTimeRef = useRef(Date.now());
  const resultRef = useRef<PreviewDetail['result']>('dismissed');
  const hasEmittedOpened = useRef(false);

  // Emit opened once on mount
  useEffect(() => {
    if (!hasEmittedOpened.current) {
      hasEmittedOpened.current = true;
      mountTimeRef.current = Date.now();
      emitUxActivationEvent('meshant.preview.opened', {
        listing_id: listingId,
      } satisfies Partial<PreviewDetail>);
    }
  }, [listingId]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    listingService
      .previewJson(listingId)
      .then((data) => {
        if (!cancelled) {
          setPreview(data);
          setLoading(false);
          resultRef.current = 'loaded';
        }
      })
      .catch((err: Error) => {
        if (!cancelled) {
          setError(err?.message || 'Failed to load preview');
          setLoading(false);
          resultRef.current = 'error';
        }
      });

    return () => {
      cancelled = true;
    };
  }, [listingId]);

  const handleClose = useCallback(() => {
    emitUxActivationEvent('meshant.preview.closed', {
      listing_id: listingId,
      duration_ms: Date.now() - mountTimeRef.current,
      result: resultRef.current,
    } satisfies PreviewDetail);
    onClose();
  }, [listingId, onClose]);

  // Close on Escape key — matches ComparisonView behaviour and WCAG 2.1
  // Dialog (Modal) pattern (2.4.13 Focus Not Obscured / ESC dismiss).
  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') handleClose();
    };
    document.addEventListener('keydown', onKeyDown);
    return () => document.removeEventListener('keydown', onKeyDown);
  }, [handleClose]);

  return (
    <div
      className="quick-preview-overlay"
      data-testid="quick-preview-overlay"
      onClick={handleClose}
    >
      <div
        className="quick-preview-modal"
        data-testid="quick-preview-modal"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-label={`Preview: ${listingTitle}`}
      >
        <div className="quick-preview-header">
          <h3>Preview: {listingTitle}</h3>
          <button
            className="quick-preview-close"
            onClick={handleClose}
            aria-label="Close preview"
          >
            ✕
          </button>
        </div>

        <div className="quick-preview-body">
          {loading && (
            <div className="quick-preview-loading">
              <LoadingSpinner size="medium" />
              <p>Loading preview...</p>
            </div>
          )}

          {error && (
            <div className="quick-preview-error" role="alert">
              {error}
            </div>
          )}

          {preview && !loading && (
            <>
              {/* Sample Data */}
              <section className="qp-section">
                <h4>Sample Data</h4>
                {preview.sample_data && preview.sample_data.rows.length > 0 ? (
                  <>
                    <p className="qp-meta">
                      Showing {preview.sample_data.sample_size} of {preview.sample_data.total_rows} rows
                    </p>
                    <div className="qp-sample-table-wrapper">
                      <table className="qp-sample-table">
                        <thead>
                          <tr>
                            {Object.keys(preview.sample_data.rows[0] || {}).slice(0, 6).map((col) => (
                              <th key={col}>{col}</th>
                            ))}
                          </tr>
                        </thead>
                        <tbody>
                          {preview.sample_data.rows.slice(0, 5).map((row, i) => (
                            <tr key={i}>
                              {Object.values(row).slice(0, 6).map((val, j) => (
                                <td key={j}>{String(val ?? '—').slice(0, 80)}</td>
                              ))}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </>
                ) : (
                  <p className="qp-na">No sample data available.</p>
                )}
              </section>

              {/* Schema */}
              <section className="qp-section">
                <h4>Schema</h4>
                {preview.schema && (preview.schema as Record<string, Record<string, unknown>[]>).fields && (preview.schema as Record<string, Record<string, unknown>[]>).fields.length > 0 ? (
                  <div className="qp-schema-list">
                    {(preview.schema as Record<string, Record<string, unknown>[]>).fields.map((f: Record<string, unknown>, i: number) => (
                      <span key={i} className="qp-schema-field">
                        <code>{String(f.name ?? '')}</code>
                        <span className="qp-schema-type">{String(f.type ?? '')}</span>
                        {f.nullable ? <span className="qp-schema-nullable">nullable</span> : null}
                      </span>
                    ))}
                  </div>
                ) : (
                  <p className="qp-na">No schema available.</p>
                )}
              </section>

              {/* Quality Metrics */}
              {preview.quality_metrics && (
                <section className="qp-section">
                  <h4>Quality</h4>
                  <div className="qp-metrics">
                    {preview.quality_metrics.overall_score != null && (
                      <div className="qp-metric">
                        <span className="qp-metric-label">Overall</span>
                        <span className="qp-metric-value">
                          {(preview.quality_metrics.overall_score * 100).toFixed(0)}%
                        </span>
                      </div>
                    )}
                    {preview.quality_metrics.completeness != null && (
                      <div className="qp-metric">
                        <span className="qp-metric-label">Completeness</span>
                        <span className="qp-metric-value">
                          {(preview.quality_metrics.completeness * 100).toFixed(0)}%
                        </span>
                      </div>
                    )}
                    {preview.quality_metrics.freshness != null && (
                      <div className="qp-metric">
                        <span className="qp-metric-label">Freshness</span>
                        <span className="qp-metric-value">
                          {(preview.quality_metrics.freshness * 100).toFixed(0)}%
                        </span>
                      </div>
                    )}
                  </div>
                </section>
              )}

              {/* Trust Signals */}
              {preview.trust_signals && Object.keys(preview.trust_signals).length > 0 && (
                <section className="qp-section">
                  <h4>Trust Signals</h4>
                  <div className="qp-trust-signals">
                    {Object.entries(preview.trust_signals).map(([key, val]) => (
                      <span key={key} className="qp-trust-tag">
                        {key}: {String(val)}
                      </span>
                    ))}
                  </div>
                </section>
              )}
            </>
          )}
        </div>

        <div className="quick-preview-footer">
          <span className="qp-expires">
            Preview expires: {preview?.preview_expires_at
              ? new Date(preview.preview_expires_at).toLocaleTimeString()
              : '—'}
          </span>
          <button className="quick-preview-close-btn" onClick={handleClose}>
            Close
          </button>
        </div>
      </div>
    </div>
  );
}

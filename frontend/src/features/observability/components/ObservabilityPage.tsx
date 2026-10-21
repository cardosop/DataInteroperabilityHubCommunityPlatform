/**
 * Observability Dashboard
 * Tabs: Freshness, Volume, SLAs, Incidents (real API; no mocks)
 */

import { useState } from 'react';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { LoadingSpinner } from '../../../shared/components/LoadingSpinner';
import {
  useFreshnessDashboard,
  useIncidentsDashboard,
  useSlasDashboard,
  useVolumeDashboard,
} from '../hooks/useObservability';
import './ObservabilityPage.css';

type TabId = 'freshness' | 'volume' | 'slas' | 'incidents';

const TABS: { id: TabId; label: string }[] = [
  { id: 'freshness', label: 'Freshness' },
  { id: 'volume', label: 'Volume' },
  { id: 'slas', label: 'SLAs' },
  { id: 'incidents', label: 'Incidents' },
];

export function ObservabilityPage() {
  const [activeTab, setActiveTab] = useState<TabId>('freshness');

  const freshness = useFreshnessDashboard({ limit: 50 });
  const volume = useVolumeDashboard({ limit: 30 });
  const slas = useSlasDashboard({ limit: 100 });
  const incidents = useIncidentsDashboard({ limit: 100 });

  const renderSection = () => {
    if (activeTab === 'freshness') {
      if (freshness.isLoading) return <LoadingSpinner message="Loading freshness..." />;
      if (freshness.error)
        return (
          <ErrorDisplay
            error={freshness.error}
            title="Freshness"
            onRetry={() => freshness.refetch()}
          />
        );
      const results = freshness.data?.results ?? [];
      const summary = freshness.data?.summary ?? {};
      return (
        <section className="observability-section" data-testid="observability-freshness-section">
          <h2>Data Freshness</h2>
          {Object.keys(summary).length > 0 && (
            <div className="observability-summary">
              <pre>{JSON.stringify(summary, null, 2)}</pre>
            </div>
          )}
          {results.length === 0 ? (
            <p className="observability-no-data">No freshness data</p>
          ) : (
            <div className="observability-list">
              {results.slice(0, 20).map((r) => (
                <div key={r.id} className="observability-item">
                  {r.asset_id && <span>Asset: {r.asset_id}</span>}
                  {r.dataset_id && <span>Dataset: {r.dataset_id}</span>}
                  {r.is_stale != null && <span>Stale: {String(r.is_stale)}</span>}
                </div>
              ))}
            </div>
          )}
        </section>
      );
    }

    if (activeTab === 'volume') {
      if (volume.isLoading) return <LoadingSpinner message="Loading volume..." />;
      if (volume.error)
        return (
          <ErrorDisplay error={volume.error} title="Volume" onRetry={() => volume.refetch()} />
        );
      const results = volume.data?.results ?? [];
      const summary = volume.data?.summary ?? {};
      return (
        <section className="observability-section" data-testid="observability-volume-section">
          <h2>Data Volume</h2>
          {Object.keys(summary).length > 0 && (
            <div className="observability-summary">
              <pre>{JSON.stringify(summary, null, 2)}</pre>
            </div>
          )}
          {results.length === 0 ? (
            <p className="observability-no-data">No volume data</p>
          ) : (
            <div className="observability-list">
              {results.slice(0, 20).map((r) => (
                <div key={r.id} className="observability-item">
                  <span>
                    Period: {r.period_start} – {r.period_end}
                  </span>
                  {r.avg_row_count != null && <span>Avg rows: {r.avg_row_count}</span>}
                </div>
              ))}
            </div>
          )}
        </section>
      );
    }

    if (activeTab === 'slas') {
      if (slas.isLoading) return <LoadingSpinner message="Loading SLAs..." />;
      if (slas.error)
        return <ErrorDisplay error={slas.error} title="SLAs" onRetry={() => slas.refetch()} />;
      const results = Array.isArray((slas.data as { results?: unknown[] })?.results)
        ? (slas.data as { results: unknown[] }).results
        : [];
      return (
        <section className="observability-section" data-testid="observability-slas-section">
          <h2>Data SLAs</h2>
          {results.length === 0 ? (
            <p className="observability-no-data">No SLA data</p>
          ) : (
            <div className="observability-list">
              {results.slice(0, 20).map((item, i) => (
                <div key={i} className="observability-item">
                  <pre>{JSON.stringify(item)}</pre>
                </div>
              ))}
            </div>
          )}
        </section>
      );
    }

    if (activeTab === 'incidents') {
      if (incidents.isLoading) return <LoadingSpinner message="Loading incidents..." />;
      if (incidents.error)
        return (
          <ErrorDisplay
            error={incidents.error}
            title="Incidents"
            onRetry={() => incidents.refetch()}
          />
        );
      const results = Array.isArray((incidents.data as { results?: unknown[] })?.results)
        ? (incidents.data as { results: unknown[] }).results
        : [];
      return (
        <section className="observability-section" data-testid="observability-incidents-section">
          <h2>Incidents</h2>
          {results.length === 0 ? (
            <p className="observability-no-data">No incidents</p>
          ) : (
            <div className="observability-list">
              {results.slice(0, 20).map((item, i) => (
                <div key={i} className="observability-item">
                  <pre>{JSON.stringify(item)}</pre>
                </div>
              ))}
            </div>
          )}
        </section>
      );
    }

    return null;
  };

  return (
    <div className="observability-page" data-testid="observability-page">
      <header className="observability-header">
        <h1>Observability</h1>
        <p className="observability-subtitle">Freshness, volume, SLAs, and incidents (real API)</p>
      </header>

      <div className="observability-tabs" role="tablist" aria-label="Observability sections">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            type="button"
            role="tab"
            aria-selected={activeTab === tab.id}
            className={`observability-tab ${activeTab === tab.id ? 'active' : ''}`}
            onClick={() => setActiveTab(tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <div className="observability-content" role="tabpanel">
        {renderSection()}
      </div>
    </div>
  );
}

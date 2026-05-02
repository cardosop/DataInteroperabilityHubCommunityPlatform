/**
 * Tenant Settings Page
 * Usage display and config toggles for tenant admins.
 * Route: /settings/tenant
 */

import { useEffect, useState } from 'react';
import { Breadcrumbs } from '../../../shared/components/Breadcrumbs';
import { Button } from '../../../shared/components/Button';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { LoadingSpinner } from '../../../shared/components/LoadingSpinner';
import type { ApiError } from '../../../shared/types/api';
import type { TenantConfig, TenantConfigUpdate, TenantUsage } from '../../../shared/types/tenants';
import { normalizeError } from '../../../shared/utils/errorUtils';
import { tenantService } from '../services/tenantService';
import { SparqlFederationPanel } from './SparqlFederationPanel';
import './TenantSettingsPage.css';

const VALID_DQ_PROFILES = ['intake_basic_gx', 'intake_basic_soda'];
const VALID_COMPLIANCE_REGIMES = ['GDPR', 'LGPD', 'CCPA', 'HIPAA', 'SOX'];
const DATA_RETENTION_MIN = 90;
const DATA_RETENTION_MAX = 3650;

type Tab = 'usage' | 'config' | 'federation';

export function TenantSettingsPage() {
  const [activeTab, setActiveTab] = useState<Tab>('usage');
  const [usage, setUsage] = useState<TenantUsage | null>(null);
  const [config, setConfig] = useState<TenantConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const [defaultDqProfile, setDefaultDqProfile] = useState('');
  const [allowedCompliance, setAllowedCompliance] = useState<string[]>([]);
  const [defaultCompliance, setDefaultCompliance] = useState<string[]>([]);
  const [dataRetentionDays, setDataRetentionDays] = useState<string>('');
  const [maxFileSizeBytes, setMaxFileSizeBytes] = useState<string>('');
  const [maxJobConcurrency, setMaxJobConcurrency] = useState<string>('');
  const [maxQueuedJobs, setMaxQueuedJobs] = useState<string>('');
  const [trustSignalsEnabled, setTrustSignalsEnabled] = useState<boolean>(true);
  const [versioningEnabled, setVersioningEnabled] = useState<boolean>(true);
  const [workflowsEnabled, setWorkflowsEnabled] = useState<boolean>(true);
  const [validationErrors, setValidationErrors] = useState<Record<string, string>>({});

  const loadUsage = async () => {
    setError(null);
    try {
      const data = await tenantService.getMeUsage();
      setUsage(data);
    } catch (err) {
      setError(normalizeError(err));
    }
  };

  const loadConfig = async () => {
    setError(null);
    try {
      const data = await tenantService.getMeConfig();
      setConfig(data);
      setDefaultDqProfile(data.default_dq_profile ?? '');
      setAllowedCompliance(data.allowed_compliance_regimes ?? []);
      setDefaultCompliance(data.default_compliance_regimes ?? []);
      setDataRetentionDays(
        data.data_retention_days != null ? String(data.data_retention_days) : ''
      );
      setMaxFileSizeBytes(
        data.max_file_size_bytes != null ? String(data.max_file_size_bytes) : ''
      );
      setMaxJobConcurrency(
        data.max_job_concurrency != null ? String(data.max_job_concurrency) : ''
      );
      setMaxQueuedJobs(
        data.max_queued_jobs != null ? String(data.max_queued_jobs) : ''
      );
      setTrustSignalsEnabled(data.trust_signals_enabled ?? true);
      setVersioningEnabled(data.versioning_enabled ?? true);
      setWorkflowsEnabled(data.workflows_enabled ?? true);
    } catch (err) {
      setError(normalizeError(err));
    }
  };

  const loadAll = async () => {
    setLoading(true);
    await Promise.all([loadUsage(), loadConfig()]);
    setLoading(false);
  };

  /* eslint-disable react-hooks/exhaustive-deps */
  useEffect(() => {
    loadAll();
  }, []);
  /* eslint-enable react-hooks/exhaustive-deps */

  const validate = (): boolean => {
    const errs: Record<string, string> = {};
    if (dataRetentionDays.trim()) {
      const n = parseInt(dataRetentionDays, 10);
      if (isNaN(n) || n < DATA_RETENTION_MIN || n > DATA_RETENTION_MAX) {
        errs.data_retention_days = `Must be between ${DATA_RETENTION_MIN} and ${DATA_RETENTION_MAX} days`;
      }
    }
    if (maxFileSizeBytes.trim()) {
      const n = parseInt(maxFileSizeBytes, 10);
      if (isNaN(n) || n < 1) {
        errs.max_file_size_bytes = 'Must be a positive number';
      }
    }
    if (maxJobConcurrency.trim()) {
      const n = parseInt(maxJobConcurrency, 10);
      if (isNaN(n) || n < 1) {
        errs.max_job_concurrency = 'Must be a positive number';
      }
    }
    if (maxQueuedJobs.trim()) {
      const n = parseInt(maxQueuedJobs, 10);
      if (isNaN(n) || n < 1) {
        errs.max_queued_jobs = 'Must be a positive number';
      }
    }
    const allowedSet = new Set(allowedCompliance);
    if (defaultCompliance.length > 0 && !defaultCompliance.every((r) => allowedSet.has(r))) {
      errs.default_compliance_regimes = 'Default must be a subset of allowed regimes';
    }
    setValidationErrors(errs);
    return Object.keys(errs).length === 0;
  };

  const handleConfigSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSuccessMessage(null);
    if (!validate()) return;

    setSaving(true);
    setError(null);
    try {
      const payload: TenantConfigUpdate = {
        default_dq_profile: defaultDqProfile.trim() || null,
        allowed_compliance_regimes: allowedCompliance.length > 0 ? allowedCompliance : undefined,
        default_compliance_regimes: defaultCompliance.length > 0 ? defaultCompliance : undefined,
        data_retention_days: dataRetentionDays.trim()
          ? parseInt(dataRetentionDays, 10)
          : null,
        max_file_size_bytes: maxFileSizeBytes.trim()
          ? parseInt(maxFileSizeBytes, 10)
          : null,
        max_job_concurrency: maxJobConcurrency.trim()
          ? parseInt(maxJobConcurrency, 10)
          : null,
        max_queued_jobs: maxQueuedJobs.trim() ? parseInt(maxQueuedJobs, 10) : null,
        trust_signals_enabled: trustSignalsEnabled,
        versioning_enabled: versioningEnabled,
        workflows_enabled: workflowsEnabled,
      };
      const updated = await tenantService.patchMeConfig(payload);
      setConfig(updated);
      setSuccessMessage('Configuration updated successfully.');
    } catch (err) {
      setError(normalizeError(err));
    } finally {
      setSaving(false);
    }
  };

  const toggleAllowedCompliance = (regime: string) => {
    setAllowedCompliance((prev) =>
      prev.includes(regime) ? prev.filter((r) => r !== regime) : [...prev, regime]
    );
    setDefaultCompliance((prev) =>
      prev.includes(regime) ? prev.filter((r) => r !== regime) : prev
    );
  };

  const toggleDefaultCompliance = (regime: string) => {
    if (!allowedCompliance.includes(regime)) return;
    setDefaultCompliance((prev) =>
      prev.includes(regime) ? prev.filter((r) => r !== regime) : [...prev, regime]
    );
  };

  const formatBytes = (bytes: number): string => {
    if (bytes >= 1024 ** 3) return `${(bytes / 1024 ** 3).toFixed(2)} GB`;
    if (bytes >= 1024 ** 2) return `${(bytes / 1024 ** 2).toFixed(2)} MB`;
    if (bytes >= 1024) return `${(bytes / 1024).toFixed(2)} KB`;
    return `${bytes} B`;
  };

  if (loading && !usage && !config) {
    return <LoadingSpinner message="Loading tenant settings..." />;
  }

  if (error && !usage && !config) {
    return (
      <ErrorDisplay
        error={error}
        title="Failed to load tenant settings"
        onRetry={() => loadAll()}
      />
    );
  }

  return (
    <div className="tenant-settings-page" data-testid="tenant-settings-page">
      <Breadcrumbs
        items={[
          { label: 'Home', href: '/' },
          { label: 'Settings', href: '/settings/profile' },
          { label: 'Tenant' },
        ]}
      />
      <div className="tenant-settings-header">
        <h1>Tenant Settings</h1>
        <p className="tenant-settings-description">
          View usage and configure tenant settings (trust signals, data retention, limits).
        </p>
      </div>

      <div className="tenant-settings-tabs">
        <button
          type="button"
          className={`tenant-settings-tab ${activeTab === 'usage' ? 'active' : ''}`}
          onClick={() => setActiveTab('usage')}
          aria-selected={activeTab === 'usage'}
        >
          Usage
        </button>
        <button
          type="button"
          className={`tenant-settings-tab ${activeTab === 'config' ? 'active' : ''}`}
          onClick={() => setActiveTab('config')}
          aria-selected={activeTab === 'config'}
        >
          Configuration
        </button>
        <button
          type="button"
          className={`tenant-settings-tab ${activeTab === 'federation' ? 'active' : ''}`}
          onClick={() => setActiveTab('federation')}
          aria-selected={activeTab === 'federation'}
        >
          SPARQL Federation
        </button>
      </div>

      {activeTab === 'usage' && usage && (
        <section className="tenant-settings-usage" data-testid="tenant-settings-usage">
          <h2>Usage</h2>
          {usage.plan_slug && (
            <p className="tenant-settings-plan">
              Plan: <strong>{usage.plan_slug}</strong>
              {usage.plan_tier && ` (${usage.plan_tier})`}
            </p>
          )}
          <div className="tenant-settings-metrics">
            <div className="tenant-metric">
              <span className="tenant-metric-label">Storage</span>
              <span className="tenant-metric-value">
                {formatBytes(usage.storage_bytes)} ({usage.storage_gb.toFixed(2)} GB)
              </span>
              {usage.plan_limits.max_storage_gb != null && (
                <div className="tenant-metric-bar">
                  <div
                    className="tenant-metric-bar-fill"
                    style={{
                      width: `${Math.min(
                        (usage.usage_percentages?.max_storage_gb ?? 0),
                        100
                      )}%`,
                    }}
                  />
                </div>
              )}
            </div>
            <div className="tenant-metric">
              <span className="tenant-metric-label">API calls (this month)</span>
              <span className="tenant-metric-value">{usage.api_calls_this_month}</span>
              {usage.plan_limits.max_api_calls_per_month != null && (
                <div className="tenant-metric-bar">
                  <div
                    className="tenant-metric-bar-fill"
                    style={{
                      width: `${Math.min(
                        usage.usage_percentages?.max_api_calls_per_month ?? 0,
                        100
                      )}%`,
                    }}
                  />
                </div>
              )}
            </div>
            <div className="tenant-metric">
              <span className="tenant-metric-label">Assets</span>
              <span className="tenant-metric-value">{usage.asset_count}</span>
              {usage.plan_limits.max_assets != null && (
                <div className="tenant-metric-bar">
                  <div
                    className="tenant-metric-bar-fill"
                    style={{
                      width: `${Math.min(
                        usage.usage_percentages?.max_assets ?? 0,
                        100
                      )}%`,
                    }}
                  />
                </div>
              )}
            </div>
            <div className="tenant-metric">
              <span className="tenant-metric-label">Datasets</span>
              <span className="tenant-metric-value">{usage.dataset_count}</span>
              {usage.plan_limits.max_datasets != null && (
                <div className="tenant-metric-bar">
                  <div
                    className="tenant-metric-bar-fill"
                    style={{
                      width: `${Math.min(
                        usage.usage_percentages?.max_datasets ?? 0,
                        100
                      )}%`,
                    }}
                  />
                </div>
              )}
            </div>
            <div className="tenant-metric">
              <span className="tenant-metric-label">Scheduled ingestions</span>
              <span className="tenant-metric-value">{usage.scheduled_ingestion_count}</span>
            </div>
            <div className="tenant-metric">
              <span className="tenant-metric-label">Scheduled exports</span>
              <span className="tenant-metric-value">{usage.scheduled_export_count}</span>
            </div>
          </div>
        </section>
      )}

      {activeTab === 'config' && (
        <section className="tenant-settings-config" data-testid="tenant-settings-config">
          <h2>Configuration</h2>
          {!config && error ? (
            <ErrorDisplay
              error={error}
              title="Failed to load configuration"
              onRetry={() => loadConfig()}
            />
          ) : config ? (
          <form className="tenant-config-form" onSubmit={handleConfigSubmit}>
            {successMessage && (
              <div className="tenant-settings-success" role="status">
                {successMessage}
              </div>
            )}
            {error && (
              <div className="tenant-settings-error" role="alert">
                {error.error.message || 'An error occurred'}
              </div>
            )}

            <div className="tenant-form-group">
              <label htmlFor="tenant-default_dq_profile">Default DQ profile</label>
              <select
                id="tenant-default_dq_profile"
                value={defaultDqProfile}
                onChange={(e) => setDefaultDqProfile(e.target.value)}
              >
                <option value="">Platform default</option>
                {VALID_DQ_PROFILES.map((p) => (
                  <option key={p} value={p}>
                    {p}
                  </option>
                ))}
              </select>
            </div>

            <div className="tenant-form-group">
              <label>Allowed compliance regimes</label>
              <div className="tenant-checkbox-group">
                {VALID_COMPLIANCE_REGIMES.map((r) => (
                  <label key={r} className="tenant-checkbox">
                    <input
                      type="checkbox"
                      checked={allowedCompliance.includes(r)}
                      onChange={() => toggleAllowedCompliance(r)}
                    />
                    {r}
                  </label>
                ))}
              </div>
            </div>

            <div className="tenant-form-group">
              <label>Default compliance regimes</label>
              <div className="tenant-checkbox-group">
                {VALID_COMPLIANCE_REGIMES.map((r) => (
                  <label key={r} className="tenant-checkbox">
                    <input
                      type="checkbox"
                      checked={defaultCompliance.includes(r)}
                      onChange={() => toggleDefaultCompliance(r)}
                      disabled={!allowedCompliance.includes(r)}
                    />
                    {r}
                  </label>
                ))}
              </div>
              {validationErrors.default_compliance_regimes && (
                <span className="tenant-field-error">
                  {validationErrors.default_compliance_regimes}
                </span>
              )}
            </div>

            <div className="tenant-form-group">
              <label htmlFor="tenant-data_retention_days">Data retention (days)</label>
              <input
                id="tenant-data_retention_days"
                type="number"
                min={DATA_RETENTION_MIN}
                max={DATA_RETENTION_MAX}
                value={dataRetentionDays}
                onChange={(e) => setDataRetentionDays(e.target.value)}
                placeholder={`${DATA_RETENTION_MIN}-${DATA_RETENTION_MAX}`}
                aria-invalid={!!validationErrors.data_retention_days}
              />
              {validationErrors.data_retention_days && (
                <span className="tenant-field-error">
                  {validationErrors.data_retention_days}
                </span>
              )}
            </div>

            <div className="tenant-form-group">
              <label htmlFor="tenant-max_file_size_bytes">Max file size (bytes)</label>
              <input
                id="tenant-max_file_size_bytes"
                type="number"
                min={1}
                value={maxFileSizeBytes}
                onChange={(e) => setMaxFileSizeBytes(e.target.value)}
                placeholder="Platform default"
                aria-invalid={!!validationErrors.max_file_size_bytes}
              />
              {validationErrors.max_file_size_bytes && (
                <span className="tenant-field-error">
                  {validationErrors.max_file_size_bytes}
                </span>
              )}
            </div>

            <div className="tenant-form-group">
              <label htmlFor="tenant-max_job_concurrency">Max job concurrency</label>
              <input
                id="tenant-max_job_concurrency"
                type="number"
                min={1}
                value={maxJobConcurrency}
                onChange={(e) => setMaxJobConcurrency(e.target.value)}
                placeholder="Platform default"
                aria-invalid={!!validationErrors.max_job_concurrency}
              />
              {validationErrors.max_job_concurrency && (
                <span className="tenant-field-error">
                  {validationErrors.max_job_concurrency}
                </span>
              )}
            </div>

            <div className="tenant-form-group">
              <label htmlFor="tenant-max_queued_jobs">Max queued jobs</label>
              <input
                id="tenant-max_queued_jobs"
                type="number"
                min={1}
                value={maxQueuedJobs}
                onChange={(e) => setMaxQueuedJobs(e.target.value)}
                placeholder="Platform default"
                aria-invalid={!!validationErrors.max_queued_jobs}
              />
              {validationErrors.max_queued_jobs && (
                <span className="tenant-field-error">
                  {validationErrors.max_queued_jobs}
                </span>
              )}
            </div>

            <div className="tenant-form-group">
              <label htmlFor="tenant-trust_signals_enabled" className="tenant-toggle-label">
                <input
                  id="tenant-trust_signals_enabled"
                  type="checkbox"
                  checked={trustSignalsEnabled}
                  onChange={(e) => setTrustSignalsEnabled(e.target.checked)}
                  aria-describedby="trust-signals-hint"
                />
                <span>Trust signals enabled</span>
              </label>
              <p id="trust-signals-hint" className="tenant-field-hint">
                Enable trust signals (badges, quality SLAs) for marketplace listings.
              </p>
            </div>

            <div className="tenant-form-group">
              <label htmlFor="tenant-versioning_enabled" className="tenant-toggle-label">
                <input
                  id="tenant-versioning_enabled"
                  type="checkbox"
                  checked={versioningEnabled}
                  onChange={(e) => setVersioningEnabled(e.target.checked)}
                  aria-describedby="versioning-hint"
                />
                <span>Versioning enabled</span>
              </label>
              <p id="versioning-hint" className="tenant-field-hint">
                Enable dataset versioning (semantic versions, version history) for this tenant.
              </p>
            </div>

            <div className="tenant-form-group">
              <label htmlFor="tenant-workflows_enabled" className="tenant-toggle-label">
                <input
                  id="tenant-workflows_enabled"
                  type="checkbox"
                  checked={workflowsEnabled}
                  onChange={(e) => setWorkflowsEnabled(e.target.checked)}
                  aria-describedby="workflows-hint"
                />
                <span>Workflows enabled</span>
              </label>
              <p id="workflows-hint" className="tenant-field-hint">
                Enable workflow orchestration for this tenant.
              </p>
            </div>

            <div className="tenant-form-actions">
              <Button variant="primary" type="submit" loading={saving}>
                Save
              </Button>
            </div>
          </form>
          ) : (
            <LoadingSpinner message="Loading configuration..." />
          )}
        </section>
      )}

      {activeTab === 'federation' && (
        config && config.tenant_id ? (
          <SparqlFederationPanel tenantId={config.tenant_id} />
        ) : (
          <LoadingSpinner message="Loading tenant context..." />
        )
      )}
    </div>
  );
}

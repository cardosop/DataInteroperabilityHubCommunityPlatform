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
import {
  COMPLIANCE_RISK_THRESHOLDS,
  isComplianceRiskThreshold,
} from '../../../shared/types/tenants';
import type {
  ComplianceRiskThreshold,
  TenantConfig,
  TenantConfigUpdate,
  TenantUsage,
} from '../../../shared/types/tenants';
import { normalizeError } from '../../../shared/utils/errorUtils';
import {
  QUOTA_WARN_THRESHOLD_PERCENT,
  severityForQuota,
} from '../../files/utils/quotaFormatting';
import { tenantService } from '../services/tenantService';
import { SparqlFederationPanel } from './SparqlFederationPanel';
import { RopaCompliancePanel } from './RopaCompliancePanel';
import { DpiaCompliancePanel } from './DpiaCompliancePanel';
import { AuditRetentionPolicyPanel } from '../../audit/components/AuditRetentionPolicyPanel';
import {
  ConnectOnboardingBanner,
} from '../../marketplace/components/ConnectOnboardingBanner';
import {
  ConnectStatusBadge,
} from '../../marketplace/components/ConnectStatusBadge';
import './TenantSettingsPage.css';

const VALID_DQ_PROFILES = ['intake_basic_gx', 'intake_basic_soda'];
const VALID_COMPLIANCE_REGIMES = ['GDPR', 'LGPD', 'CCPA', 'HIPAA', 'SOX'];
// `COMPLIANCE_RISK_THRESHOLDS` is now imported from
// `shared/types/tenants` so the same const tuple drives the type union
// AND the runtime guard AND this `<select>` option list — single source
// of truth for the backend `RiskLevel` choices.
const DATA_RETENTION_MIN = 90;
const DATA_RETENTION_MAX = 3650;

type Tab = 'usage' | 'config' | 'compliance' | 'federation' | 'audit' | 'billing';

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
  const [complianceRiskThreshold, setComplianceRiskThreshold] =
    useState<ComplianceRiskThreshold>('HIGH');
  // Phase 270.C.4 — per-tenant compliance legal-basis strict mode.
  // Default false so a tenant operator opts-in explicitly; the
  // env-aware backend default (True in prod, False elsewhere) is
  // applied at tenant CREATION; this UI surfaces the per-tenant
  // current value + lets the operator override.
  const [complianceLegalBasisStrict, setComplianceLegalBasisStrict] =
    useState<boolean>(false);
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
      setComplianceRiskThreshold(data.compliance_risk_threshold ?? 'HIGH');
      setComplianceLegalBasisStrict(data.compliance_legal_basis_strict ?? false);
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
        compliance_risk_threshold: complianceRiskThreshold,
        compliance_legal_basis_strict: complianceLegalBasisStrict,
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
          className={`tenant-settings-tab ${activeTab === 'compliance' ? 'active' : ''}`}
          onClick={() => setActiveTab('compliance')}
          aria-selected={activeTab === 'compliance'}
        >
          Compliance
        </button>
        <button
          type="button"
          className={`tenant-settings-tab ${activeTab === 'federation' ? 'active' : ''}`}
          onClick={() => setActiveTab('federation')}
          aria-selected={activeTab === 'federation'}
        >
          SPARQL Federation
        </button>
        <button
          type="button"
          className={`tenant-settings-tab ${activeTab === 'audit' ? 'active' : ''}`}
          onClick={() => setActiveTab('audit')}
          aria-selected={activeTab === 'audit'}
        >
          Audit
        </button>
        {/* Phase 270.D.6 — Tax & Billing Identity tab. */}
        <button
          type="button"
          className={`tenant-settings-tab ${activeTab === 'billing' ? 'active' : ''}`}
          onClick={() => setActiveTab('billing')}
          aria-selected={activeTab === 'billing'}
        >
          Tax &amp; Billing
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
          {(() => {
            const anyAtRisk = Object.entries(usage.usage_percentages ?? {}).some(
              ([, pct]) => typeof pct === 'number' && pct >= QUOTA_WARN_THRESHOLD_PERCENT,
            );
            return anyAtRisk ? (
              <p className="tenant-settings-upgrade-cta" data-testid="usage-upgrade-cta">
                <a href="/settings/billing">Upgrade plan</a> to increase limits.
              </p>
            ) : null;
          })()}
          <div className="tenant-settings-metrics">
            {((
              metrics: Array<{
                label: string; value: string; max: number | null;
                pct: number | null;
              }>,
            ) =>
              metrics.map((m) => {
                const pct = m.pct ?? 0;
                const severity = severityForQuota(pct);
                const barClass = `tenant-metric-bar-fill tenant-metric-bar-fill--${severity}`;
                return (
                  <div className="tenant-metric" key={m.label}>
                    <span className="tenant-metric-label">{m.label}</span>
                    <span className="tenant-metric-value">
                      {m.value}
                      {m.max != null && ` / ${m.max}`}
                    </span>
                    {m.max != null && (
                      <div
                        className="tenant-metric-bar"
                        role="progressbar"
                        aria-valuenow={Math.min(pct, 100)}
                        aria-valuemin={0}
                        aria-valuemax={100}
                        aria-label={`${m.label} usage: ${Math.round(pct)}%`}
                      >
                        <div
                          className={barClass}
                          style={{ width: `${Math.min(pct, 100)}%` }}
                        />
                      </div>
                    )}
                  </div>
                );
              })
            )([
              {
                label: 'Storage',
                value: `${formatBytes(usage.storage_bytes)} (${usage.storage_gb.toFixed(2)} GB)`,
                max: usage.plan_limits.max_storage_gb,
                pct: usage.usage_percentages?.max_storage_gb ?? null,
              },
              {
                label: 'API calls (this month)',
                value: `${usage.api_calls_this_month}`,
                max: usage.plan_limits.max_api_calls_per_month,
                pct: usage.usage_percentages?.max_api_calls_per_month ?? null,
              },
              {
                label: 'Assets',
                value: `${usage.asset_count}`,
                max: usage.plan_limits.max_assets,
                pct: usage.usage_percentages?.max_assets ?? null,
              },
              {
                label: 'Datasets',
                value: `${usage.dataset_count}`,
                max: usage.plan_limits.max_datasets,
                pct: usage.usage_percentages?.max_datasets ?? null,
              },
            ])}
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
              <label htmlFor="tenant-compliance_risk_threshold">Compliance risk threshold</label>
              <p className="tenant-settings-description">
                Listing publish and asset activation require a succeeded compliance run at or below this
                risk ceiling.
              </p>
              <select
                id="tenant-compliance_risk_threshold"
                value={complianceRiskThreshold}
                onChange={(e) => {
                  // Defence-in-depth: the <select>'s `<option>` list is
                  // already constrained to `COMPLIANCE_RISK_THRESHOLDS`,
                  // but the type guard means a future option-list typo
                  // (or a programmatic setter from a test) cannot
                  // smuggle a non-union value into state.
                  const next = e.target.value;
                  if (isComplianceRiskThreshold(next)) {
                    setComplianceRiskThreshold(next);
                  }
                }}
              >
                {COMPLIANCE_RISK_THRESHOLDS.map((t) => (
                  <option key={t} value={t}>
                    {t}
                  </option>
                ))}
              </select>
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

            {/* Phase 270.C.4.5 — per-tenant legal-basis strict mode toggle.
                Surfaces the Tenant.compliance_legal_basis_strict field
                introduced in Phase 270.C.4.1. Strict mode rejects
                compliance scans missing a valid GDPR/UK_GDPR/LGPD
                legal_basis with HTTP 422; lenient mode (the default)
                preserves the Phase 19.7.1 behaviour. */}
            <div className="tenant-form-group">
              <label
                htmlFor="tenant-compliance_legal_basis_strict"
                className="tenant-toggle-label"
              >
                <input
                  id="tenant-compliance_legal_basis_strict"
                  type="checkbox"
                  checked={complianceLegalBasisStrict}
                  onChange={(e) =>
                    setComplianceLegalBasisStrict(e.target.checked)
                  }
                  aria-describedby="compliance-legal-basis-strict-hint"
                />
                <span>Strict legal-basis enforcement</span>
              </label>
              <p
                id="compliance-legal-basis-strict-hint"
                className="tenant-field-hint"
              >
                <strong>Strict</strong> (recommended for production
                tenants under GDPR/UK GDPR/LGPD): compliance scans
                that detect personal data but are missing a valid{' '}
                <code>legal_basis</code> are <strong>rejected</strong>{' '}
                with HTTP 422. <strong>Lenient</strong> (default in
                staging/dev): the scan succeeds and the missing
                basis appears as an ERROR-severity issue in the
                report. New production tenants default to strict;
                pre-existing tenants default to lenient (opt-in
                here).
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

      {activeTab === 'compliance' && (
        <section className="tenant-settings-compliance" data-testid="tenant-settings-compliance">
          <h2>Compliance</h2>
          <p className="tenant-settings-description">
            Record of processing activities (RoPA) preview, exports, and history.
          </p>
          <RopaCompliancePanel />
          <DpiaCompliancePanel />
        </section>
      )}

      {activeTab === 'federation' && (
        config && config.tenant_id ? (
          <SparqlFederationPanel tenantId={config.tenant_id} />
        ) : (
          <LoadingSpinner message="Loading tenant context..." />
        )
      )}

      {activeTab === 'audit' && <AuditRetentionPolicyPanel />}

      {/* Phase 270.D.6 — Tax & Billing Identity panel. */}
      {activeTab === 'billing' && <TaxBillingIdentityPanel />}
      {/* Phase 271.3 — Stripe Connect onboarding status. */}
      {activeTab === 'billing' && <ConnectAccountPanel />}
    </div>
  );
}


// ---------------------------------------------------------------------------
// Phase 270.D.6 — Tax & Billing Identity panel
// ---------------------------------------------------------------------------

/**
 * Surface for ``GET /api/v1/tenants/me/tax-id/`` +
 * ``POST /api/v1/tenants/me/tax-id/``. Shows the current tax_id
 * (masked-on-display so non-admin viewers don't see the full
 * value), the type, the Stripe verification badge, and the
 * registered address. The submission form re-uses the same
 * endpoint — POSTing replaces the stored value AND resets
 * ``tax_id_verified`` to False pending Stripe's verification
 * webhook.
 *
 * Tax-id-type select carries the Stripe-vocabulary values
 * (``eu_vat``, ``gb_vat``, ``us_ein``, ``br_cnpj``); the full
 * Stripe list has ~40 entries — surfacing the most-common 8
 * here, with a free-text fallback for the rest. Tenants with
 * niche jurisdictions can submit via the API directly while
 * the UI catches the rest.
 */
function TaxBillingIdentityPanel(): React.ReactElement {
  const [taxId, setTaxId] = useState<string>('');
  const [taxIdType, setTaxIdType] = useState<string>('eu_vat');
  const [taxAddressCountry, setTaxAddressCountry] = useState<string>('');
  const [taxAddressPostal, setTaxAddressPostal] = useState<string>('');
  const [taxAddressLine1, setTaxAddressLine1] = useState<string>('');
  const [taxIdVerified, setTaxIdVerified] = useState<boolean>(false);
  const [storedTaxId, setStoredTaxId] = useState<string>('');
  const [loading, setLoadingState] = useState(true);
  const [saving, setSavingState] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  // Load existing tax identity.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoadingState(true);
      try {
        const data = await tenantService.getMeTaxId();
        if (cancelled) return;
        setStoredTaxId(data.tax_id || '');
        setTaxId(data.tax_id || '');
        setTaxIdType(data.tax_id_type || 'eu_vat');
        setTaxIdVerified(!!data.tax_id_verified);
        const addr = (data.tax_address || {}) as {
          country?: string;
          postal_code?: string;
          line1?: string;
        };
        setTaxAddressCountry(String(addr.country || ''));
        setTaxAddressPostal(String(addr.postal_code || ''));
        setTaxAddressLine1(String(addr.line1 || ''));
      } catch (err) {
        if (!cancelled) setError((normalizeError(err) as ApiError).error?.message || 'Failed to load tax identity');
      } finally {
        if (!cancelled) setLoadingState(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccess(null);
    if (!taxId.trim() || !taxIdType.trim()) {
      setError('Tax ID and type are required.');
      return;
    }
    setSavingState(true);
    try {
      const data = await tenantService.postMeTaxId({
        tax_id: taxId.trim(),
        tax_id_type: taxIdType.trim(),
        tax_address: {
          country: taxAddressCountry.trim(),
          postal_code: taxAddressPostal.trim(),
          line1: taxAddressLine1.trim(),
        },
      });
      setStoredTaxId(data.tax_id ?? '');
      setTaxIdVerified(!!data.tax_id_verified);
      setSuccess(
        'Submitted. Stripe is verifying your tax ID — the badge will turn green once verification completes.',
      );
    } catch (err) {
      setError((normalizeError(err) as ApiError).error?.message || 'Failed to save tax identity');
    } finally {
      setSavingState(false);
    }
  };

  if (loading) return <LoadingSpinner message="Loading tax identity..." />;

  return (
    <section
      className="tenant-settings-tax-billing"
      data-testid="tenant-settings-tax-billing"
    >
      <h2>Tax &amp; Billing Identity</h2>
      <p className="tenant-field-hint">
        Configure your tax registration ID. Stripe validates the ID and applies
        the correct tax handling (B2B reverse-charge for verified EU VAT IDs,
        local VAT/sales tax otherwise) on every invoice and one-time payment.
      </p>

      {storedTaxId && (
        <p className="tenant-field-hint">
          Current tax ID: <code>{storedTaxId}</code>{' '}
          <span
            data-testid="tax-id-verified-badge"
            style={{
              padding: '2px 8px',
              borderRadius: 4,
              background: taxIdVerified ? '#d1fae5' : '#fef3c7',
              color: taxIdVerified ? '#065f46' : '#92400e',
              fontWeight: 600,
              fontSize: 12,
              marginLeft: 8,
            }}
          >
            {taxIdVerified ? '✓ Verified' : '⏳ Pending verification'}
          </span>
        </p>
      )}

      {error && (
        <div className="tenant-form-error" role="alert">
          {error}
        </div>
      )}
      {success && (
        <div className="tenant-form-success" role="status">
          {success}
        </div>
      )}

      <form onSubmit={handleSubmit} className="tenant-form">
        <div className="tenant-form-group">
          <label htmlFor="tax-id-input">Tax ID</label>
          <input
            id="tax-id-input"
            type="text"
            value={taxId}
            onChange={(e) => setTaxId(e.target.value)}
            placeholder="e.g. GB123456789, BR12345678000199"
          />
        </div>

        <div className="tenant-form-group">
          <label htmlFor="tax-id-type-select">Tax ID type</label>
          <select
            id="tax-id-type-select"
            value={taxIdType}
            onChange={(e) => setTaxIdType(e.target.value)}
          >
            <option value="eu_vat">EU VAT</option>
            <option value="gb_vat">UK VAT (GB)</option>
            <option value="us_ein">US EIN</option>
            <option value="br_cnpj">Brazil CNPJ</option>
            <option value="in_gst">India GST</option>
            <option value="au_abn">Australia ABN</option>
            <option value="ca_bn">Canada BN</option>
            <option value="sg_uen">Singapore UEN</option>
          </select>
        </div>

        <div className="tenant-form-group">
          <label htmlFor="tax-address-country">Country (ISO code)</label>
          <input
            id="tax-address-country"
            type="text"
            value={taxAddressCountry}
            onChange={(e) => setTaxAddressCountry(e.target.value)}
            placeholder="GB"
            maxLength={2}
          />
        </div>

        <div className="tenant-form-group">
          <label htmlFor="tax-address-postal">Postal code</label>
          <input
            id="tax-address-postal"
            type="text"
            value={taxAddressPostal}
            onChange={(e) => setTaxAddressPostal(e.target.value)}
          />
        </div>

        <div className="tenant-form-group">
          <label htmlFor="tax-address-line1">Address line 1</label>
          <input
            id="tax-address-line1"
            type="text"
            value={taxAddressLine1}
            onChange={(e) => setTaxAddressLine1(e.target.value)}
          />
        </div>

        <div className="tenant-form-actions">
          <Button type="submit" variant="primary" loading={saving}>
            Submit tax ID
          </Button>
        </div>
      </form>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Phase 271.3 — Stripe Connect account status panel
// ---------------------------------------------------------------------------

/**
 * Embedded Connect onboarding panel rendered inside the "Billing" tab
 * of TenantSettingsPage.  Fetches the current ``ConnectAccount`` state
 * from ``GET /api/v1/billing/connect/status/`` and renders either:
 *
 * - An onboarding CTA banner when no ConnectAccount exists yet, OR
 * - A status badge + a link to the provider revenue dashboard when
 *   the account exists.
 */
function ConnectAccountPanel() {
  interface AccountStatus {
    stripe_account_id: string;
    account_type: string;
    charges_enabled: boolean;
    payouts_enabled: boolean;
    details_submitted: boolean;
    country: string;
    default_currency: string;
  }

  const [status, setStatus] = useState<AccountStatus | null>(null);
  const [connected, setConnected] = useState<boolean | null>(null);
  const [loadingStatus, setLoadingStatus] = useState(true);
  const [statusError, setStatusError] = useState<string | null>(null);

  useEffect(() => {
    const token = localStorage.getItem('access_token');
    if (!token) return;
    fetch('/api/v1/billing/connect/status/', {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then(async (res) => {
        if (res.status === 404) {
          setConnected(false);
          setLoadingStatus(false);
          return;
        }
        if (!res.ok) {
          const body = await res.json().catch(() => ({}));
          setStatusError(body.detail || 'Failed to load Connect status');
          setLoadingStatus(false);
          return;
        }
        const data = await res.json();
        setStatus(data);
        setConnected(true);
        setLoadingStatus(false);
      })
      .catch(() => {
        setStatusError('Network error loading Connect status');
        setLoadingStatus(false);
      });
  }, []);

  if (loadingStatus) {
    return <LoadingSpinner message="Loading Connect account status..." />;
  }

  if (statusError) {
    return <ErrorDisplay error={statusError} />;
  }

  return (
    <section className="tenant-settings-tax-billing" data-testid="tenant-settings-connect">
      <h3>Stripe Connect (Provider Payouts)</h3>

      {!connected && (
        <ConnectOnboardingBanner
          reason="Complete Stripe Connect onboarding to publish paid listings and
receive payouts."
        />
      )}

      {connected && status && (
        <div className="connect-account-summary">
          <div className="connect-account-summary__row">
            <span className="connect-account-summary__label">Status</span>
            <ConnectStatusBadge
              chargesEnabled={status.charges_enabled}
              payoutsEnabled={status.payouts_enabled}
              detailsSubmitted={status.details_submitted}
            />
          </div>
          {status.country && (
            <div className="connect-account-summary__row">
              <span className="connect-account-summary__label">Country</span>
              <span>{status.country}</span>
            </div>
          )}
          {status.default_currency && (
            <div className="connect-account-summary__row">
              <span className="connect-account-summary__label">Currency</span>
              <span>{status.default_currency.toUpperCase()}</span>
            </div>
          )}
          <a href="/settings/revenue" className="connect-account-summary__link">
            View payout history →
          </a>
        </div>
      )}
    </section>
  );
}

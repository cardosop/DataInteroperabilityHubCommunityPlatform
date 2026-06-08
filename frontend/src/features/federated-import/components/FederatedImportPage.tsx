/**
 * 284.A.5 — FederatedImportPage.
 *
 * Provider listing with import form (credential_ref, never raw creds),
 * job status polling, and cancel capability. Gated behind
 * ``CapabilityRoute capability="federated_import"``.
 */
import React, { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { apiClient } from '../../../shared/api/client';
import { CapabilityRoute } from '../../../shared/components/CapabilityRoute';

interface Provider {
  id: string;
  name: string;
  description: string;
  credential_type: string;
}

interface ImportJob {
  id: string;
  type: string;
  status: string;
  provider_id: string;
  data_strategy: string;
  details: Record<string, unknown>;
  created_at: string;
  updated_at?: string;
  completed_at?: string;
}

type JobStatus = 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED' | 'CANCELLED';

const STATUS_LABELS: Record<JobStatus, string> = {
  PENDING: 'Pending',
  RUNNING: 'Running',
  COMPLETED: 'Completed',
  FAILED: 'Failed',
  CANCELLED: 'Cancelled',
};

export const FederatedImportPage: React.FC = () => {
  const { t } = useTranslation();
  const [providers, setProviders] = useState<Provider[]>([]);
  const [loadingProviders, setLoadingProviders] = useState(true);
  const [selectedProvider, setSelectedProvider] = useState<string>('');
  const [credentialRef, setCredentialRef] = useState('');
  const [externalListingId, setExternalListingId] = useState('');
  const [dataStrategy, setDataStrategy] = useState<'METADATA_ONLY' | 'DOWNLOAD_SELECTIVE' | 'DOWNLOAD_ALL'>('METADATA_ONLY');
  const [importing, setImporting] = useState(false);
  const [activeJob, setActiveJob] = useState<ImportJob | null>(null);
  const [error, setError] = useState<string | null>(null);

  const fetchProviders = useCallback(async () => {
    setLoadingProviders(true);
    try {
      const resp = await apiClient.getClient().get<{ providers: Provider[]; count: number }>(
        '/api/v1/integrations/federated-import/providers/'
      );
      setProviders(resp.data.providers || []);
    } catch {
      setError(t('federatedImport.errors.providersFailed', 'Failed to load providers.'));
    } finally {
      setLoadingProviders(false);
    }
  }, [t]);

  useEffect(() => {
    fetchProviders();
  }, [fetchProviders]);

  const handleCreateImport = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedProvider) {
      setError(t('federatedImport.errors.noProvider', 'Select a provider.'));
      return;
    }
    if (!credentialRef || !credentialRef.startsWith('arn:aws:secretsmanager:')) {
      setError(t('federatedImport.errors.invalidArn', 'Enter a valid AWS Secrets Manager ARN.'));
      return;
    }
    setImporting(true);
    setError(null);
    try {
      const resp = await apiClient.getClient().post<ImportJob>(
        '/api/v1/integrations/federated-import/imports/',
        {
          provider_id: selectedProvider,
          credential_ref: credentialRef,
          external_listing_id: externalListingId,
          data_strategy: dataStrategy,
        }
      );
      setActiveJob(resp.data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Import creation failed.');
    } finally {
      setImporting(false);
    }
  };

  const pollJobStatus = useCallback(async () => {
    if (!activeJob || activeJob.status === 'COMPLETED' || activeJob.status === 'FAILED' || activeJob.status === 'CANCELLED') {
      return;
    }
    try {
      const resp = await apiClient.getClient().get<ImportJob>(
        `/api/v1/integrations/federated-import/imports/${activeJob.id}/`
      );
      setActiveJob(resp.data);
    } catch {
      // Silently retry on next poll
    }
  }, [activeJob]);

  useEffect(() => {
    if (!activeJob) return;
    const interval = setInterval(pollJobStatus, 5000);
    return () => clearInterval(interval);
  }, [activeJob, pollJobStatus]);

  const handleCancel = async () => {
    if (!activeJob) return;
    try {
      const resp = await apiClient.getClient().post<ImportJob>(
        `/api/v1/integrations/federated-import/imports/${activeJob.id}/cancel/`
      );
      setActiveJob(resp.data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Cancel failed.');
    }
  };

  return (
    <CapabilityRoute capability="federated_import">
      <div className="federated-import-page" data-testid="federated-import-page">
        <h1>{t('federatedImport.title', 'Federated Import')}</h1>

        {error && (
          <div className="error-banner" role="alert" data-testid="import-error">
            {error}
            <button onClick={() => setError(null)} aria-label={t('common.dismiss', 'Dismiss')}>×</button>
          </div>
        )}

        {/* Provider list */}
        <section>
          <h2>{t('federatedImport.providers', 'Providers')}</h2>
          {loadingProviders ? (
            <div className="spinner" data-testid="providers-loading" aria-busy="true">
              {t('federatedImport.loadingProviders', 'Loading providers…')}
            </div>
          ) : (
            <table data-testid="providers-table">
              <thead>
                <tr>
                  <th>{t('federatedImport.providerName', 'Name')}</th>
                  <th>{t('federatedImport.providerType', 'Credential Type')}</th>
                  <th>{t('federatedImport.providerDescription', 'Description')}</th>
                </tr>
              </thead>
              <tbody>
                {providers.map((p) => (
                  <tr key={p.id}>
                    <td>{p.name}</td>
                    <td>{p.credential_type}</td>
                    <td>{p.description}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>

        {/* Import form */}
        <section>
          <h2>{t('federatedImport.createImport', 'Create Import')}</h2>
          <form onSubmit={handleCreateImport} data-testid="import-form">
            <div className="form-field">
              <label htmlFor="provider-select">{t('federatedImport.selectProvider', 'Provider')}</label>
              <select
                id="provider-select"
                value={selectedProvider}
                onChange={(e) => setSelectedProvider(e.target.value)}
                data-testid="provider-select"
              >
                <option value="">{t('federatedImport.selectProviderPlaceholder', '-- Select --')}</option>
                {providers.map((p) => (
                  <option key={p.id} value={p.id}>{p.name}</option>
                ))}
              </select>
            </div>
            <div className="form-field">
              <label htmlFor="credential-ref">{t('federatedImport.credentialRef', 'Credential ARN')}</label>
              <input
                id="credential-ref"
                type="text"
                value={credentialRef}
                onChange={(e) => setCredentialRef(e.target.value)}
                placeholder="arn:aws:secretsmanager:..."
                data-testid="credential-ref-input"
              />
              <small>{t('federatedImport.credentialRefHint', 'AWS Secrets Manager ARN. Raw credentials are never accepted.')}</small>
            </div>
            <div className="form-field">
              <label htmlFor="listing-id">{t('federatedImport.externalListingId', 'External Listing ID (optional)')}</label>
              <input
                id="listing-id"
                type="text"
                value={externalListingId}
                onChange={(e) => setExternalListingId(e.target.value)}
                data-testid="listing-id-input"
              />
            </div>
            <div className="form-field">
              <label htmlFor="data-strategy">{t('federatedImport.dataStrategy', 'Data Strategy')}</label>
              <select
                id="data-strategy"
                value={dataStrategy}
                onChange={(e) => setDataStrategy(e.target.value as typeof dataStrategy)}
                data-testid="data-strategy-select"
              >
                <option value="METADATA_ONLY">{t('federatedImport.metadataOnly', 'Metadata Only')}</option>
                <option value="DOWNLOAD_SELECTIVE">{t('federatedImport.downloadSelective', 'Download Selective')}</option>
                <option value="DOWNLOAD_ALL">{t('federatedImport.downloadAll', 'Download All')}</option>
              </select>
            </div>
            <button type="submit" disabled={importing} data-testid="create-import-btn">
              {importing ? t('federatedImport.creating', 'Creating…') : t('federatedImport.create', 'Create Import')}
            </button>
          </form>
        </section>

        {/* Active job status */}
        {activeJob && (
          <section data-testid="active-job-section">
            <h2>{t('federatedImport.jobStatus', 'Import Job')}</h2>
            <dl>
              <dt>{t('federatedImport.jobId', 'Job ID')}</dt>
              <dd data-testid="job-id">{activeJob.id}</dd>
              <dt>{t('federatedImport.status', 'Status')}</dt>
              <dd data-testid="job-status">{STATUS_LABELS[activeJob.status as JobStatus] || activeJob.status}</dd>
              <dt>{t('federatedImport.provider', 'Provider')}</dt>
              <dd>{activeJob.provider_id}</dd>
              <dt>{t('federatedImport.strategy', 'Strategy')}</dt>
              <dd>{activeJob.data_strategy}</dd>
            </dl>
            {(activeJob.status === 'PENDING' || activeJob.status === 'RUNNING') && (
              <button onClick={handleCancel} data-testid="cancel-job-btn">
                {t('federatedImport.cancel', 'Cancel Import')}
              </button>
            )}
          </section>
        )}
      </div>
    </CapabilityRoute>
  );
};

export default FederatedImportPage;

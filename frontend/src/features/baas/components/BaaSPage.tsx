/**
 * BaaS Page
 * Displays API key management and usage dashboards
 */

import { useState } from 'react';
import { useAPIKeys, useCreateAPIKey, useRevokeAPIKey, useUsageStats, useUsageByEndpoint } from '../hooks/useBaaS';
import { ConfirmDialog } from '../../../shared/components/ConfirmDialog';
import { LoadingSpinner } from '../../../shared/components/LoadingSpinner';
import { useToast } from '../../../shared/components/Toast';
import { normalizeError } from '../../../shared/utils/errorUtils';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { EmptyState } from '../../../shared/components/EmptyState';
import { APITier } from '../../../shared/types/baas';
import './BaaSPage.css';

type TabType = 'api-keys' | 'usage';

export function BaaSPage() {
  const [activeTab, setActiveTab] = useState<TabType>('api-keys');
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [apiKeyName, setAPIKeyName] = useState('');
  const [apiKeyTier, setAPIKeyTier] = useState<APITier>(APITier.FREE);
  const [newAPIKey, setNewAPIKey] = useState<string | null>(null);

  const { data: apiKeysData, isLoading: apiKeysLoading, error: apiKeysError, refetch: refetchAPIKeys } = useAPIKeys();
  const { data: usageStats, isLoading: usageLoading, error: usageError } = useUsageStats();
  const { data: usageByEndpoint, isLoading: endpointLoading } = useUsageByEndpoint();
  const createAPIKeyMutation = useCreateAPIKey();
  const revokeAPIKeyMutation = useRevokeAPIKey();
  const toast = useToast();
  const [confirmRevokeId, setConfirmRevokeId] = useState<string | null>(null);

  const handleCreateAPIKey = async () => {
    if (!apiKeyName.trim()) return;

    try {
      const result = await createAPIKeyMutation.mutateAsync({
        name: apiKeyName,
        tier: apiKeyTier,
      });
      setNewAPIKey(result.key || null);
      setAPIKeyName('');
      setShowCreateForm(false);
      refetchAPIKeys();
    } catch (err) {
      // Error handled by mutation
    }
  };

  const handleRevokeClick = (keyId: string) => setConfirmRevokeId(keyId);
  const handleRevokeConfirm = async () => {
    const keyId = confirmRevokeId;
    if (!keyId) return;
    setConfirmRevokeId(null);
    try {
      await revokeAPIKeyMutation.mutateAsync(keyId);
      toast.success('API key revoked.');
      refetchAPIKeys();
    } catch (err) {
      toast.error(normalizeError(err).error.message || 'Failed to revoke API key');
    }
  };

  return (
    <div className="baas-page">
      <div className="baas-header">
        <h1>BaaS Platform</h1>
        <p className="subtitle">Manage API keys and monitor usage</p>
      </div>

      <div className="baas-tabs">
        <button
          className={`baas-tab ${activeTab === 'api-keys' ? 'active' : ''}`}
          onClick={() => setActiveTab('api-keys')}
          type="button"
        >
          API Keys
        </button>
        <button
          className={`baas-tab ${activeTab === 'usage' ? 'active' : ''}`}
          onClick={() => setActiveTab('usage')}
          type="button"
        >
          Usage Dashboard
        </button>
      </div>

      <div className="baas-content">
        {activeTab === 'api-keys' && (
          <div className="api-keys-section">
            <div className="section-header">
              <h2>API Keys</h2>
              {!showCreateForm && (
                <button
                  className="btn-primary"
                  onClick={() => setShowCreateForm(true)}
                  type="button"
                >
                  Create API Key
                </button>
              )}
            </div>

            {newAPIKey && (
              <div className="new-api-key-alert">
                <h3>API Key Created!</h3>
                <p><strong>Important:</strong> Save this key now. You won't be able to see it again.</p>
                <div className="api-key-value">{newAPIKey}</div>
                <button
                  className="btn-secondary"
                  onClick={() => {
                    setNewAPIKey(null);
                    navigator.clipboard.writeText(newAPIKey);
                  }}
                  type="button"
                >
                  Copy to Clipboard
                </button>
              </div>
            )}

            {showCreateForm && (
              <div className="create-api-key-form">
                <h3>Create New API Key</h3>
                <div className="form-group">
                  <label htmlFor="api-key-name">Name *</label>
                  <input
                    id="api-key-name"
                    type="text"
                    value={apiKeyName}
                    onChange={(e) => setAPIKeyName(e.target.value)}
                    placeholder="e.g., Production API Key"
                    required
                  />
                </div>
                <div className="form-group">
                  <label htmlFor="api-key-tier">Tier</label>
                  <select
                    id="api-key-tier"
                    value={apiKeyTier}
                    onChange={(e) => setAPIKeyTier(e.target.value as APITier)}
                  >
                    <option value={APITier.FREE}>FREE (1,000 req/hour)</option>
                    <option value={APITier.PRO}>PRO (10,000 req/hour)</option>
                    <option value={APITier.ENTERPRISE}>ENTERPRISE (Unlimited)</option>
                  </select>
                </div>
                <div className="form-actions">
                  <button
                    className="btn-primary"
                    onClick={handleCreateAPIKey}
                    disabled={!apiKeyName.trim() || createAPIKeyMutation.isPending}
                    type="button"
                  >
                    {createAPIKeyMutation.isPending ? 'Creating...' : 'Create'}
                  </button>
                  <button
                    className="btn-secondary"
                    onClick={() => {
                      setShowCreateForm(false);
                      setAPIKeyName('');
                    }}
                    type="button"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            )}

            {apiKeysLoading && <LoadingSpinner message="Loading API keys..." />}
            {apiKeysError && <ErrorDisplay error={apiKeysError} title="Failed to load API keys" />}
            {apiKeysData && apiKeysData.results.length === 0 && (
              <EmptyState
                title="No API keys"
                message="Create your first API key to start using the BaaS platform."
              />
            )}
            {apiKeysData && apiKeysData.results.length > 0 && (
              <div className="api-keys-list">
                {apiKeysData.results.map(key => (
                  <div key={key.id} className="api-key-card">
                    <div className="api-key-info">
                      <h3>{key.name}</h3>
                      <div className="api-key-meta">
                        <span className={`tier-badge tier-${key.tier.toLowerCase()}`}>{key.tier}</span>
                        {key.expires_at && (
                          <span className="expires-at">
                            Expires: {new Date(key.expires_at).toLocaleDateString()}
                          </span>
                        )}
                        {key.revoked_at && (
                          <span className="revoked-badge">Revoked</span>
                        )}
                      </div>
                    </div>
                    <div className="api-key-actions">
                      {!key.revoked_at && (
                        <button
                          className="btn-danger"
                          onClick={() => handleRevokeClick(key.id)}
                          disabled={revokeAPIKeyMutation.isPending}
                          type="button"
                        >
                          Revoke
                        </button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {activeTab === 'usage' && (
          <div className="usage-section">
            <h2>Usage Dashboard</h2>

            {usageLoading && <LoadingSpinner message="Loading usage statistics..." />}
            {usageError && <ErrorDisplay error={usageError} title="Failed to load usage statistics" />}
            {usageStats && (
              <div className="usage-stats">
                <div className="stat-card">
                  <h3>Total Requests</h3>
                  <p className="stat-value">{usageStats.total_requests.toLocaleString()}</p>
                </div>
                <div className="stat-card">
                  <h3>Success Rate</h3>
                  <p className="stat-value">{(usageStats.success_rate * 100).toFixed(1)}%</p>
                </div>
                <div className="stat-card">
                  <h3>Average Response Time</h3>
                  <p className="stat-value">{usageStats.average_response_time_ms}ms</p>
                </div>
                <div className="stat-card">
                  <h3>Failed Requests</h3>
                  <p className="stat-value">{usageStats.failed_requests.toLocaleString()}</p>
                </div>
              </div>
            )}

            {endpointLoading && <LoadingSpinner message="Loading endpoint usage..." />}
            {usageByEndpoint && usageByEndpoint.length > 0 && (
              <div className="usage-by-endpoint">
                <h3>Usage by Endpoint</h3>
                <table className="usage-table">
                  <thead>
                    <tr>
                      <th>Endpoint</th>
                      <th>Requests</th>
                      <th>Success</th>
                      <th>Failed</th>
                      <th>Avg Response Time</th>
                    </tr>
                  </thead>
                  <tbody>
                    {usageByEndpoint.map((endpoint, idx) => (
                      <tr key={idx}>
                        <td>{endpoint.endpoint}</td>
                        <td>{endpoint.requests.toLocaleString()}</td>
                        <td>{endpoint.successful.toLocaleString()}</td>
                        <td>{endpoint.failed.toLocaleString()}</td>
                        <td>{endpoint.average_response_time_ms}ms</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}
      </div>

      <ConfirmDialog
        isOpen={confirmRevokeId !== null}
        onClose={() => setConfirmRevokeId(null)}
        onConfirm={handleRevokeConfirm}
        title="Revoke API key"
        message="Are you sure you want to revoke this API key?"
        confirmLabel="Revoke"
        variant="danger"
      />
    </div>
  );
}

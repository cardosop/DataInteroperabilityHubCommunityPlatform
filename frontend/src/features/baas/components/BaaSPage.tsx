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
import { APITier, type APIKeyCreateRequest } from '../../../shared/types/baas';
import './BaaSPage.css';
import { Button } from '../../../shared/components/Button';
import { CustomerListPage } from './CustomerListPage';
import { BillingReportListPage } from './BillingReportListPage';

type TabType = 'api-keys' | 'usage' | 'customers' | 'billing-reports' | 'ml-developer';

export function BaaSPage() {
  const [activeTab, setActiveTab] = useState<TabType>('api-keys');
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [apiKeyName, setAPIKeyName] = useState('');
  const [apiKeyTier, setAPIKeyTier] = useState<APITier>(APITier.FREE);
  const [newAPIKey, setNewAPIKey] = useState<string | null>(null);
  const [customerId, setCustomerId] = useState('');
  const [customerName, setCustomerName] = useState('');
  const [customerEmail, setCustomerEmail] = useState('');
  const [pricingEnabled, setPricingEnabled] = useState(false);
  const [monthlyFlatFee, setMonthlyFlatFee] = useState('');
  const [includedRequests, setIncludedRequests] = useState('');
  const [overageRate, setOverageRate] = useState('');

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
      const payload: APIKeyCreateRequest = {
        name: apiKeyName,
        tier: apiKeyTier,
      };
      if (customerId) payload.customer_id = customerId;
      if (customerName) payload.customer_name = customerName;
      if (customerEmail) payload.customer_email = customerEmail;
      if (pricingEnabled) {
        payload.pricing = {
          monthly_flat_fee: monthlyFlatFee || '0',
          included_requests: parseInt(includedRequests || '0', 10),
          overage_rate: overageRate || '0',
        };
      }
      const result = await createAPIKeyMutation.mutateAsync(payload);
      setNewAPIKey(result.key || null);
      setAPIKeyName('');
      setCustomerId('');
      setCustomerName('');
      setCustomerEmail('');
      setPricingEnabled(false);
      setMonthlyFlatFee('');
      setIncludedRequests('');
      setOverageRate('');
      setShowCreateForm(false);
      refetchAPIKeys();
    } catch {
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
        <button
          className={`baas-tab ${activeTab === 'customers' ? 'active' : ''}`}
          onClick={() => setActiveTab('customers')}
          type="button"
        >
          Customers
        </button>
        <button
          className={`baas-tab ${activeTab === 'billing-reports' ? 'active' : ''}`}
          onClick={() => setActiveTab('billing-reports')}
          type="button"
        >
          Billing Reports
        </button>
        <button
          className={`baas-tab ${activeTab === 'ml-developer' ? 'active' : ''}`}
          onClick={() => setActiveTab('ml-developer')}
          type="button"
        >
          ML Developer
        </button>
      </div>

      <div className="baas-content">
        {activeTab === 'api-keys' && (
          <div className="api-keys-section">
            <div className="section-header">
              <h2>API Keys</h2>
              {!showCreateForm && (
                <Button
 variant="primary"
 onClick={() => setShowCreateForm(true)}>
                  Create API Key
                </Button>
              )}
            </div>

            {newAPIKey && (
              <div className="new-api-key-alert">
                <h3>API Key Created!</h3>
                <p><strong>Important:</strong> Save this key now. You won't be able to see it again.</p>
                <div className="api-key-value">{newAPIKey}</div>
                <Button
 variant="secondary"
 onClick={() => {
 setNewAPIKey(null);
 navigator.clipboard.writeText(newAPIKey);
 }}>
                  Copy to Clipboard
                </Button>
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
                {/* Customer fields (116C.4) */}
                <div className="form-group">
                  <label htmlFor="customer-id">Customer ID</label>
                  <input id="customer-id" type="text" value={customerId} onChange={(e) => setCustomerId(e.target.value)} placeholder="e.g., cust_001" />
                </div>
                <div className="form-group">
                  <label htmlFor="customer-name">Customer Name</label>
                  <input id="customer-name" type="text" value={customerName} onChange={(e) => setCustomerName(e.target.value)} placeholder="e.g., Acme Corp" />
                </div>
                <div className="form-group">
                  <label htmlFor="customer-email">Customer Email</label>
                  <input id="customer-email" type="email" value={customerEmail} onChange={(e) => setCustomerEmail(e.target.value)} placeholder="billing@example.com" />
                </div>

                {/* Pricing config (116C.4) */}
                <div className="form-group">
                  <label>
                    <input type="checkbox" checked={pricingEnabled} onChange={(e) => setPricingEnabled(e.target.checked)} />
                    {' '}Configure custom pricing
                  </label>
                </div>
                {pricingEnabled && (
                  <div className="pricing-config-panel">
                    <div className="form-group">
                      <label htmlFor="monthly-fee">Monthly Flat Fee (USD)</label>
                      <input id="monthly-fee" type="number" step="0.01" min="0" value={monthlyFlatFee} onChange={(e) => setMonthlyFlatFee(e.target.value)} placeholder="50.00" />
                    </div>
                    <div className="form-group">
                      <label htmlFor="included-requests">Included Requests</label>
                      <input id="included-requests" type="number" min="0" value={includedRequests} onChange={(e) => setIncludedRequests(e.target.value)} placeholder="1000" />
                    </div>
                    <div className="form-group">
                      <label htmlFor="overage-rate">Overage Rate (per request, USD)</label>
                      <input id="overage-rate" type="number" step="0.000001" min="0" value={overageRate} onChange={(e) => setOverageRate(e.target.value)} placeholder="0.002" />
                    </div>
                  </div>
                )}

                <div className="form-actions">
                  <Button
 variant="primary"
 onClick={handleCreateAPIKey}
 disabled={!apiKeyName.trim() || createAPIKeyMutation.isPending}>
                    {createAPIKeyMutation.isPending ? 'Creating...' : 'Create'}
                  </Button>
                  <Button
 variant="secondary"
 onClick={() => {
 setShowCreateForm(false);
 setAPIKeyName('');
 setCustomerId('');
 setCustomerName('');
 setCustomerEmail('');
 setPricingEnabled(false);
 setMonthlyFlatFee('');
 setIncludedRequests('');
 setOverageRate('');
 }}>
                    Cancel
                  </Button>
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
                        <Button
 variant="danger"
 onClick={() => handleRevokeClick(key.id)}
 loading={revokeAPIKeyMutation.isPending}>
                          Revoke
                        </Button>
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

        {activeTab === 'customers' && <CustomerListPage />}

        {activeTab === 'billing-reports' && <BillingReportListPage />}

        {activeTab === 'ml-developer' && (
          <div className="ml-developer-section">
            <h2>ML Developer Portal</h2>
            <p className="ml-developer-intro">
              Build intelligent applications using the ML inference API.
              Deploy models, run predictions, and monitor performance.
            </p>

            <div className="ml-dev-cards">
              <div className="ml-dev-card">
                <h3>Quick Start</h3>
                <p>Authenticate with your API key and call the inference endpoint:</p>
                <pre className="ml-dev-code">{`curl -X POST /api/v1/ml/inference/deployments/predict/ \\
  -H "Authorization: Bearer <API_KEY>" \\
  -H "Content-Type: application/json" \\
  -d '{"deployment_id": "<ID>", "input": {"features": [1.0, 2.0]}}'`}</pre>
              </div>

              <div className="ml-dev-card">
                <h3>Available Endpoints</h3>
                <table className="ml-dev-endpoint-table">
                  <thead>
                    <tr>
                      <th>Method</th>
                      <th>Endpoint</th>
                      <th>Scope</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr>
                      <td><span className="ml-dev-method ml-dev-get">GET</span></td>
                      <td>/api/v1/ml/models/</td>
                      <td><code>ml:read</code></td>
                    </tr>
                    <tr>
                      <td><span className="ml-dev-method ml-dev-get">GET</span></td>
                      <td>/api/v1/ml/models/:id/</td>
                      <td><code>ml:read</code></td>
                    </tr>
                    <tr>
                      <td><span className="ml-dev-method ml-dev-post">POST</span></td>
                      <td>/api/v1/ml/models/</td>
                      <td><code>ml:write</code></td>
                    </tr>
                    <tr>
                      <td><span className="ml-dev-method ml-dev-get">GET</span></td>
                      <td>/api/v1/ml/inference/deployments/</td>
                      <td><code>ml:read</code></td>
                    </tr>
                    <tr>
                      <td><span className="ml-dev-method ml-dev-post">POST</span></td>
                      <td>/api/v1/ml/inference/deployments/</td>
                      <td><code>ml:write</code></td>
                    </tr>
                    <tr>
                      <td><span className="ml-dev-method ml-dev-post">POST</span></td>
                      <td>/api/v1/ml/inference/deployments/predict/</td>
                      <td><code>ml:write</code></td>
                    </tr>
                    <tr>
                      <td><span className="ml-dev-method ml-dev-get">GET</span></td>
                      <td>/api/v1/ml/inference/deployments/:id/metrics/</td>
                      <td><code>ml:read</code></td>
                    </tr>
                    <tr>
                      <td><span className="ml-dev-method ml-dev-post">POST</span></td>
                      <td>/api/v1/ml/training/jobs/</td>
                      <td><code>ml:write</code></td>
                    </tr>
                    <tr>
                      <td><span className="ml-dev-method ml-dev-get">GET</span></td>
                      <td>/api/v1/ml/training/jobs/</td>
                      <td><code>ml:read</code></td>
                    </tr>
                  </tbody>
                </table>
              </div>

              <div className="ml-dev-card">
                <h3>Rate Limits</h3>
                <p>
                  ML inference requests are metered per tenant. Your plan includes a monthly
                  quota for inference calls and training jobs. Check your{' '}
                  <a href="/settings/subscription">subscription page</a> for current limits.
                </p>
                <dl className="ml-dev-limits-dl">
                  <dt>API Key Scopes</dt>
                  <dd>Include <code>ml:read</code> and/or <code>ml:write</code> when creating API keys</dd>
                  <dt>Cross-tenant Access</dt>
                  <dd>Requires an active marketplace entitlement for the model's asset</dd>
                </dl>
              </div>
            </div>
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

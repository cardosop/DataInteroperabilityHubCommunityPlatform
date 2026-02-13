/**
 * Marketplace Connection Detail Page
 * Shows connection details; edit/delete/test when backend supports
 */

import { useParams, useNavigate } from 'react-router-dom';
import {
  useMarketplaceConnection,
  useDeleteMarketplaceConnection,
  useTestMarketplaceConnection,
} from '../hooks/useMarketplaceConnections';
import { LoadingSpinner } from '../../../shared/components/LoadingSpinner';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import './MarketplaceConnectionDetailPage.css';

export function MarketplaceConnectionDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { data: connection, isLoading, error, refetch } = useMarketplaceConnection(id ?? null);
  const deleteMutation = useDeleteMarketplaceConnection();
  const testMutation = useTestMarketplaceConnection();

  const handleDelete = async () => {
    if (!id || !confirm('Are you sure you want to delete this connection? This action cannot be undone.'))
      return;
    try {
      await deleteMutation.mutateAsync(id);
      navigate('/integrations/connections');
    } catch {
      // Error handled by mutation
    }
  };

  const handleTest = async () => {
    if (!id) return;
    try {
      const result = await testMutation.mutateAsync(id);
      if (result.success) {
        alert(`Connection test passed: ${result.message}`);
      } else {
        alert(`Connection test failed: ${result.message}${result.error ? ` (${result.error})` : ''}`);
      }
    } catch (err) {
      alert('Connection test failed. Check console for details.');
    }
  };

  if (isLoading || !connection) {
    return <LoadingSpinner message="Loading connection..." />;
  }

  if (error) {
    return (
      <ErrorDisplay
        error={error}
        title="Failed to load connection"
        onRetry={() => refetch()}
      />
    );
  }

  return (
    <div className="marketplace-connection-detail-page">
      <div className="marketplace-connection-detail-header">
        <button
          onClick={() => navigate('/integrations/connections')}
          className="btn-back"
          type="button"
        >
          ← Back to Connections
        </button>
        <div className="header-actions">
          <button
            onClick={handleTest}
            className="btn-secondary"
            type="button"
            disabled={testMutation.isPending}
            title="Test connection"
          >
            {testMutation.isPending ? 'Testing...' : 'Test Connection'}
          </button>
          <button
            onClick={() => navigate(`/integrations/connections/${id}/edit`)}
            className="btn-secondary"
            type="button"
            title="Edit connection"
          >
            Edit
          </button>
          <button
            onClick={handleDelete}
            className="btn-danger"
            type="button"
            disabled={deleteMutation.isPending}
            title="Delete connection"
          >
            {deleteMutation.isPending ? 'Deleting...' : 'Delete'}
          </button>
        </div>
      </div>

      <div className="marketplace-connection-detail-content">
        <div className="detail-section">
          <h1>{connection.name}</h1>
          <div className="detail-meta">
            <span className={`connection-status-badge ${connection.is_active ? 'active' : 'inactive'}`}>
              {connection.is_active ? 'Active' : 'Inactive'}
            </span>
            <span className="connection-type-badge">{connection.marketplace_type}</span>
          </div>
        </div>

        <div className="detail-section">
          <h2>Details</h2>
          <dl className="detail-list">
            <dt>ID</dt>
            <dd><code>{connection.id}</code></dd>
            <dt>Tenant</dt>
            <dd><code>{connection.tenant}</code></dd>
            <dt>Created</dt>
            <dd>{new Date(connection.created_at).toLocaleString()}</dd>
            <dt>Updated</dt>
            <dd>{new Date(connection.updated_at).toLocaleString()}</dd>
            {connection.last_sync_at && (
              <>
                <dt>Last sync</dt>
                <dd>{new Date(connection.last_sync_at).toLocaleString()}</dd>
              </>
            )}
            {connection.status != null && (
              <>
                <dt>Status</dt>
                <dd>{connection.status}</dd>
              </>
            )}
            {connection.error_message && (
              <>
                <dt>Error</dt>
                <dd className="error-text">{connection.error_message}</dd>
              </>
            )}
          </dl>
        </div>

        <div className="detail-section">
          <h2>Configuration</h2>
          <pre className="config-json">
            {JSON.stringify(connection.config_json, null, 2)}
          </pre>
        </div>
      </div>
    </div>
  );
}

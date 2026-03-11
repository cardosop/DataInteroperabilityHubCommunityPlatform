/**
 * Marketplace Connection Detail Page
 * Shows connection details; edit/delete/test when backend supports
 */

import { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  useMarketplaceConnection,
  useDeleteMarketplaceConnection,
  useTestMarketplaceConnection,
} from '../hooks/useMarketplaceConnections';
import { ConfirmDialog } from '../../../shared/components/ConfirmDialog';
import { LoadingSpinner } from '../../../shared/components/LoadingSpinner';
import { useToast } from '../../../shared/components/Toast';
import { normalizeError } from '../../../shared/utils/errorUtils';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { UuidWithCopy } from '../../../shared/components/UuidWithCopy';
import { Breadcrumbs } from '../../../shared/components/Breadcrumbs';
import './MarketplaceConnectionDetailPage.css';

export function MarketplaceConnectionDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { data: connection, isLoading, error, refetch } = useMarketplaceConnection(id ?? null);
  const deleteMutation = useDeleteMarketplaceConnection();
  const testMutation = useTestMarketplaceConnection();
  const toast = useToast();
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);

  const handleDeleteClick = () => setShowDeleteConfirm(true);
  const handleDeleteConfirm = async () => {
    if (!id) return;
    setShowDeleteConfirm(false);
    try {
      await deleteMutation.mutateAsync(id);
      toast.success('Connection deleted.');
      navigate('/integrations/connections');
    } catch (err) {
      toast.error(normalizeError(err).error.message || 'Failed to delete connection');
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

  if (error) {
    return (
      <ErrorDisplay
        error={error}
        title="Failed to load connection"
        onRetry={() => refetch()}
      />
    );
  }

  if (isLoading || !connection) {
    return <LoadingSpinner message="Loading connection..." />;
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
            onClick={handleDeleteClick}
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
        <Breadcrumbs
          items={[
            { label: 'Home', href: '/' },
            { label: 'Connections', href: '/integrations/connections' },
            { label: connection.name || 'Connection' },
          ]}
        />
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
            <dd>
              <UuidWithCopy value={connection.id} label="Connection ID" />
            </dd>
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

      <ConfirmDialog
        isOpen={showDeleteConfirm}
        onClose={() => setShowDeleteConfirm(false)}
        onConfirm={handleDeleteConfirm}
        title="Delete connection"
        message="Are you sure you want to delete this connection? This action cannot be undone."
        confirmLabel="Delete"
        variant="danger"
      />
    </div>
  );
}

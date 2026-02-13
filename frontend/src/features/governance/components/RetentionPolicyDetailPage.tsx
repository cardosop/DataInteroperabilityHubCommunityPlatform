/**
 * Retention Policy Detail Page
 * Shows retention policy details
 */

import { useNavigate, useParams } from 'react-router-dom';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { LoadingSpinner } from '../../../shared/components/LoadingSpinner';
import { useDeleteRetentionPolicy, useRetentionPolicy } from '../hooks/useRetention';
import './RetentionPolicyDetailPage.css';

export function RetentionPolicyDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { data: policy, isLoading, error, refetch } = useRetentionPolicy(id || null);
  const deleteMutation = useDeleteRetentionPolicy();

  const handleDelete = async () => {
    if (
      !id ||
      !confirm(
        'Are you sure you want to delete this retention policy? This action cannot be undone.'
      )
    )
      return;
    try {
      await deleteMutation.mutateAsync(id);
      navigate('/governance/retention');
    } catch {
      // Error handled by mutation
    }
  };

  const handleEdit = () => {
    if (id) navigate(`/governance/retention/${id}/edit`);
  };

  if (isLoading) {
    return <LoadingSpinner message="Loading retention policy..." />;
  }

  if (error || !policy) {
    return (
      <ErrorDisplay
        error={error || new Error('Retention policy not found')}
        title="Failed to load retention policy"
        onRetry={() => refetch()}
      />
    );
  }

  const resourceLabel =
    [policy.asset && 'Asset', policy.dataset && 'Dataset', policy.file && 'File']
      .filter(Boolean)
      .join(', ') || '—';

  return (
    <div className="governance-retention-policy-detail-page">
      <div className="governance-detail-header">
        <button
          type="button"
          className="btn-back"
          onClick={() => navigate('/governance/retention')}
        >
          ← Back to Retention Policies
        </button>
        <div className="governance-detail-actions">
          <button type="button" className="btn-secondary" onClick={handleEdit}>
            Edit
          </button>
          <button
            type="button"
            className="btn-danger"
            onClick={handleDelete}
            disabled={deleteMutation.isPending}
          >
            {deleteMutation.isPending ? 'Deleting...' : 'Delete'}
          </button>
        </div>
      </div>

      <div className="governance-detail-content">
        <h1>{policy.name}</h1>

        <div className="governance-detail-section">
          <div className="governance-detail-metadata">
            <div className="metadata-item">
              <label>Status</label>
              <span
                className={`governance-status-badge ${policy.enabled ? 'enabled' : 'disabled'}`}
              >
                {policy.enabled ? 'Enabled' : 'Disabled'}
              </span>
            </div>
            {policy.description && (
              <div className="metadata-item">
                <label>Description</label>
                <p style={{ margin: 0 }}>{policy.description}</p>
              </div>
            )}
            <div className="metadata-item">
              <label>Policy Type</label>
              <span>{policy.policy_type}</span>
            </div>
            {policy.policy_type === 'TIME_BASED' && policy.retention_period_days && (
              <div className="metadata-item">
                <label>Retention Period</label>
                <span>{policy.retention_period_days} days</span>
              </div>
            )}
            {policy.policy_type === 'EVENT_BASED' && policy.event_trigger && (
              <div className="metadata-item">
                <label>Event Trigger</label>
                <span>{policy.event_trigger}</span>
              </div>
            )}
            <div className="metadata-item">
              <label>Action</label>
              <span>{policy.action}</span>
            </div>
            <div className="metadata-item">
              <label>Grace Period</label>
              <span>{policy.grace_period_days} days</span>
            </div>
            <div className="metadata-item">
              <label>Resource</label>
              <span>{resourceLabel}</span>
              {policy.asset && <a href={`/assets/${policy.asset}`}>View asset</a>}
              {policy.dataset && <a href={`/datasets/${policy.dataset}`}>View dataset</a>}
              {policy.file && <a href={`/files/${policy.file}`}>View file</a>}
            </div>
            {policy.legal_hold && (
              <>
                <div className="metadata-item">
                  <label>Legal Hold</label>
                  <span>Yes</span>
                </div>
                {policy.legal_hold_reason && (
                  <div className="metadata-item">
                    <label>Legal Hold Reason</label>
                    <p style={{ margin: 0 }}>{policy.legal_hold_reason}</p>
                  </div>
                )}
                {policy.legal_hold_expires_at && (
                  <div className="metadata-item">
                    <label>Legal Hold Expires</label>
                    <span>{new Date(policy.legal_hold_expires_at).toLocaleString()}</span>
                  </div>
                )}
              </>
            )}
            {policy.last_enforced_at && (
              <div className="metadata-item">
                <label>Last Enforced</label>
                <span>{new Date(policy.last_enforced_at).toLocaleString()}</span>
              </div>
            )}
            <div className="metadata-item">
              <label>Created</label>
              <span>{new Date(policy.created_at).toLocaleString()}</span>
            </div>
            <div className="metadata-item">
              <label>Updated</label>
              <span>{new Date(policy.updated_at).toLocaleString()}</span>
            </div>
          </div>
        </div>

        {deleteMutation.error && (
          <div className="error-display" role="alert">
            {deleteMutation.error instanceof Error
              ? deleteMutation.error.message
              : 'Failed to delete retention policy'}
          </div>
        )}
      </div>
    </div>
  );
}

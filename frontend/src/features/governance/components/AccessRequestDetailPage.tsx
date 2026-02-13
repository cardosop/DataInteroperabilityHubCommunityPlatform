/**
 * Access Request Detail Page
 * Shows access request details; Approve/Reject for TENANT_ADMIN/PLATFORM_ADMIN
 */

import { useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { LoadingSpinner } from '../../../shared/components/LoadingSpinner';
import { AccessRequestStatus } from '../../../shared/types/governance';
import { useAuthStore } from '../../auth/store/authStore';
import {
  useAccessRequest,
  useApproveAccessRequest,
  useRejectAccessRequest,
} from '../hooks/useGovernance';
import './AccessRequestDetailPage.css';

function canApproveOrReject(roles: string[] | undefined): boolean {
  if (!roles || !Array.isArray(roles)) return false;
  return roles.includes('TENANT_ADMIN') || roles.includes('PLATFORM_ADMIN');
}

export function AccessRequestDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { user } = useAuthStore();
  const { data: accessRequest, isLoading, error, refetch } = useAccessRequest(id || null);
  const approveMutation = useApproveAccessRequest();
  const rejectMutation = useRejectAccessRequest();
  const [rejectModalOpen, setRejectModalOpen] = useState(false);
  const [rejectReason, setRejectReason] = useState('');

  const isAdmin = canApproveOrReject(user?.roles);
  const isPending = accessRequest?.status === AccessRequestStatus.PENDING;

  const handleApprove = async () => {
    if (!id) return;
    try {
      await approveMutation.mutateAsync({ id });
      refetch();
    } catch {
      // Error shown by mutation
    }
  };

  const handleRejectSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!id || !rejectReason.trim()) return;
    try {
      await rejectMutation.mutateAsync({ id, reason: rejectReason.trim() });
      setRejectModalOpen(false);
      setRejectReason('');
      refetch();
    } catch {
      // Error shown by mutation
    }
  };

  if (isLoading) {
    return <LoadingSpinner message="Loading access request..." />;
  }

  if (error || !accessRequest) {
    return (
      <ErrorDisplay
        error={error || new Error('Access request not found')}
        title="Failed to load access request"
        onRetry={() => refetch()}
      />
    );
  }

  const resourceLabel =
    [
      accessRequest.asset && 'Asset',
      accessRequest.dataset && 'Dataset',
      accessRequest.file && 'File',
    ]
      .filter(Boolean)
      .join(', ') || '—';

  return (
    <div className="governance-access-request-detail-page">
      <div className="governance-detail-header">
        <button type="button" className="btn-back" onClick={() => navigate('/governance')}>
          ← Back to Access Requests
        </button>
      </div>

      <div className="governance-detail-content">
        <h1>Access Request</h1>

        <div className="governance-detail-section">
          <span className={`governance-status-badge ${accessRequest.status}`}>
            {accessRequest.status}
          </span>
          <div className="governance-detail-metadata" style={{ marginTop: '1rem' }}>
            <div className="metadata-item">
              <label>Reason</label>
              <p style={{ margin: 0 }}>{accessRequest.reason}</p>
            </div>
            <div className="metadata-item">
              <label>Requested access type</label>
              <span>{accessRequest.requested_access_type}</span>
            </div>
            <div className="metadata-item">
              <label>Resource</label>
              <span>{resourceLabel}</span>
              {accessRequest.asset && <a href={`/assets/${accessRequest.asset}`}>View asset</a>}
              {accessRequest.dataset && (
                <a href={`/datasets/${accessRequest.dataset}`}>View dataset</a>
              )}
            </div>
            <div className="metadata-item">
              <label>Created</label>
              <span>{new Date(accessRequest.created_at).toLocaleString()}</span>
            </div>
            {accessRequest.approved_at && (
              <div className="metadata-item">
                <label>Approved at</label>
                <span>{new Date(accessRequest.approved_at).toLocaleString()}</span>
              </div>
            )}
            {accessRequest.rejected_at && accessRequest.rejection_reason && (
              <>
                <div className="metadata-item">
                  <label>Rejected at</label>
                  <span>{new Date(accessRequest.rejected_at).toLocaleString()}</span>
                </div>
                <div className="metadata-item">
                  <label>Rejection reason</label>
                  <p style={{ margin: 0 }}>{accessRequest.rejection_reason}</p>
                </div>
              </>
            )}
          </div>

          {isAdmin && isPending && (
            <div className="governance-detail-actions">
              <button
                type="button"
                className="btn-primary btn-approve"
                onClick={handleApprove}
                disabled={approveMutation.isPending}
              >
                {approveMutation.isPending ? 'Approving…' : 'Approve'}
              </button>
              <button
                type="button"
                className="btn-primary btn-reject"
                onClick={() => setRejectModalOpen(true)}
                disabled={rejectMutation.isPending}
              >
                Reject
              </button>
            </div>
          )}
        </div>

        {(approveMutation.error || rejectMutation.error) && (
          <div className="error-display" role="alert">
            {approveMutation.error instanceof Error
              ? approveMutation.error.message
              : rejectMutation.error instanceof Error
                ? rejectMutation.error.message
                : 'An error occurred'}
          </div>
        )}
      </div>

      {rejectModalOpen && (
        <div
          className="governance-reject-modal-overlay"
          role="dialog"
          aria-modal="true"
          aria-labelledby="reject-modal-title"
        >
          <div className="governance-reject-modal">
            <h3 id="reject-modal-title">Reject access request</h3>
            <form onSubmit={handleRejectSubmit}>
              <label htmlFor="reject-reason">Reason (required)</label>
              <textarea
                id="reject-reason"
                value={rejectReason}
                onChange={(e) => setRejectReason(e.target.value)}
                required
                placeholder="Enter rejection reason..."
              />
              <div className="governance-reject-modal-actions">
                <button
                  type="button"
                  className="btn-secondary"
                  onClick={() => setRejectModalOpen(false)}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="btn-primary btn-reject"
                  disabled={!rejectReason.trim() || rejectMutation.isPending}
                >
                  {rejectMutation.isPending ? 'Rejecting…' : 'Reject'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

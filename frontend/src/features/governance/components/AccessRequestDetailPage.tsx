/**
 * Access Request Detail Page
 * Shows access request details; Approve/Reject for TENANT_ADMIN/PLATFORM_ADMIN
 */

import { useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { DetailPageSkeleton } from '../../../shared/components/skeletons/DetailPageSkeleton';
import { AccessRequestStatus } from '../../../shared/types/governance';
import { useAuthStore } from '../../auth/store/authStore';
import {
  useAccessRequest,
  useApproveAccessRequest,
  useRejectAccessRequest,
  useRevokeAccessRequest,
} from '../hooks/useGovernance';
import { UuidWithCopy } from '../../../shared/components/UuidWithCopy';
import { Breadcrumbs } from '../../../shared/components/Breadcrumbs';
import { ActivityTimeline } from '../../../shared/components/ActivityTimeline';
import { InfoHint } from '../../../shared/components/InfoHint';
import { AccessRequestCommentsThread } from './AccessRequestCommentsThread';
import './AccessRequestDetailPage.css';
import { Button } from '../../../shared/components/Button';

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
  const revokeMutation = useRevokeAccessRequest();
  const [rejectModalOpen, setRejectModalOpen] = useState(false);
  const [rejectReason, setRejectReason] = useState('');
  const [activeTab, setActiveTab] = useState<'details' | 'activity' | 'comments'>('details');

  const isAdmin = canApproveOrReject(user?.roles);
  const isPending = accessRequest?.status === AccessRequestStatus.PENDING;
  const isApproved = accessRequest?.status === AccessRequestStatus.APPROVED;

  const handleRevoke = async () => {
    if (!id) return;
    try {
      await revokeMutation.mutateAsync(id);
      refetch();
    } catch {
      // Error shown by mutation
    }
  };

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
    return <DetailPageSkeleton />;
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
        <Button variant="ghost" onClick={() => navigate('/governance')}>
          ← Back to Access Requests
        </Button>
      </div>

      <div className="governance-detail-content">
        <Breadcrumbs
          items={[
            { label: 'Home', href: '/' },
            { label: 'Access Requests', href: '/governance' },
            { label: 'Request' },
          ]}
        />
        <h1>
          Access Request
          <InfoHint
            label="About Access Requests"
            content="An Access Request is a formal, auditable ticket from a data consumer asking to use a specific asset, dataset, or file. When APPROVED by a governance admin, it becomes an entitlement that grants scoped READ/WRITE access for a bounded time window. Every status transition is captured in the audit log."
          />
        </h1>
        {id && (
          <div className="access-request-uuid" data-testid="access-request-uuid">
            <UuidWithCopy value={id} label="Access Request ID" />
          </div>
        )}

        {/* Phase 224.3.4 — Details/Activity tabs. */}
        <div
          className="governance-detail-tabs"
          role="tablist"
          aria-label="Access Request sections"
        >
          <button
            type="button"
            role="tab"
            aria-selected={activeTab === 'details'}
            className={`governance-detail-tab ${activeTab === 'details' ? 'active' : ''}`}
            onClick={() => setActiveTab('details')}
            data-testid="access-request-tab-details"
          >
            Details
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={activeTab === 'activity'}
            className={`governance-detail-tab ${activeTab === 'activity' ? 'active' : ''}`}
            onClick={() => setActiveTab('activity')}
            data-testid="access-request-tab-activity"
          >
            Activity
          </button>
          {/* Phase 272.1 — Comments tab */}
          <button
            type="button"
            role="tab"
            aria-selected={activeTab === 'comments'}
            className={`governance-detail-tab ${activeTab === 'comments' ? 'active' : ''}`}
            onClick={() => setActiveTab('comments')}
            data-testid="access-request-tab-comments"
          >
            Comments
          </button>
        </div>

        {activeTab === 'activity' && id && (
          <div className="governance-detail-section" data-testid="access-request-activity">
            <ActivityTimeline resourceType="ACCESS_REQUEST" resourceId={id} />
          </div>
        )}

        {activeTab === 'comments' && id && (
          <div className="governance-detail-section" data-testid="access-request-comments">
            <AccessRequestCommentsThread accessRequestId={id} />
          </div>
        )}

        <div className="governance-detail-section" hidden={activeTab !== 'details'}>
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

          {accessRequest.order && (
            <div className="metadata-item">
              <label>Marketplace Order</label>
              <a href={`/marketplace/orders/${accessRequest.order}`}>View order</a>
            </div>
          )}

          {isAdmin && isPending && (
            <div className="governance-detail-actions">
              <Button
 variant="primary" className="btn-approve"
 onClick={handleApprove}
 loading={approveMutation.isPending}>
                Approve
              </Button>
              <Button
 variant="primary" className="btn-reject"
 onClick={() => setRejectModalOpen(true)}
 loading={rejectMutation.isPending}>
                Reject
              </Button>
            </div>
          )}

          {isAdmin && isApproved && (
            <div className="governance-detail-actions">
              <Button
 variant="danger"
 onClick={handleRevoke}
 loading={revokeMutation.isPending}>
                Revoke Access
              </Button>
            </div>
          )}
        </div>

        {!!(approveMutation.error || rejectMutation.error || revokeMutation.error) && (
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
                <Button
 variant="secondary"
 onClick={() => setRejectModalOpen(false)}>
                  Cancel
                </Button>
                <Button
 type="submit"
 variant="primary" className="btn-reject"
 disabled={!rejectReason.trim() || rejectMutation.isPending}>
                  {rejectMutation.isPending ? 'Rejecting…' : 'Reject'}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

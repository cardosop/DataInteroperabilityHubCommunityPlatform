/**
 * Order Detail Page
 * View detailed information about an order
 */

import { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  useOrder,
  useApproveOrder,
  useRejectOrder,
  useCancelOrder,
  useRefundOrder,
} from '../hooks/useOrders';
import { useListing } from '../hooks/useListings';
import { useAuthStore } from '../../auth/store/authStore';
import { ConfirmDialog } from '../../../shared/components/ConfirmDialog';
import { Modal } from '../../../shared/components/Modal';
import { LoadingSpinner } from '../../../shared/components/LoadingSpinner';
import { DetailPageSkeleton } from '../../../shared/components/skeletons/DetailPageSkeleton';
import { useToast } from '../../../shared/components/Toast';
import { normalizeError } from '../../../shared/utils/errorUtils';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { OrderStatus } from '../../../shared/types/marketplace';
import { UuidWithCopy } from '../../../shared/components/UuidWithCopy';
import { Breadcrumbs } from '../../../shared/components/Breadcrumbs';
import './OrderDetailPage.css';
import { Button } from '../../../shared/components/Button';

export function OrderDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { data: order, isLoading, error, refetch } = useOrder(id || null);
  const { data: listing } = useListing(order?.listing ?? null);
  const { user, active_tenant_id } = useAuthStore();
  const approveMutation = useApproveOrder();
  const rejectMutation = useRejectOrder();
  const cancelMutation = useCancelOrder();
  const refundMutation = useRefundOrder();
  const toast = useToast();
  const [showCancelConfirm, setShowCancelConfirm] = useState(false);
  const [showRejectDialog, setShowRejectDialog] = useState(false);
  const [rejectReason, setRejectReason] = useState('');
  const [showRefundDialog, setShowRefundDialog] = useState(false);
  const [refundReason, setRefundReason] = useState('');

  const handleApprove = async () => {
    if (!id) return;
    try {
      await approveMutation.mutateAsync(id);
    } catch {
      // Error handled by mutation
    }
  };

  const handleRejectClick = () => setShowRejectDialog(true);
  const handleRejectConfirm = async () => {
    if (!id) return;
    setShowRejectDialog(false);
    try {
      await rejectMutation.mutateAsync({ id, reason: rejectReason || undefined });
    } catch {
      // Error handled by mutation
    }
    setRejectReason('');
  };

  const handleCancelClick = () => setShowCancelConfirm(true);
  const handleCancelConfirm = async () => {
    if (!id) return;
    setShowCancelConfirm(false);
    try {
      await cancelMutation.mutateAsync(id);
      toast.success('Order cancelled.');
    } catch (err) {
      toast.error(normalizeError(err).error.message || 'Failed to cancel order');
    }
  };

  if (isLoading) {
    return <DetailPageSkeleton />;
  }

  if (error) {
    return <ErrorDisplay error={error} title="Failed to load order" onRetry={() => refetch()} />;
  }

  if (!order) {
    return <ErrorDisplay error="Order not found" title="Order not found" />;
  }

  const canApprove = order.status === OrderStatus.REQUESTED;
  const canReject = order.status === OrderStatus.REQUESTED;
  const canCancel = order.status === OrderStatus.REQUESTED || order.status === OrderStatus.APPROVED;

  const effectiveTenantId = active_tenant_id || user?.tenant_id;
  const canRefund =
    order.status === OrderStatus.FULFILLED &&
    listing &&
    (user?.is_platform_admin === true ||
      (!!effectiveTenantId && effectiveTenantId === listing.tenant));

  const handleRefundConfirm = async () => {
    if (!id || !refundReason.trim()) return;
    setShowRefundDialog(false);
    try {
      await refundMutation.mutateAsync({ orderId: id, reason: refundReason.trim() });
      toast.success('Refund submitted.');
      setRefundReason('');
      void refetch();
    } catch (err) {
      toast.error(normalizeError(err).error.message || 'Refund failed');
    }
  };

  return (
    <div className="order-detail-page">
      <div className="order-detail-header">
        <Button onClick={() => navigate('/marketplace/orders')} variant="ghost">
          ← Back to Orders
        </Button>
        <div className="order-detail-title-section">
          <h1>Order {order.id.slice(0, 8)}</h1>
          <span className={`order-status order-status-${order.status.toLowerCase()}`}>
            {order.status}
          </span>
        </div>
        <div className="order-uuid" data-testid="order-uuid">
          <UuidWithCopy value={order.id} label="Order ID" />
        </div>
      </div>

      <div className="order-detail-content">
        <Breadcrumbs
          items={[
            { label: 'Home', href: '/' },
            { label: 'Orders', href: '/marketplace/orders' },
            { label: `Order ${order.id.slice(0, 8)}` },
          ]}
        />
        <div className="order-detail-main">
          <div className="order-section">
            <h2>Listing Information</h2>
            <div className="order-info-grid">
              <div className="order-info-item">
                <span className="order-info-label">Listing:</span>
                <span className="order-info-value">{order.listing_title || order.listing}</span>
              </div>
              {order.asset_id && (
                <div className="order-info-item">
                  <span className="order-info-label">Asset ID:</span>
                  <span className="order-info-value">{order.asset_id}</span>
                </div>
              )}
            </div>
          </div>

          <div className="order-section">
            <h2>Status Information</h2>
            <div className="order-info-grid">
              <div className="order-info-item">
                <span className="order-info-label">Status:</span>
                <span className={`order-status order-status-${order.status.toLowerCase()}`}>
                  {order.status}
                </span>
              </div>
              <div className="order-info-item">
                <span className="order-info-label">Created:</span>
                <span className="order-info-value">
                  {new Date(order.created_at).toLocaleString()}
                </span>
              </div>
              {order.approved_at && (
                <div className="order-info-item">
                  <span className="order-info-label">Approved:</span>
                  <span className="order-info-value">
                    {new Date(order.approved_at).toLocaleString()}
                  </span>
                </div>
              )}
              {order.rejected_at && (
                <div className="order-info-item">
                  <span className="order-info-label">Rejected:</span>
                  <span className="order-info-value">
                    {new Date(order.rejected_at).toLocaleString()}
                  </span>
                </div>
              )}
              {order.fulfilled_at && (
                <div className="order-info-item">
                  <span className="order-info-label">Fulfilled:</span>
                  <span className="order-info-value">
                    {new Date(order.fulfilled_at).toLocaleString()}
                  </span>
                </div>
              )}
            </div>
          </div>

          {order.rejection_reason && (
            <div className="order-section">
              <h2>Rejection Reason</h2>
              <p>{order.rejection_reason}</p>
            </div>
          )}

          {order.access_request_id && (
            <div className="order-section">
              <h2>Governance</h2>
              <p>
                This order has a linked governance access request.{' '}
                <a href={`/governance/access-requests/${order.access_request_id}`}>
                  View access request
                </a>
              </p>
            </div>
          )}
        </div>

        <div className="order-detail-sidebar">
          <div className="order-actions-card">
            {canApprove && (
              <Button
 variant="primary" className="btn-large"
 onClick={handleApprove}
 loading={approveMutation.isPending}>
                {approveMutation.isPending ? (
                  <>
                    <LoadingSpinner size="small" />
                    Approving...
                  </>
                ) : (
                  'Approve Order'
                )}
              </Button>
            )}
            {canReject && (
              <Button
 variant="secondary" className="btn-large"
 onClick={handleRejectClick}
 loading={rejectMutation.isPending}>
                {rejectMutation.isPending ? (
                  <>
                    <LoadingSpinner size="small" />
                    Rejecting...
                  </>
                ) : (
                  'Reject Order'
                )}
              </Button>
            )}
            {canRefund && (
              <Button
                variant="secondary"
                className="btn-large"
                onClick={() => setShowRefundDialog(true)}
                loading={refundMutation.isPending}
              >
                Issue refund
              </Button>
            )}
            {canCancel && (
              <Button
 variant="secondary" className="btn-large"
 onClick={handleCancelClick}
 loading={cancelMutation.isPending}>
                {cancelMutation.isPending ? (
                  <>
                    <LoadingSpinner size="small" />
                    Cancelling...
                  </>
                ) : (
                  'Cancel Order'
                )}
              </Button>
            )}
            {order.fulfilled_at && (
              <div className="order-success-message">
                ✓ Order fulfilled. Entitlement created.
              </div>
            )}
          </div>
        </div>
      </div>

      <Modal
        isOpen={showRefundDialog}
        onClose={() => setShowRefundDialog(false)}
        title="Refund order"
      >
        <p>Provide a reason for the refund (required).</p>
        <textarea
          className="order-reject-textarea"
          value={refundReason}
          onChange={(e) => setRefundReason(e.target.value)}
          rows={3}
          placeholder="Reason"
        />
        <div className="order-reject-actions">
          <Button variant="ghost" onClick={() => setShowRefundDialog(false)}>
            Cancel
          </Button>
          <Button
            variant="primary"
            onClick={() => void handleRefundConfirm()}
            disabled={!refundReason.trim()}
          >
            Submit refund
          </Button>
        </div>
      </Modal>

      <ConfirmDialog
        isOpen={showCancelConfirm}
        onClose={() => setShowCancelConfirm(false)}
        onConfirm={handleCancelConfirm}
        title="Cancel order"
        message="Are you sure you want to cancel this order?"
        confirmLabel="Cancel Order"
        variant="warning"
      />

      <Modal
        isOpen={showRejectDialog}
        onClose={() => { setShowRejectDialog(false); setRejectReason(''); }}
        title="Reject Order"
        aria-describedby="reject-dialog-desc"
      >
        <div className="confirm-dialog-body confirm-dialog-warning">
          <p id="reject-dialog-desc" className="confirm-dialog-message">
            Are you sure you want to reject this order?
          </p>
          <label htmlFor="reject-reason" style={{ display: 'block', marginBottom: 'var(--spacing-sm, 0.5rem)' }}>
            Reason for rejection (optional):
          </label>
          <textarea
            id="reject-reason"
            value={rejectReason}
            onChange={(e) => setRejectReason(e.target.value)}
            rows={3}
            placeholder="Enter rejection reason..."
            style={{ width: '100%', resize: 'vertical', marginBottom: 'var(--spacing-lg, 1rem)' }}
          />
          <div className="confirm-dialog-actions">
            <Button variant="secondary" onClick={() => { setShowRejectDialog(false); setRejectReason(''); }}>
              Cancel
            </Button>
            <Button variant="danger" onClick={handleRejectConfirm}>
              Reject Order
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}

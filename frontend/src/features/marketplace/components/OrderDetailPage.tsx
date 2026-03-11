/**
 * Order Detail Page
 * View detailed information about an order
 */

import { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useOrder, useApproveOrder, useRejectOrder, useCancelOrder } from '../hooks/useOrders';
import { ConfirmDialog } from '../../../shared/components/ConfirmDialog';
import { LoadingSpinner } from '../../../shared/components/LoadingSpinner';
import { useToast } from '../../../shared/components/Toast';
import { normalizeError } from '../../../shared/utils/errorUtils';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { OrderStatus } from '../../../shared/types/marketplace';
import { UuidWithCopy } from '../../../shared/components/UuidWithCopy';
import { Breadcrumbs } from '../../../shared/components/Breadcrumbs';
import './OrderDetailPage.css';

export function OrderDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { data: order, isLoading, error, refetch } = useOrder(id || null);
  const approveMutation = useApproveOrder();
  const rejectMutation = useRejectOrder();
  const cancelMutation = useCancelOrder();
  const toast = useToast();
  const [showCancelConfirm, setShowCancelConfirm] = useState(false);

  const handleApprove = async () => {
    if (!id) return;
    try {
      await approveMutation.mutateAsync(id);
    } catch (error) {
      // Error handled by mutation
    }
  };

  const handleReject = async () => {
    if (!id) return;
    const reason = window.prompt('Reason for rejection (optional):');
    try {
      await rejectMutation.mutateAsync({ id, reason: reason || undefined });
    } catch (error) {
      // Error handled by mutation
    }
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
    return <LoadingSpinner message="Loading order..." />;
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

  return (
    <div className="order-detail-page">
      <div className="order-detail-header">
        <button onClick={() => navigate('/marketplace/orders')} className="btn-back" type="button">
          ← Back to Orders
        </button>
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
        </div>

        <div className="order-detail-sidebar">
          <div className="order-actions-card">
            {canApprove && (
              <button
                className="btn-primary btn-large"
                onClick={handleApprove}
                disabled={approveMutation.isPending}
                type="button"
              >
                {approveMutation.isPending ? (
                  <>
                    <LoadingSpinner size="small" />
                    Approving...
                  </>
                ) : (
                  'Approve Order'
                )}
              </button>
            )}
            {canReject && (
              <button
                className="btn-secondary btn-large"
                onClick={handleReject}
                disabled={rejectMutation.isPending}
                type="button"
              >
                {rejectMutation.isPending ? (
                  <>
                    <LoadingSpinner size="small" />
                    Rejecting...
                  </>
                ) : (
                  'Reject Order'
                )}
              </button>
            )}
            {canCancel && (
              <button
                className="btn-secondary btn-large"
                onClick={handleCancelClick}
                disabled={cancelMutation.isPending}
                type="button"
              >
                {cancelMutation.isPending ? (
                  <>
                    <LoadingSpinner size="small" />
                    Cancelling...
                  </>
                ) : (
                  'Cancel Order'
                )}
              </button>
            )}
            {order.fulfilled_at && (
              <div className="order-success-message">
                ✓ Order fulfilled. Entitlement created.
              </div>
            )}
          </div>
        </div>
      </div>

      <ConfirmDialog
        isOpen={showCancelConfirm}
        onClose={() => setShowCancelConfirm(false)}
        onConfirm={handleCancelConfirm}
        title="Cancel order"
        message="Are you sure you want to cancel this order?"
        confirmLabel="Cancel Order"
        variant="warning"
      />
    </div>
  );
}

/**
 * Entitlement Detail Page
 * View detailed information about an entitlement
 */

import { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useEntitlement, useRevokeEntitlement } from '../hooks/useEntitlements';
import { ConfirmDialog } from '../../../shared/components/ConfirmDialog';
import { LoadingSpinner } from '../../../shared/components/LoadingSpinner';
import { DetailPageSkeleton } from '../../../shared/components/skeletons/DetailPageSkeleton';
import { useToast } from '../../../shared/components/Toast';
import { normalizeError } from '../../../shared/utils/errorUtils';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { EntitlementStatus } from '../../../shared/types/marketplace';
import { UuidWithCopy } from '../../../shared/components/UuidWithCopy';
import { Breadcrumbs } from '../../../shared/components/Breadcrumbs';
import './EntitlementDetailPage.css';
import { Button } from '../../../shared/components/Button';

export function EntitlementDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { data: entitlement, isLoading, error, refetch } = useEntitlement(id || null);
  const revokeMutation = useRevokeEntitlement();
  const toast = useToast();
  const [showRevokeConfirm, setShowRevokeConfirm] = useState(false);

  const handleRevokeClick = () => setShowRevokeConfirm(true);
  const handleRevokeConfirm = async () => {
    if (!id) return;
    setShowRevokeConfirm(false);
    try {
      await revokeMutation.mutateAsync(id);
      toast.success('Entitlement revoked.');
    } catch (err) {
      toast.error(normalizeError(err).error.message || 'Failed to revoke entitlement');
    }
  };

  if (isLoading) {
    return <DetailPageSkeleton />;
  }

  if (error) {
    return <ErrorDisplay error={error} title="Failed to load entitlement" onRetry={() => refetch()} />;
  }

  if (!entitlement) {
    return <ErrorDisplay error="Entitlement not found" title="Entitlement not found" />;
  }

  const canRevoke = entitlement.status === EntitlementStatus.ACTIVE;

  return (
    <div className="entitlement-detail-page">
      <div className="entitlement-detail-header">
        <Button onClick={() => navigate('/marketplace/entitlements')} variant="ghost">
          ← Back to Entitlements
        </Button>
        <div className="entitlement-detail-title-section">
          <h1>Entitlement {entitlement.id.slice(0, 8)}</h1>
          <span className={`entitlement-status entitlement-status-${entitlement.status.toLowerCase()}`}>
            {entitlement.status}
          </span>
        </div>
        <div className="entitlement-uuid" data-testid="entitlement-uuid">
          <UuidWithCopy value={entitlement.id} label="Entitlement ID" />
        </div>
      </div>

      <div className="entitlement-detail-content">
        <Breadcrumbs
          items={[
            { label: 'Home', href: '/' },
            { label: 'Entitlements', href: '/marketplace/entitlements' },
            { label: `Entitlement ${entitlement.id.slice(0, 8)}` },
          ]}
        />
        <div className="entitlement-detail-main">
          <div className="entitlement-section">
            <h2>Asset Information</h2>
            <div className="entitlement-info-grid">
              <div className="entitlement-info-item">
                <span className="entitlement-info-label">Asset:</span>
                <span className="entitlement-info-value">
                  {entitlement.asset_name || entitlement.asset}
                </span>
              </div>
              <div className="entitlement-info-item">
                <span className="entitlement-info-label">Asset ID:</span>
                <span className="entitlement-info-value">{entitlement.asset}</span>
              </div>
            </div>
          </div>

          <div className="entitlement-section">
            <h2>Listing Information</h2>
            <div className="entitlement-info-grid">
              <div className="entitlement-info-item">
                <span className="entitlement-info-label">Listing:</span>
                <span className="entitlement-info-value">
                  {entitlement.listing_title || entitlement.listing}
                </span>
              </div>
              <div className="entitlement-info-item">
                <span className="entitlement-info-label">Listing ID:</span>
                <span className="entitlement-info-value">{entitlement.listing}</span>
              </div>
            </div>
          </div>

          <div className="entitlement-section">
            <h2>Status Information</h2>
            <div className="entitlement-info-grid">
              <div className="entitlement-info-item">
                <span className="entitlement-info-label">Status:</span>
                <span className={`entitlement-status entitlement-status-${entitlement.status.toLowerCase()}`}>
                  {entitlement.status}
                </span>
              </div>
              <div className="entitlement-info-item">
                <span className="entitlement-info-label">Granted:</span>
                <span className="entitlement-info-value">
                  {new Date(entitlement.granted_at).toLocaleString()}
                </span>
              </div>
              {entitlement.revoked_at && (
                <div className="entitlement-info-item">
                  <span className="entitlement-info-label">Revoked:</span>
                  <span className="entitlement-info-value">
                    {new Date(entitlement.revoked_at).toLocaleString()}
                  </span>
                </div>
              )}
              <div className="entitlement-info-item">
                <span className="entitlement-info-label">Expires:</span>
                <span className="entitlement-info-value">
                  {entitlement.expires_at
                    ? new Date(entitlement.expires_at).toLocaleString()
                    : 'Never'}
                </span>
              </div>
            </div>
          </div>

          {entitlement.order && (
            <div className="entitlement-section">
              <h2>Order Information</h2>
              <div className="entitlement-info-grid">
                <div className="entitlement-info-item">
                  <span className="entitlement-info-label">Order ID:</span>
                  <span className="entitlement-info-value">{entitlement.order}</span>
                </div>
              </div>
            </div>
          )}
        </div>

        <div className="entitlement-detail-sidebar">
          <div className="entitlement-actions-card">
            {canRevoke && (
              <Button
 variant="secondary" className="btn-large"
 onClick={handleRevokeClick}
 loading={revokeMutation.isPending}>
                {revokeMutation.isPending ? (
                  <>
                    <LoadingSpinner size="small" />
                    Revoking...
                  </>
                ) : (
                  'Revoke Entitlement'
                )}
              </Button>
            )}
            {entitlement.status === EntitlementStatus.ACTIVE && (
              <div className="entitlement-success-message">
                ✓ You have active access to this asset.
              </div>
            )}
          </div>
        </div>
      </div>

      <ConfirmDialog
        isOpen={showRevokeConfirm}
        onClose={() => setShowRevokeConfirm(false)}
        onConfirm={handleRevokeConfirm}
        title="Revoke entitlement"
        message="Are you sure you want to revoke this entitlement?"
        confirmLabel="Revoke"
        variant="danger"
      />
    </div>
  );
}

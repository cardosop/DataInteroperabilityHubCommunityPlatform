/**
 * Entitlement Detail Page
 * View detailed information about an entitlement
 */

import { useParams, useNavigate } from 'react-router-dom';
import { useEntitlement, useRevokeEntitlement } from '../hooks/useEntitlements';
import { LoadingSpinner } from '../../../shared/components/LoadingSpinner';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { EntitlementStatus } from '../../../shared/types/marketplace';
import './EntitlementDetailPage.css';

export function EntitlementDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { data: entitlement, isLoading, error, refetch } = useEntitlement(id || null);
  const revokeMutation = useRevokeEntitlement();

  const handleRevoke = async () => {
    if (!id) return;
    if (!window.confirm('Are you sure you want to revoke this entitlement?')) return;
    try {
      await revokeMutation.mutateAsync(id);
    } catch (error) {
      // Error handled by mutation
    }
  };

  if (isLoading) {
    return <LoadingSpinner message="Loading entitlement..." />;
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
        <button onClick={() => navigate('/marketplace/entitlements')} className="btn-back" type="button">
          ← Back to Entitlements
        </button>
        <div className="entitlement-detail-title-section">
          <h1>Entitlement {entitlement.id.slice(0, 8)}</h1>
          <span className={`entitlement-status entitlement-status-${entitlement.status.toLowerCase()}`}>
            {entitlement.status}
          </span>
        </div>
      </div>

      <div className="entitlement-detail-content">
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
              <button
                className="btn-secondary btn-large"
                onClick={handleRevoke}
                disabled={revokeMutation.isPending}
                type="button"
              >
                {revokeMutation.isPending ? (
                  <>
                    <LoadingSpinner size="small" />
                    Revoking...
                  </>
                ) : (
                  'Revoke Entitlement'
                )}
              </button>
            )}
            {entitlement.status === EntitlementStatus.ACTIVE && (
              <div className="entitlement-success-message">
                ✓ You have active access to this asset.
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

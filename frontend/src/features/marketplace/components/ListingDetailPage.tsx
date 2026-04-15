/**
 * Listing Detail Page
 * View detailed information about a marketplace listing
 */

import { useParams, useNavigate } from 'react-router-dom';
import { useListing } from '../hooks/useListings';
import { useCreateOrder } from '../hooks/useOrders';
import { LoadingSpinner } from '../../../shared/components/LoadingSpinner';
import { DetailPageSkeleton } from '../../../shared/components/skeletons/DetailPageSkeleton';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { PricingModel, ListingStatus } from '../../../shared/types/marketplace';
import { UuidWithCopy } from '../../../shared/components/UuidWithCopy';
import { Breadcrumbs } from '../../../shared/components/Breadcrumbs';
import { useAuthStore } from '../../auth/store/authStore';
import './ListingDetailPage.css';
import { Button } from '../../../shared/components/Button';

export function ListingDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { data: listing, isLoading, error, refetch } = useListing(id || null);
  const createOrderMutation = useCreateOrder({
    onDuplicateActiveOrder: (orderId) => navigate(`/marketplace/orders/${orderId}`),
  });
  const userTenantId = useAuthStore((state) => state.user?.tenant_id ?? null);
  const activeTenantId = useAuthStore((state) => state.active_tenant_id);

  const handlePurchase = async () => {
    if (!id) return;
    try {
      // For FREE listings, use regular order creation (no payment required)
      // The backend will auto-approve FREE_AUTO_APPROVE listings
      const response = await createOrderMutation.mutateAsync({ listing_id: id });
      // Response may be {order: {...}, entitlement: {...}} for auto-approved orders
      // or just Order for regular orders
      const order = (response as Record<string, unknown & { id?: string }>).order || response;
      const orderId = (order as { id?: string }).id;
      if (order && orderId) {
        navigate(`/marketplace/orders/${orderId}`);
      } else {
        console.error('Invalid order response:', response);
        throw new Error('Invalid order response from server');
      }
    } catch {
      // Error handled by mutation
    }
  };

  if (error) {
    return <ErrorDisplay error={error} title="Failed to load listing" onRetry={() => refetch()} />;
  }

  if (isLoading) {
    return <DetailPageSkeleton />;
  }

  if (!listing) {
    return <ErrorDisplay error="Listing not found" title="Listing not found" />;
  }

  const effectiveTenantId = activeTenantId || userTenantId;
  const isOwnListing = !!effectiveTenantId && listing.tenant === effectiveTenantId;
  // Same-tenant users can request access (governance); cross-tenant can purchase/get access.
  const canInteract = listing.status === ListingStatus.PUBLISHED &&
    (listing.pricing_model === PricingModel.FREE || listing.pricing_model === PricingModel.FREE_AUTO_APPROVE || listing.pricing_model === PricingModel.REQUEST_APPROVAL);

  const priceNum = listing.price_amount != null ? Number(listing.price_amount) : 0;
  const needsPaidCheckout = !isOwnListing && priceNum > 0;

  return (
    <div className="listing-detail-page">
      <div className="listing-detail-header">
        <Button onClick={() => navigate('/marketplace')} variant="ghost">
          ← Back to Marketplace
        </Button>
        <div className="listing-detail-title-section">
          <h1>{listing.title || 'Untitled Listing'}</h1>
          <span className={`listing-status listing-status-${listing.status.toLowerCase()}`}>
            {listing.status}
          </span>
        </div>
        {id && (
          <div className="listing-uuid" data-testid="listing-uuid">
            <UuidWithCopy value={id} label="Listing ID" />
          </div>
        )}
      </div>

      <div className="listing-detail-content">
        <Breadcrumbs
          items={[
            { label: 'Home', href: '/' },
            { label: 'Marketplace', href: '/marketplace' },
            { label: listing.title || 'Listing' },
          ]}
        />
        <div className="listing-detail-main">
          <div className="listing-section">
            <h2>Description</h2>
            <p>{listing.long_description || listing.description || 'No description available'}</p>
          </div>

          {listing.domain && (
            <div className="listing-section">
              <h2>Domain</h2>
              <p>{listing.domain}</p>
            </div>
          )}

          {listing.tags && listing.tags.length > 0 && (
            <div className="listing-section">
              <h2>Tags</h2>
              <div className="listing-tags">
                {(Array.isArray(listing.tags) ? listing.tags : listing.tags.split(',')).map((tag: string, idx: number) => (
                  <span key={idx} className="listing-tag">
                    {typeof tag === 'string' ? tag.trim() : String(tag).trim()}
                  </span>
                ))}
              </div>
            </div>
          )}

          <div className="listing-section">
            <h2>Pricing</h2>
            <p className="listing-pricing-info">
              {listing.pricing_model === PricingModel.FREE || listing.pricing_model === PricingModel.FREE_AUTO_APPROVE
                ? 'Free'
                : listing.price_amount
                ? `${listing.currency || '$'}${listing.price_amount}`
                : 'Request Access'}
            </p>
            <p className="listing-pricing-model">
              Model: {listing.pricing_model === PricingModel.FREE_AUTO_APPROVE
                ? 'Free (Auto-approve)'
                : listing.pricing_model === PricingModel.REQUEST_APPROVAL
                ? 'Request Approval'
                : 'Free'}
            </p>
          </div>

          {listing.published_at && (
            <div className="listing-section">
              <h2>Published</h2>
              <p>{new Date(listing.published_at).toLocaleDateString()}</p>
            </div>
          )}

          {listing.asset && (
            <div className="listing-section">
              <h2>Data Preview</h2>
              <p>View the source asset for schema details and sample data.</p>
              <Button
                variant="secondary"
                onClick={() => navigate(`/assets/${listing.asset}`)}
              >
                View Source Asset
              </Button>
            </div>
          )}
        </div>

        <div className="listing-detail-sidebar">
          <div className="listing-actions-card">
            {/* Pricing display */}
            <div className="listing-price-display">
              {needsPaidCheckout ? (
                <>
                  <span className="listing-price-amount">
                    {listing.currency === 'EUR' ? '€' : listing.currency === 'GBP' ? '£' : '$'}
                    {Number(listing.price_amount).toFixed(2)}
                  </span>
                  {listing.metadata_json?.billing_cycle && (
                    <span className="listing-price-cycle">
                      / {String(listing.metadata_json.billing_cycle) === 'monthly' ? 'mo' : 'yr'}
                    </span>
                  )}
                  {listing.metadata_json?.pricing_description && (
                    <p className="listing-price-desc">{String(listing.metadata_json.pricing_description)}</p>
                  )}
                </>
              ) : (
                <span className="listing-price-amount listing-price-free">Free</span>
              )}
            </div>

            {isOwnListing && canInteract && (
              <p className="listing-action-hint listing-action-hint--info">
                Internal access request — requires approval from data owner.
              </p>
            )}
            {canInteract && (
              <Button
                variant="primary"
                className="btn-large"
                onClick={
                  // Same-tenant: always regular order (governance, no payment)
                  // Cross-tenant + paid: Stripe checkout
                  // Cross-tenant + free: regular order
                  isOwnListing ? handlePurchase
                    : needsPaidCheckout && id ? () => navigate(`/marketplace/checkout/${id}`)
                    : handlePurchase
                }
                loading={createOrderMutation.isPending}
              >
                {createOrderMutation.isPending ? (
                  <>
                    <LoadingSpinner size="small" />
                    Processing...
                  </>
                ) : isOwnListing ? (
                  'Request Access'
                ) : needsPaidCheckout ? (
                  `Purchase for ${listing.currency === 'EUR' ? '€' : listing.currency === 'GBP' ? '£' : '$'}${Number(listing.price_amount).toFixed(2)}`
                ) : listing.pricing_model === PricingModel.FREE_AUTO_APPROVE ? (
                  'Get Free Access'
                ) : (
                  'Request Access'
                )}
              </Button>
            )}
            <div className="listing-meta">
              <div className="listing-meta-item">
                <span className="listing-meta-label">Pricing Model:</span>
                <span className="listing-meta-value">
                  {listing.pricing_model === PricingModel.FREE_AUTO_APPROVE
                    ? 'Free — instant access'
                    : listing.pricing_model === PricingModel.REQUEST_APPROVAL
                    ? needsPaidCheckout ? 'Paid — requires approval' : 'Free — requires approval'
                    : 'Free'}
                </span>
              </div>
              <div className="listing-meta-item">
                <span className="listing-meta-label">Asset ID:</span>
                <span className="listing-meta-value">{listing.asset}</span>
              </div>
              <div className="listing-meta-item">
                <span className="listing-meta-label">Created:</span>
                <span className="listing-meta-value">
                  {new Date(listing.created_at).toLocaleDateString()}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

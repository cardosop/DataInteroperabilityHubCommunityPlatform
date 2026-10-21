/**
 * Phase 278.H.3 — Side-by-side listing comparison tool.
 *
 * Select 2-3 listings and compare schema, pricing, compliance, and
 * sample availability in a responsive side-by-side layout.
 *
 * Usage:
 *   <ComparisonView listings={selectedListings} onClose={handleClose} />
 */
import { useEffect, useRef } from 'react';
import type { Listing } from '../../../shared/types/marketplace';
import { PricingModel } from '../../../shared/types/marketplace';
import type { ComplianceRunSummary } from '../../../shared/types/complianceDiscovery';
import { ComplianceBadge } from '../../compliance/components/ComplianceBadge';
import { TrustSignalsBar } from './TrustSignalsBar';
import { formatCurrency } from '../../../shared/i18n/formatters';
import {
  emitUxActivationEvent,
  type ComparisonDetail,
} from '../../../shared/telemetry/uxActivationTelemetry';
import './ComparisonView.css';

interface ComparisonViewProps {
  listings: Listing[];
  onClose: () => void;
}

export function ComparisonView({ listings, onClose }: ComparisonViewProps) {
  const listingIds = listings.map((l) => l.id);
  // Track opened once on mount
  const hasEmittedOpened = useRef(false);
  useEffect(() => {
    if (!hasEmittedOpened.current) {
      hasEmittedOpened.current = true;
      emitUxActivationEvent('meshant.comparison.opened', {
        listing_count: listings.length,
        listing_ids: listingIds,
      } satisfies ComparisonDetail);
    }
  }, [listings.length, listingIds]);

  if (listings.length < 2) return null;

  const handleClose = () => {
    emitUxActivationEvent('meshant.comparison.closed', {
      listing_count: listings.length,
      listing_ids: listingIds,
    } satisfies ComparisonDetail);
    onClose();
  };

  return (
    <div className="comparison-overlay" data-testid="comparison-overlay" onClick={handleClose} onKeyDown={(e) => { if (e.key === "Escape") handleClose(); }} tabIndex={-1}>
      <div
        className="comparison-modal"
        data-testid="comparison-modal"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-label={`Compare ${listings.length} listings`}
      >
        <div className="comparison-header">
          <h2>Compare Listings ({listings.length})</h2>
          <button
            className="comparison-close-btn"
            onClick={handleClose}
            aria-label="Close comparison"
          >
            ✕
          </button>
        </div>

        <div className="comparison-grid" style={{ '--cols': listings.length } as React.CSSProperties}>
          {/* Header row — listing titles */}
          <div className="comparison-row comparison-row-header">
            <div className="comparison-label"></div>
            {listings.map((listing) => (
              <div key={listing.id} className="comparison-cell comparison-title-cell">
                <h3>{listing.title || 'Untitled'}</h3>
                {listing.provider_name && (
                  <span className="comparison-provider">by {listing.provider_name}</span>
                )}
              </div>
            ))}
          </div>

          {/* Status & Trust Signals */}
          <ComparisonRow label="Trust & Compliance">
            {listings.map((listing) => (
              <div key={listing.id} className="comparison-cell">
                <TrustSignalsBar
                  kycStatus={listing.kyc_status}
                  complianceGrade={listing.compliance_grade as 'PASS' | 'WARN' | 'FAIL' | 'UNKNOWN' | undefined}
                  sampleAvailable={listing.sample_available}
                  updatedAt={listing.updated_at}
                />
                <ComplianceBadge summary={listing.latest_compliance_run as ComplianceRunSummary | null | undefined} compact />
              </div>
            ))}
          </ComparisonRow>

          {/* Pricing */}
          <ComparisonRow label="Pricing">
            {listings.map((listing) => (
              <div key={listing.id} className="comparison-cell">
                <div className="comparison-pricing">
                  <span className="comparison-pricing-model">
                    {listing.pricing_model === PricingModel.FREE
                      ? 'Free'
                      : listing.pricing_model === PricingModel.FREE_AUTO_APPROVE
                        ? 'Free (Auto-approve)'
                        : 'Request Approval'}
                  </span>
                  {listing.price_amount && Number(listing.price_amount) > 0 && (
                    <span className="comparison-price">
                      {formatCurrency(Number(listing.price_amount) * 100, listing.currency || 'USD')}
                    </span>
                  )}
                </div>
              </div>
            ))}
          </ComparisonRow>

          {/* Domain */}
          <ComparisonRow label="Domain">
            {listings.map((listing) => (
              <div key={listing.id} className="comparison-cell">
                {listing.domain || <span className="comparison-na">—</span>}
              </div>
            ))}
          </ComparisonRow>

          {/* Description */}
          <ComparisonRow label="Description">
            {listings.map((listing) => (
              <div key={listing.id} className="comparison-cell comparison-description">
                {listing.short_description || listing.description || (
                  <span className="comparison-na">No description</span>
                )}
              </div>
            ))}
          </ComparisonRow>

          {/* Tags */}
          <ComparisonRow label="Tags">
            {listings.map((listing) => (
              <div key={listing.id} className="comparison-cell">
                {listing.tags && (Array.isArray(listing.tags) ? listing.tags : []).length > 0 ? (
                  <div className="comparison-tags">
                    {(Array.isArray(listing.tags) ? listing.tags : []).map((tag, i) => (
                      <span key={i} className="comparison-tag">{String(tag)}</span>
                    ))}
                  </div>
                ) : (
                  <span className="comparison-na">—</span>
                )}
              </div>
            ))}
          </ComparisonRow>

          {/* Sample availability */}
          <ComparisonRow label="Sample Data">
            {listings.map((listing) => (
              <div key={listing.id} className="comparison-cell">
                {listing.sample_available ? (
                  <span className="comparison-available">Available</span>
                ) : (
                  <span className="comparison-na">Not available</span>
                )}
              </div>
            ))}
          </ComparisonRow>

          {/* Status */}
          <ComparisonRow label="Status">
            {listings.map((listing) => (
              <div key={listing.id} className="comparison-cell">
                <span className={`listing-status listing-status-${listing.status.toLowerCase()}`}>
                  {listing.status}
                </span>
              </div>
            ))}
          </ComparisonRow>

          {/* Published */}
          <ComparisonRow label="Published">
            {listings.map((listing) => (
              <div key={listing.id} className="comparison-cell">
                {listing.published_at
                  ? new Date(listing.published_at).toLocaleDateString()
                  : <span className="comparison-na">—</span>}
              </div>
            ))}
          </ComparisonRow>
        </div>

        <div className="comparison-footer">
          <button className="comparison-close-btn-secondary" onClick={handleClose}>
            Close
          </button>
        </div>
      </div>
    </div>
  );
}

function ComparisonRow({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="comparison-row">
      <div className="comparison-label">{label}</div>
      {children}
    </div>
  );
}

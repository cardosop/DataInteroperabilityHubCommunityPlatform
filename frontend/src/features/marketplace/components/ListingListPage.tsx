/**
 * Listing List Page
 * Browse and search marketplace listings
 */

import { useEffect, useMemo, useState, type ReactNode } from 'react';
import { useNavigate } from 'react-router-dom';
import { useListings, useSearchListings } from '../hooks/useListings';
import { ListPageSkeleton } from '../../../shared/components/skeletons/ListPageSkeleton';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { EmptyState } from '../../../shared/components/EmptyState';
import { useDebouncedValue } from '../../../shared/hooks/useDebouncedValue';
import { ListingStatus, PricingModel, ProductCategory, type Listing, type ListingListFilters } from '../../../shared/types/marketplace';
import { SavedSearchButton } from './SavedSearchButton';
import { TrustSignalsBar } from './TrustSignalsBar';
import { ComparisonView } from './ComparisonView';
import { QuickPreviewModal } from './QuickPreviewModal';
import { useAuthStore } from '../../auth/store/authStore';
import './ListingListPage.css';
import { Button } from '../../../shared/components/Button';

export function ListingListPage() {
  const navigate = useNavigate();
  const userTenantId = useAuthStore((s) => s.user?.tenant_id ?? null);
  const activeTenantId = useAuthStore((s) => s.active_tenant_id);
  const effectiveTenantId = activeTenantId || userTenantId;
  const [page, setPage] = useState(1);
  const [pageSize] = useState(50);
  const [search, setSearch] = useState('');
  const [domainFilter, setDomainFilter] = useState<string>('');
  const [pricingFilter, setPricingFilter] = useState<PricingModel | ''>('');
  const [statusFilter, setStatusFilter] = useState<ListingStatus | ''>('');
  const [categoryFilter, setCategoryFilter] = useState<ProductCategory | ''>('');
  // Phase 278.H.3 — comparison selection state (max 3 listings).
  const [compareIds, setCompareIds] = useState<string[]>([]);
  const [comparisonOpen, setComparisonOpen] = useState(false);
  // Phase 278.H.5 — quick-preview target; null = modal closed.
  const [previewListing, setPreviewListing] = useState<{
    id: string;
    title: string;
  } | null>(null);
  // PR 5.3: debounce the search input. Both the main listings query and
  // the search-specific query consume the debounced value.
  const debouncedSearch = useDebouncedValue(search, 300);

  const filters = {
    page,
    page_size: pageSize,
    search: debouncedSearch || undefined,
    domain: domainFilter || undefined,
    pricing_model: pricingFilter || undefined,
    status: statusFilter || undefined,
    product_category: categoryFilter || undefined,
    ordering: '-created_at',
  };

  const { data, isLoading, error, refetch } = useListings(filters);
  // Only use search when there's actually a (debounced) search query
  const searchQuery = useSearchListings(debouncedSearch, filters);

  // Use search results if the debounced query is non-empty, otherwise use regular list
  const hasSearch = debouncedSearch.length > 0;
  const displayData = hasSearch ? searchQuery.data : data;
  // The domain select was a dead control (only "All Domains" ever
  // rendered — the marketplace API has no domains endpoint, so nothing
  // populated it). Derive the options from the loaded listings instead.
  // Page-scoped by design: after filtering by domain X the option list
  // collapses to X, and "All Domains" is the reset path back.
  const domainOptions = useMemo(() => {
    const domains = new Set<string>();
    for (const listing of displayData?.results ?? []) {
      if (listing.domain) domains.add(listing.domain);
    }
    return Array.from(domains).sort();
  }, [displayData]);
  const displayIsLoading = hasSearch ? searchQuery.isLoading : isLoading;
  const displayError = hasSearch ? searchQuery.error : error;

  const handleListingClick = (listingId: string) => {
    navigate(`/marketplace/listings/${listingId}`);
  };

  const handlePublishClick = () => {
    navigate('/marketplace/publish');
  };

  const handleOrdersClick = () => {
    navigate('/marketplace/orders');
  };

  const toggleCompare = (listingId: string) => {
    setCompareIds((prev) => {
      if (prev.includes(listingId)) {
        return prev.filter((id) => id !== listingId);
      }
      // Max-3 constraint: the 4th checkbox is disabled while 3 are
      // selected, so this branch is defensive only.
      if (prev.length >= 3) return prev;
      return [...prev, listingId];
    });
  };

  const clearCompare = () => setCompareIds([]);

  // Resolve the selected ids back to Listing objects for ComparisonView.
  const compareListings = (displayData?.results ?? []).filter((l: Listing) =>
    compareIds.includes(l.id),
  );

  // Phase 278.H.3 — a11y test hook. The focus-management E2E opens the
  // comparison modal through React state directly
  // (window.__listingListPage.openComparison()) to bypass DOM-click
  // timing; the feature's original design shipped this hook and the
  // spec still expects it. Cleaned up on unmount.
  useEffect(() => {
    const win = window as unknown as {
      __listingListPage?: { openComparison: () => void };
    };
    win.__listingListPage = { openComparison: () => setComparisonOpen(true) };
    return () => {
      delete win.__listingListPage;
    };
  }, []);

  const hasFilters = !!(
    debouncedSearch ||
    domainFilter ||
    pricingFilter ||
    statusFilter ||
    categoryFilter
  );

  // Track B structural inversion: header + filter bar render unconditionally.
  // Previously the filter bar was duplicated across empty and success branches;
  // inversion deduplicates to a single render site.
  let mainContent: ReactNode;
  if (displayIsLoading) {
    mainContent = <ListPageSkeleton />;
  } else if (displayError) {
    mainContent = (
      <ErrorDisplay
        error={displayError}
        title="Failed to load listings"
        onRetry={() => refetch()}
      />
    );
  } else if (!displayData || displayData.results.length === 0) {
    mainContent = (
      <EmptyState
        title="No listings found"
        message={
          hasFilters
            ? 'Try adjusting your filters to see more results.'
            : 'No marketplace listings available yet.'
        }
        action={!hasFilters ? { label: 'Publish Listing', onClick: handlePublishClick } : undefined}
      />
    );
  } else {
    mainContent = (
      <>
        <div className="listing-list-grid" data-testid="listing-list-grid">
          {displayData.results.map((listing) => (
            // Shell wrapper: the toolbar below the card holds the
            // interactive controls OUTSIDE the role="button" card — a
            // checkbox/button nested inside a childrenPresentational
            // role trips axe's nested-interactive rule (serious), which
            // the marketplace a11y audit hard-gates.
            <div key={listing.id} className="listing-card-shell">
              <div
                className="listing-card"
                data-listing-id={listing.id}
                onClick={() => handleListingClick(listing.id)}
                role="button"
                tabIndex={0}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    handleListingClick(listing.id);
                  }
                }}
              >
                <div className="listing-card-header">
                  <h3>{listing.title || 'Untitled Listing'}</h3>
                  <span className={`listing-status listing-status-${listing.status.toLowerCase()}`}>
                    {listing.status}
                  </span>
                  {listing.product_category === ProductCategory.ML_MODEL && (
                    <span className="listing-category-badge listing-category-ml">ML Model</span>
                  )}
                </div>
                <p className="listing-card-description">
                  {listing.short_description || listing.description || 'No description available'}
                </p>
                <div className="listing-card-footer">
                  {effectiveTenantId && listing.tenant !== effectiveTenantId && (
                    <span className="listing-external-badge">External</span>
                  )}
                  <span className="listing-pricing">
                    {listing.pricing_model === PricingModel.FREE ||
                    listing.pricing_model === PricingModel.FREE_AUTO_APPROVE
                      ? 'Free'
                      : listing.price_amount && Number(listing.price_amount) > 0
                        ? `${listing.currency === 'EUR' ? '€' : listing.currency === 'GBP' ? '£' : '$'}${Number(listing.price_amount).toFixed(2)}${listing.metadata_json?.billing_cycle ? (String(listing.metadata_json.billing_cycle) === 'monthly' ? '/mo' : '/yr') : ''}`
                        : 'Request Access'}
                  </span>
                  {listing.domain && <span className="listing-domain">{listing.domain}</span>}
                  {/* Phase 278.V.6 — trust-signals bar in the card footer.
                      Previously mounted only in ComparisonView; the card
                      integration never landed, so the trust-signals E2E
                      counted zero bars on a page full of cards (b6 #4).
                      The bar is non-interactive — clicks bubble to the
                      card's navigation handler like the rest of the footer. */}
                  <TrustSignalsBar
                    kycStatus={listing.kyc_status}
                    complianceGrade={
                      listing.compliance_grade as
                        | 'PASS'
                        | 'WARN'
                        | 'FAIL'
                        | 'UNKNOWN'
                        | undefined
                    }
                    sampleAvailable={listing.sample_available}
                    updatedAt={listing.updated_at}
                  />
                </div>
              </div>
              {/* b6-skip: compare + preview entries (Phase 278.H.3/.H.5) —
                  both shipped but were never mounted, so
                  comparison-side-by-side.spec.ts counted zero
                  .listing-card-compare checkboxes and
                  quick-preview-modal.spec.ts zero .listing-card-preview-btn
                  buttons (b6 #3/#4 precedent). The toolbar is a sibling of
                  the role="button" card — see the shell comment above for
                  the nested-interactive axe constraint. Max 3 selections;
                  the 4th checkbox disables once 3 are chosen. */}
              <div className="listing-card-toolbar">
                <label
                  className="listing-card-compare"
                  title="Select for comparison (max 3)"
                >
                  <input
                    type="checkbox"
                    checked={compareIds.includes(listing.id)}
                    onChange={() => toggleCompare(listing.id)}
                    disabled={
                      compareIds.length >= 3 && !compareIds.includes(listing.id)
                    }
                    aria-label={`Compare ${listing.title || 'Untitled Listing'}`}
                  />
                  <span>Compare</span>
                </label>
                <button
                  type="button"
                  className="listing-card-preview-btn"
                  onClick={() =>
                    setPreviewListing({
                      id: listing.id,
                      title: listing.title || 'Untitled Listing',
                    })
                  }
                >
                  Preview
                </button>
              </div>
            </div>
          ))}
        </div>

        {displayData.count > pageSize && (
          <div className="listing-list-pagination">
            <Button
              variant="secondary"
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page === 1}
            >
              Previous
            </Button>
            <span className="pagination-info">
              Page {page} of {Math.ceil(displayData.count / pageSize)}
            </span>
            <Button
              variant="secondary"
              onClick={() => setPage((p) => p + 1)}
              disabled={page >= Math.ceil(displayData.count / pageSize)}
            >
              Next
            </Button>
          </div>
        )}
      </>
    );
  }

  return (
    <div className="listing-list-page" data-testid="listing-list-page">
      <div className="listing-list-header" data-testid="listing-list-header">
        <h1>Marketplace</h1>
        <div className="listing-list-header-actions">
          <Button variant="secondary" onClick={handleOrdersClick}>
            My Orders
          </Button>
          <Button variant="primary" onClick={handlePublishClick}>
            Publish Listing
          </Button>
        </div>
      </div>

      <div className="listing-list-filters" data-testid="listing-list-filters">
        <input
          type="text"
          placeholder="Search listings..."
          value={search}
          onChange={(e) => {
            setSearch(e.target.value);
            setPage(1);
          }}
          className="filter-input"
          aria-label="Search marketplace listings"
        />
        <select
          value={domainFilter}
          onChange={(e) => {
            setDomainFilter(e.target.value);
            setPage(1);
          }}
          className="filter-select"
          aria-label="Filter by domain"
        >
          <option value="">All Domains</option>
          {domainOptions.map((domain) => (
            <option key={domain} value={domain}>
              {domain}
            </option>
          ))}
        </select>
        <select
          value={pricingFilter}
          onChange={(e) => {
            setPricingFilter(e.target.value as PricingModel | '');
            setPage(1);
          }}
          className="filter-select"
          aria-label="Filter by pricing model"
        >
          <option value="">All Pricing Models</option>
          <option value={PricingModel.FREE}>Free</option>
          <option value={PricingModel.FREE_AUTO_APPROVE}>Free (Auto-approve)</option>
          <option value={PricingModel.REQUEST_APPROVAL}>Request Approval</option>
        </select>
        <select
          value={statusFilter}
          onChange={(e) => {
            setStatusFilter(e.target.value as ListingStatus | '');
            setPage(1);
          }}
          className="filter-select"
          aria-label="Filter by status"
        >
          <option value="">All Statuses</option>
          <option value={ListingStatus.DRAFT}>Draft</option>
          <option value={ListingStatus.PUBLISHED}>Published</option>
          <option value={ListingStatus.UNLISTED}>Unlisted</option>
        </select>
        <select
          value={categoryFilter}
          onChange={(e) => {
            setCategoryFilter(e.target.value as ProductCategory | '');
            setPage(1);
          }}
          className="filter-select"
          aria-label="Filter by category"
        >
          <option value="">All Categories</option>
          <option value={ProductCategory.DATA}>Data Products</option>
          <option value={ProductCategory.ML_MODEL}>ML Models</option>
        </select>
        {/* Phase 278.H.4 — saved-search trigger + dropdown, mounted next to
            the filters it snapshots/applies. Previously the component
            shipped but was never mounted, so the saved-search CRUD E2E
            waited 120s on a trigger that couldn't render (b6 #3). */}
        <SavedSearchButton
          currentFilters={filters}
          onApply={(applied: ListingListFilters) => {
            setSearch(applied.search ?? '');
            setDomainFilter(applied.domain ?? '');
            setPricingFilter(applied.pricing_model ?? '');
            setStatusFilter(applied.status ?? '');
            setCategoryFilter(applied.product_category ?? '');
            setPage(1);
          }}
        />
      </div>

      {mainContent}

      {/* Phase 278.H.3 — compare action bar. Renders once ≥1 listing is
          selected; the Compare button only appears at ≥2 (ComparisonView
          itself returns null below 2). Clear resets all selections. */}
      {compareIds.length > 0 && (
        <div
          className="compare-action-bar"
          data-testid="compare-action-bar"
          role="region"
          aria-label="Listing comparison selection"
        >
          <span className="compare-action-bar-text">
            {compareIds.length} selected (max 3)
          </span>
          {compareIds.length >= 2 && (
            <button
              type="button"
              className="compare-action-bar-btn"
              onClick={() => setComparisonOpen(true)}
            >
              Compare
            </button>
          )}
          <button type="button" className="compare-action-bar-clear" onClick={clearCompare}>
            Clear
          </button>
        </div>
      )}

      {/* Phase 278.H.3 — side-by-side comparison modal. */}
      {comparisonOpen && compareListings.length >= 2 && (
        <ComparisonView
          listings={compareListings}
          onClose={() => setComparisonOpen(false)}
        />
      )}

      {/* Phase 278.H.5 — quick preview modal for the card's Preview button. */}
      {previewListing && (
        <QuickPreviewModal
          listingId={previewListing.id}
          listingTitle={previewListing.title}
          onClose={() => setPreviewListing(null)}
        />
      )}
    </div>
  );
}

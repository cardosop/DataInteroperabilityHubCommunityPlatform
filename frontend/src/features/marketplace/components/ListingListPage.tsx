/**
 * Listing List Page
 * Browse and search marketplace listings
 */

import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useListings, useSearchListings } from '../hooks/useListings';
import { ListPageSkeleton } from '../../../shared/components/skeletons/ListPageSkeleton';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { EmptyState } from '../../../shared/components/EmptyState';
import { ListingStatus, PricingModel, ProductCategory } from '../../../shared/types/marketplace';
import './ListingListPage.css';
import { Button } from '../../../shared/components/Button';

export function ListingListPage() {
  const navigate = useNavigate();
  const [page, setPage] = useState(1);
  const [pageSize] = useState(50);
  const [search, setSearch] = useState('');
  const [domainFilter, setDomainFilter] = useState<string>('');
  const [pricingFilter, setPricingFilter] = useState<PricingModel | ''>('');
  const [statusFilter, setStatusFilter] = useState<ListingStatus | ''>('');
  const [categoryFilter, setCategoryFilter] = useState<ProductCategory | ''>('');

  const filters = {
    page,
    page_size: pageSize,
    search: search || undefined,
    domain: domainFilter || undefined,
    pricing_model: pricingFilter || undefined,
    status: statusFilter || undefined,
    product_category: categoryFilter || undefined,
    ordering: '-created_at',
  };

  const { data, isLoading, error, refetch } = useListings(filters);
  // Only use search when there's actually a search query
  const searchQuery = useSearchListings(search, filters);

  // Use search results if search query is provided, otherwise use regular list
  const displayData = search && search.length > 0 ? searchQuery.data : data;
  const displayIsLoading = search && search.length > 0 ? searchQuery.isLoading : isLoading;
  const displayError = search && search.length > 0 ? searchQuery.error : error;

  const handleListingClick = (listingId: string) => {
    navigate(`/marketplace/listings/${listingId}`);
  };

  const handlePublishClick = () => {
    navigate('/marketplace/publish');
  };

  const handleOrdersClick = () => {
    navigate('/marketplace/orders');
  };

  if (displayIsLoading) {
    return <ListPageSkeleton />;
  }

  if (displayError) {
    return <ErrorDisplay error={displayError} title="Failed to load listings" onRetry={() => refetch()} />;
  }

  if (!displayData || displayData.results.length === 0) {
    const hasFilters = !!(search || domainFilter || pricingFilter || statusFilter || categoryFilter);
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
          />
        </div>

        <EmptyState
          title="No listings found"
          message={hasFilters
            ? "Try adjusting your filters to see more results."
            : "No marketplace listings available yet."}
          action={!hasFilters
            ? { label: 'Publish Listing', onClick: handlePublishClick }
            : undefined}
        />
      </div>
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
        />
        <select
          value={domainFilter}
          onChange={(e) => {
            setDomainFilter(e.target.value);
            setPage(1);
          }}
          className="filter-select"
        >
          <option value="">All Domains</option>
        </select>
        <select
          value={pricingFilter}
          onChange={(e) => {
            setPricingFilter(e.target.value as PricingModel | '');
            setPage(1);
          }}
          className="filter-select"
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
        >
          <option value="">All Categories</option>
          <option value={ProductCategory.DATA}>Data Products</option>
          <option value={ProductCategory.ML_MODEL}>ML Models</option>
        </select>
      </div>

      <div className="listing-list-grid">
        {displayData.results.map((listing) => (
          <div
            key={listing.id}
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
              <span className="listing-pricing">
                {listing.pricing_model === PricingModel.FREE || listing.pricing_model === PricingModel.FREE_AUTO_APPROVE
                  ? 'Free'
                  : listing.price_amount && Number(listing.price_amount) > 0
                  ? `${listing.currency === 'EUR' ? '€' : listing.currency === 'GBP' ? '£' : '$'}${Number(listing.price_amount).toFixed(2)}${listing.metadata_json?.billing_cycle ? (listing.metadata_json.billing_cycle === 'monthly' ? '/mo' : '/yr') : ''}`
                  : 'Request Access'}
              </span>
              {listing.domain && <span className="listing-domain">{listing.domain}</span>}
            </div>
          </div>
        ))}
      </div>

      {displayData.count > pageSize && (
        <div className="listing-list-pagination">
          <Button
 variant="secondary"
 onClick={() => setPage((p) => Math.max(1, p - 1))}
 disabled={page === 1}>
            Previous
          </Button>
          <span className="pagination-info">
            Page {page} of {Math.ceil(displayData.count / pageSize)}
          </span>
          <Button
 variant="secondary"
 onClick={() => setPage((p) => p + 1)}
 disabled={page>= Math.ceil(displayData.count / pageSize)}>
            Next
          </Button>
        </div>
      )}
    </div>
  );
}

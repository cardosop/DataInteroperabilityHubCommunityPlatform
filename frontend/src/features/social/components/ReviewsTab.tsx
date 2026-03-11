/**
 * Reviews Tab
 * Displays and manages asset reviews
 */

import { useEffect, useState } from 'react';
import { useReviews, useSubmitReview } from '../hooks/useSocial';
import { useAssets } from '../../assets/hooks/useAssets';
import { LoadingSpinner } from '../../../shared/components/LoadingSpinner';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { EmptyState } from '../../../shared/components/EmptyState';
import type { ReviewStatus } from '../../../shared/types/social';
import './ReviewsTab.css';

interface ReviewsTabProps {
  assetId: string | null;
  onAssetSelect?: (assetId: string) => void;
  /** When true, hide asset selector (e.g. when embedded in AssetDetailPage with assetId from route) */
  assetIdOnly?: boolean;
}

export function ReviewsTab({ assetId, onAssetSelect: _onAssetSelect, assetIdOnly = false }: ReviewsTabProps) {
  const [selectedAssetId, setSelectedAssetId] = useState<string | null>(assetId);

  useEffect(() => {
    if (!assetIdOnly) setSelectedAssetId(assetId);
  }, [assetId, assetIdOnly]);
  const [showForm, setShowForm] = useState(false);
  const [reviewText, setReviewText] = useState('');
  const [rating, setRating] = useState<number | undefined>(undefined);
  const [statusFilter, setStatusFilter] = useState<ReviewStatus | ''>('');

  const effectiveAssetId = assetIdOnly ? assetId : selectedAssetId;
  const { data: reviewsData, isLoading, error, refetch } = useReviews(effectiveAssetId || '', {
    page_size: 50,
    status: statusFilter || undefined,
  });
  const { data: assetsData } = useAssets({ page_size: 100 });
  const submitReviewMutation = useSubmitReview();

  const handleSubmitReview = async () => {
    if (!effectiveAssetId || !reviewText.trim() || reviewText.length < 10) return;

    try {
      await submitReviewMutation.mutateAsync({
        asset_id: effectiveAssetId,
        review_text: reviewText,
        rating: rating,
      });
      setReviewText('');
      setRating(undefined);
      setShowForm(false);
      refetch();
    } catch (err) {
      // Error handled by mutation
    }
  };

  if (isLoading) {
    return <LoadingSpinner message="Loading reviews..." />;
  }

  if (error) {
    return <ErrorDisplay error={error} title="Failed to load reviews" onRetry={() => refetch()} />;
  }

  const reviews = reviewsData?.results || [];

  return (
    <div className="reviews-tab">
      {!assetIdOnly && (
        <div className="reviews-tab-header">
          <div className="asset-selector">
            <label htmlFor="asset-select">Select Asset:</label>
            <select
              id="asset-select"
              value={selectedAssetId || ''}
              onChange={(e) => {
                setSelectedAssetId(e.target.value || null);
                setShowForm(false);
              }}
            >
              <option value="">-- Select an asset --</option>
              {assetsData?.results?.map(asset => (
                <option key={asset.id} value={asset.id}>
                  {asset.name}
                </option>
              ))}
            </select>
          </div>
          <div className="filter-controls">
            <label htmlFor="status-filter">Status:</label>
            <select
              id="status-filter"
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value as ReviewStatus | '')}
            >
              <option value="">All</option>
              <option value="APPROVED">Approved</option>
              <option value="PENDING">Pending</option>
              <option value="REJECTED">Rejected</option>
            </select>
          </div>
        </div>
      )}
      {assetIdOnly && (
        <div className="reviews-tab-header">
          <div className="filter-controls">
            <label htmlFor="status-filter-reviews">Status:</label>
            <select
              id="status-filter-reviews"
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value as ReviewStatus | '')}
            >
              <option value="">All</option>
              <option value="APPROVED">Approved</option>
              <option value="PENDING">Pending</option>
              <option value="REJECTED">Rejected</option>
            </select>
          </div>
        </div>
      )}

      {effectiveAssetId && (
        <>
          {!showForm && (
            <button
              className="btn-primary"
              onClick={() => setShowForm(true)}
              type="button"
            >
              Write Review
            </button>
          )}

          {showForm && (
            <div className="review-form">
              <h3>Write Review</h3>
              <div className="rating-input">
                <label>Rating (optional):</label>
                <div className="star-rating-input">
                  {[1, 2, 3, 4, 5].map(star => (
                    <button
                      key={star}
                      type="button"
                      className={`star-button ${star <= (rating || 0) ? 'selected' : ''}`}
                      onClick={() => setRating(star)}
                    >
                      ★
                    </button>
                  ))}
                </div>
              </div>
              <textarea
                placeholder="Write your review (minimum 10 characters)..."
                value={reviewText}
                onChange={(e) => setReviewText(e.target.value)}
                minLength={10}
                maxLength={2000}
                rows={6}
                required
              />
              <div className="char-count">
                {reviewText.length}/2000 characters
              </div>
              <div className="form-actions">
                <button
                  className="btn-primary"
                  onClick={handleSubmitReview}
                  disabled={reviewText.length < 10 || submitReviewMutation.isPending}
                  type="button"
                >
                  {submitReviewMutation.isPending ? 'Submitting...' : 'Submit Review'}
                </button>
                <button
                  className="btn-secondary"
                  onClick={() => {
                    setShowForm(false);
                    setReviewText('');
                    setRating(undefined);
                  }}
                  type="button"
                >
                  Cancel
                </button>
              </div>
            </div>
          )}

          {reviews.length === 0 ? (
            <EmptyState
              title="No reviews yet"
              message="Be the first to review this asset!"
            />
          ) : (
            <div className="reviews-list">
              {reviews.map(review => (
                <div key={review.id} className="review-item">
                  <div className="review-header">
                    <div className="review-meta">
                      {review.rating && (
                        <div className="stars">
                          {[1, 2, 3, 4, 5].map(star => (
                            <span
                              key={star}
                              className={`star ${star <= review.rating! ? 'filled' : ''}`}
                            >
                              ★
                            </span>
                          ))}
                        </div>
                      )}
                      <span className={`review-status status-${review.status.toLowerCase()}`}>
                        {review.status}
                      </span>
                      <span className="review-date">
                        {new Date(review.created_at).toLocaleDateString()}
                      </span>
                    </div>
                    <div className="helpful-count">
                      {review.helpful_count} {review.helpful_count === 1 ? 'person' : 'people'} found this helpful
                    </div>
                  </div>
                  <p className="review-text">{review.review_text}</p>
                </div>
              ))}
            </div>
          )}
        </>
      )}

      {!effectiveAssetId && (
        <EmptyState
          title="Select an asset"
          message="Choose an asset from the dropdown above to view and write reviews."
        />
      )}
    </div>
  );
}

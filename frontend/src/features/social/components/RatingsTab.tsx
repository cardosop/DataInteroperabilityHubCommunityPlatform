/**
 * Ratings Tab
 * Displays and manages asset ratings
 */

import { useState } from 'react';
import { useRatings, useSubmitRating } from '../hooks/useSocial';
import { useAssets } from '../../assets/hooks/useAssets';
import { LoadingSpinner } from '../../../shared/components/LoadingSpinner';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { EmptyState } from '../../../shared/components/EmptyState';
import './RatingsTab.css';

interface RatingsTabProps {
  assetId: string | null;
  onAssetSelect: (assetId: string) => void;
}

export function RatingsTab({ assetId, onAssetSelect: _onAssetSelect }: RatingsTabProps) {
  const [selectedAssetId, setSelectedAssetId] = useState<string | null>(assetId);
  const [rating, setRating] = useState<number>(0);
  const [comment, setComment] = useState('');
  const [showForm, setShowForm] = useState(false);

  const { data: ratingsData, isLoading, error, refetch } = useRatings(selectedAssetId || '', { page_size: 50 });
  const { data: assetsData } = useAssets({ page_size: 100 });
  const submitRatingMutation = useSubmitRating();

  const handleSubmitRating = async () => {
    if (!selectedAssetId || rating === 0) return;

    try {
      await submitRatingMutation.mutateAsync({
        asset_id: selectedAssetId,
        rating,
        comment: comment || undefined,
      });
      setRating(0);
      setComment('');
      setShowForm(false);
      refetch();
    } catch (err) {
      // Error handled by mutation
    }
  };

  const handleStarClick = (value: number) => {
    setRating(value);
    if (!showForm) setShowForm(true);
  };

  if (isLoading) {
    return <LoadingSpinner message="Loading ratings..." />;
  }

  if (error) {
    return <ErrorDisplay error={error} title="Failed to load ratings" onRetry={() => refetch()} />;
  }

  const ratings = ratingsData?.results || [];
  const averageRating = ratings.length > 0
    ? ratings.reduce((sum, r) => sum + r.rating, 0) / ratings.length
    : 0;

  return (
    <div className="ratings-tab">
      <div className="ratings-tab-header">
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
            {assetsData?.results.map(asset => (
              <option key={asset.id} value={asset.id}>
                {asset.name}
              </option>
            ))}
          </select>
        </div>
      </div>

      {selectedAssetId && (
        <>
          <div className="ratings-summary">
            <div className="average-rating">
              <span className="rating-value">{averageRating.toFixed(1)}</span>
              <div className="stars">
                {[1, 2, 3, 4, 5].map(star => (
                  <span
                    key={star}
                    className={`star ${star <= Math.round(averageRating) ? 'filled' : ''}`}
                  >
                    ★
                  </span>
                ))}
              </div>
              <span className="rating-count">({ratings.length} {ratings.length === 1 ? 'rating' : 'ratings'})</span>
            </div>
          </div>

          {!showForm && (
            <button
              className="btn-primary"
              onClick={() => setShowForm(true)}
              type="button"
            >
              Submit Rating
            </button>
          )}

          {showForm && (
            <div className="rating-form">
              <h3>Submit Rating</h3>
              <div className="star-rating-input">
                {[1, 2, 3, 4, 5].map(star => (
                  <button
                    key={star}
                    type="button"
                    className={`star-button ${star <= rating ? 'selected' : ''}`}
                    onClick={() => handleStarClick(star)}
                  >
                    ★
                  </button>
                ))}
              </div>
              <textarea
                placeholder="Optional comment..."
                value={comment}
                onChange={(e) => setComment(e.target.value)}
                maxLength={500}
                rows={3}
              />
              <div className="form-actions">
                <button
                  className="btn-primary"
                  onClick={handleSubmitRating}
                  disabled={rating === 0 || submitRatingMutation.isPending}
                  type="button"
                >
                  {submitRatingMutation.isPending ? 'Submitting...' : 'Submit'}
                </button>
                <button
                  className="btn-secondary"
                  onClick={() => {
                    setShowForm(false);
                    setRating(0);
                    setComment('');
                  }}
                  type="button"
                >
                  Cancel
                </button>
              </div>
            </div>
          )}

          {ratings.length === 0 ? (
            <EmptyState
              title="No ratings yet"
              message="Be the first to rate this asset!"
            />
          ) : (
            <div className="ratings-list">
              {ratings.map(ratingItem => (
                <div key={ratingItem.id} className="rating-item">
                  <div className="rating-header">
                    <div className="stars">
                      {[1, 2, 3, 4, 5].map(star => (
                        <span
                          key={star}
                          className={`star ${star <= ratingItem.rating ? 'filled' : ''}`}
                        >
                          ★
                        </span>
                      ))}
                    </div>
                    <span className="rating-date">
                      {new Date(ratingItem.created_at).toLocaleDateString()}
                    </span>
                  </div>
                  {ratingItem.comment && (
                    <p className="rating-comment">{ratingItem.comment}</p>
                  )}
                </div>
              ))}
            </div>
          )}
        </>
      )}

      {!selectedAssetId && (
        <EmptyState
          title="Select an asset"
          message="Choose an asset from the dropdown above to view and submit ratings."
        />
      )}
    </div>
  );
}

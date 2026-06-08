/**
 * Phase 278.H.1 — Marketplace recommendations widget.
 *
 * Renders two recommendation sections:
 *  - "You might also like" (cross-sell)
 *  - "Trending in your domain" (popularity-weighted recency)
 *
 * Inline feedback: thumbs-up/down on each card.
 */
import { useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { useRecommendations, useSubmitRecommendationFeedback } from '../hooks/useRecommendations';
import { ErrorBoundary } from '../../../shared/components/ErrorBoundary';
import {
  emitUxActivationEvent,
} from '../../../shared/telemetry/uxActivationTelemetry';
import './MarketplaceRecommendations.css';

interface MarketplaceRecommendationsProps {
  domain?: string;
  listingId?: string;
  limit?: number;
}

export function MarketplaceRecommendations({
  domain,
  listingId,
  limit = 5,
}: MarketplaceRecommendationsProps) {
  const navigate = useNavigate();
  const { data, isLoading } = useRecommendations({ domain, listing_id: listingId, limit });
  const feedbackMutation = useSubmitRecommendationFeedback();

  // Track impression once per mount
  const hasEmittedImpression = useRef(false);
  useEffect(() => {
    if (data && !hasEmittedImpression.current) {
      hasEmittedImpression.current = true;
      const { you_might_also_like = [], trending = [] } = data;
      if (trending.length > 0) {
        emitUxActivationEvent('meshant.recommendations.impression', {
          section: 'trending',
          listing_count: trending.length,
          domain,
        });
      }
      if (you_might_also_like.length > 0) {
        emitUxActivationEvent('meshant.recommendations.impression', {
          section: 'you_might_also_like',
          listing_count: you_might_also_like.length,
          domain,
        });
      }
    }
  }, [data, domain]);

  if (isLoading || !data) return null;

  const { you_might_also_like = [], trending = [] } = data;

  if (!you_might_also_like.length && !trending.length) return null;

  const handleCardClick = (id: string, section: 'trending' | 'you_might_also_like') => {
    emitUxActivationEvent('meshant.recommendations.click', {
      listing_id: id,
      section,
    });
    navigate(`/marketplace/listings/${id}`);
  };

  const handleFeedback = (
    e: React.MouseEvent,
    recListingId: string,
    helpful: boolean,
  ) => {
    e.stopPropagation();
    emitUxActivationEvent('meshant.recommendations.feedback', {
      listing_id: recListingId,
      helpful,
    });
    feedbackMutation.mutate({ listingId: recListingId, helpful });
  };

  return (
    <div className="marketplace-recommendations" data-testid="marketplace-recommendations">
      {trending.length > 0 && (
        <section className="rec-section" data-testid="rec-section-trending">
          <h2 className="rec-section-title">Trending in your domain</h2>
          <div className="rec-cards">
            {trending.map((rec) => (
              <div
                key={rec.listing_id ?? rec.id}
                className="rec-card"
                data-testid={`rec-card-${rec.listing_id ?? rec.id}`}
              >
                <div
                  className="rec-card-clickable"
                  onClick={() => handleCardClick(rec.listing_id ?? rec.id, 'trending')}
                  role="button"
                  tabIndex={0}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault();
                      handleCardClick(rec.listing_id ?? rec.id, 'trending');
                    }
                  }}
                  aria-label={`View listing: ${rec.title}`}
                >
                  <div className="rec-card-body">
                    <h3 className="rec-card-title">{rec.title}</h3>
                    {rec.domain && <span className="rec-card-domain">{rec.domain}</span>}
                    <div className="rec-card-reasons">
                      {(rec.reasons?.slice(0, 2) ?? []).map((r, i) => (
                        <span key={i} className="rec-reason-tag">{r.reason}</span>
                      ))}
                    </div>
                  </div>
                </div>
                <div className="rec-card-actions">
                  <button
                    className="rec-feedback-btn"
                    onClick={(e) => handleFeedback(e, rec.listing_id ?? rec.id, true)}
                    aria-label="Helpful"
                    title="Helpful"
                  >
                    👍
                  </button>
                  <button
                    className="rec-feedback-btn"
                    onClick={(e) => handleFeedback(e, rec.listing_id ?? rec.id, false)}
                    aria-label="Not helpful"
                    title="Not helpful"
                  >
                    👎
                  </button>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {you_might_also_like.length > 0 && (
        <section className="rec-section" data-testid="rec-section-cross-sell">
          <h2 className="rec-section-title">You might also like</h2>
          <div className="rec-cards">
            {you_might_also_like.map((rec) => (
              <div
                key={rec.listing_id ?? rec.id}
                className="rec-card"
                data-testid={`rec-card-${rec.listing_id ?? rec.id}`}
              >
                <div
                  className="rec-card-clickable"
                  onClick={() => handleCardClick(rec.listing_id ?? rec.id, 'you_might_also_like')}
                  role="button"
                  tabIndex={0}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault();
                      handleCardClick(rec.listing_id ?? rec.id, 'you_might_also_like');
                    }
                  }}
                  aria-label={`View listing: ${rec.title}`}
                >
                  <div className="rec-card-body">
                    <h3 className="rec-card-title">{rec.title}</h3>
                    {rec.domain && <span className="rec-card-domain">{rec.domain}</span>}
                    <div className="rec-card-score">
                      <span className="rec-score-bar" style={{ width: `${Math.round((rec.score ?? 0) * 100)}%` }} />
                    </div>
                    <div className="rec-card-reasons">
                      {(rec.reasons?.slice(0, 2) ?? []).map((r, i) => (
                        <span key={i} className="rec-reason-tag">{r.reason}</span>
                      ))}
                    </div>
                  </div>
                </div>
                <div className="rec-card-actions">
                  <button
                    className="rec-feedback-btn"
                    onClick={(e) => handleFeedback(e, rec.listing_id ?? rec.id, true)}
                    aria-label="Helpful"
                    title="Helpful"
                  >
                    👍
                  </button>
                  <button
                    className="rec-feedback-btn"
                    onClick={(e) => handleFeedback(e, rec.listing_id ?? rec.id, false)}
                    aria-label="Not helpful"
                    title="Not helpful"
                  >
                    👎
                  </button>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

/**
 * Error-boundary-wrapped recommendations. Gracefully degrades to nothing
 * when the recommendations endpoint fails — marketplace browsing should
 * not break because of a recommendation engine issue.
 */
export function MarketplaceRecommendationsSafe(props: MarketplaceRecommendationsProps) {
  return (
    <ErrorBoundary fallback={null}>
      <MarketplaceRecommendations {...props} />
    </ErrorBoundary>
  );
}

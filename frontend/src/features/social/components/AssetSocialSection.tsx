/**
 * Asset Social Section
 * Embeds Ratings, Reviews, and Comments for a specific asset (e.g. on AssetDetailPage).
 * Capability-gated: only shows sections the user has access to.
 */

import { useEffect, useState } from 'react';
import { useCapabilities } from '../../../shared/hooks/useCapabilities';
import { RatingsTab } from './RatingsTab';
import { ReviewsTab } from './ReviewsTab';
import { CommentsTab } from './CommentsTab';
import './AssetSocialSection.css';

type SocialTabType = 'ratings' | 'reviews' | 'comments';

interface AssetSocialSectionProps {
  /** Asset ID from route (e.g. AssetDetailPage) */
  assetId: string;
}

export function AssetSocialSection({ assetId }: AssetSocialSectionProps) {
  const { isCapabilityAvailable } = useCapabilities();
  const hasRatings = isCapabilityAvailable('social.ratings');
  const hasReviews = isCapabilityAvailable('social.reviews');
  const hasComments = isCapabilityAvailable('social.comments');

  const allTabs: { id: SocialTabType; label: string; available: boolean }[] = [
    { id: 'ratings', label: 'Ratings', available: hasRatings },
    { id: 'reviews', label: 'Reviews', available: hasReviews },
    { id: 'comments', label: 'Comments', available: hasComments },
  ];
  const tabs = allTabs.filter((tab) => tab.available);

  const firstAvailableTab: SocialTabType = hasRatings ? 'ratings' : hasReviews ? 'reviews' : 'comments';
  const [activeTab, setActiveTab] = useState<SocialTabType>(() => firstAvailableTab);

  const isActiveTabAvailable =
    (activeTab === 'ratings' && hasRatings) ||
    (activeTab === 'reviews' && hasReviews) ||
    (activeTab === 'comments' && hasComments);

  useEffect(() => {
    if (!isActiveTabAvailable) {
      setActiveTab(firstAvailableTab);
    }
  }, [isActiveTabAvailable, firstAvailableTab]);

  if (tabs.length === 0) return null;

  return (
    <div className="asset-social-section" data-testid="asset-social-section">
      <h2>Community</h2>
      <div className="asset-social-tabs">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            type="button"
            className={`asset-social-tab ${activeTab === tab.id ? 'active' : ''}`}
            onClick={() => setActiveTab(tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </div>
      <div className="asset-social-content">
        {activeTab === 'ratings' && hasRatings && (
          <RatingsTab assetId={assetId} assetIdOnly />
        )}
        {activeTab === 'reviews' && hasReviews && (
          <ReviewsTab assetId={assetId} assetIdOnly />
        )}
        {activeTab === 'comments' && hasComments && (
          <CommentsTab assetId={assetId} assetIdOnly />
        )}
      </div>
    </div>
  );
}

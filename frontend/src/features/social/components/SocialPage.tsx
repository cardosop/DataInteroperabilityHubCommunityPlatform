/**
 * Social Page
 * Main page for social features: ratings, reviews, comments, and communities
 */

import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useCapabilities } from '../../../shared/hooks/useCapabilities';
import { UnavailablePage } from '../../../shared/components/UnavailablePage';
import { RatingsTab } from './RatingsTab';
import { ReviewsTab } from './ReviewsTab';
import { CommentsTab } from './CommentsTab';
import { CommunitiesTab } from './CommunitiesTab';
import './SocialPage.css';

type TabType = 'ratings' | 'reviews' | 'comments' | 'communities';

export function SocialPage() {
  const navigate = useNavigate();
  const { isCapabilityAvailable } = useCapabilities();
  const [activeTab, setActiveTab] = useState<TabType>('ratings');
  const [selectedAssetId, setSelectedAssetId] = useState<string | null>(null);

  // Check if any social capability is available
  const hasRatings = isCapabilityAvailable('social.ratings');
  const hasReviews = isCapabilityAvailable('social.reviews');
  const hasComments = isCapabilityAvailable('social.comments');
  const hasCommunities = isCapabilityAvailable('social.communities');

  if (!hasRatings && !hasReviews && !hasComments && !hasCommunities) {
    return (
      <UnavailablePage
        title="Social Features Unavailable"
        message="Social features are not available in this environment. Please contact your administrator."
      />
    );
  }

  const tabs = [
    { id: 'ratings' as TabType, label: 'Ratings', available: hasRatings },
    { id: 'reviews' as TabType, label: 'Reviews', available: hasReviews },
    { id: 'comments' as TabType, label: 'Comments', available: hasComments },
    { id: 'communities' as TabType, label: 'Communities', available: hasCommunities },
  ].filter(tab => tab.available);

  const handleTabChange = (tab: TabType) => {
    setActiveTab(tab);
  };

  const handleAssetSelect = (assetId: string) => {
    setSelectedAssetId(assetId);
    navigate(`/assets/${assetId}`);
  };

  return (
    <div className="social-page">
      <div className="social-page-header">
        <h1>Social Features</h1>
      </div>

      <div className="social-page-tabs">
        {tabs.map(tab => (
          <button
            key={tab.id}
            className={`social-tab ${activeTab === tab.id ? 'active' : ''}`}
            onClick={() => handleTabChange(tab.id)}
            type="button"
          >
            {tab.label}
          </button>
        ))}
      </div>

      <div className="social-page-content">
        {activeTab === 'ratings' && hasRatings && (
          <RatingsTab assetId={selectedAssetId} onAssetSelect={handleAssetSelect} />
        )}
        {activeTab === 'reviews' && hasReviews && (
          <ReviewsTab assetId={selectedAssetId} onAssetSelect={handleAssetSelect} />
        )}
        {activeTab === 'comments' && hasComments && (
          <CommentsTab assetId={selectedAssetId} onAssetSelect={handleAssetSelect} />
        )}
        {activeTab === 'communities' && hasCommunities && (
          <CommunitiesTab />
        )}
      </div>
    </div>
  );
}

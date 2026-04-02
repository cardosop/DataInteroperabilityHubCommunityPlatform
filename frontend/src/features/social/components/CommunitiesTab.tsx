/**
 * Communities Tab
 * Displays and manages data communities
 */

import { useState } from 'react';
import { useCommunities, useCreateOrJoinCommunity, useCommunityMembers } from '../hooks/useSocial';
import { LoadingSpinner } from '../../../shared/components/LoadingSpinner';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { EmptyState } from '../../../shared/components/EmptyState';
import './CommunitiesTab.css';
import { Button } from '../../../shared/components/Button';

export function CommunitiesTab() {
  const [showForm, setShowForm] = useState(false);
  const [communityName, setCommunityName] = useState('');
  const [communityDescription, setCommunityDescription] = useState('');
  const [isPublic, setIsPublic] = useState(true);
  const [selectedCommunityId, setSelectedCommunityId] = useState<string | null>(null);

  const { data: communitiesData, isLoading, error, refetch } = useCommunities({ page_size: 50 });
  const { data: membersData } = useCommunityMembers(selectedCommunityId || '', { page_size: 50 });
  const createOrJoinMutation = useCreateOrJoinCommunity();

  const handleCreateCommunity = async () => {
    if (!communityName.trim()) return;

    try {
      await createOrJoinMutation.mutateAsync({
        name: communityName,
        description: communityDescription || undefined,
        is_public: isPublic,
      });
      setCommunityName('');
      setCommunityDescription('');
      setIsPublic(true);
      setShowForm(false);
      refetch();
    } catch {
      // Error handled by mutation
    }
  };

  const handleJoinCommunity = async (communityId: string) => {
    try {
      await createOrJoinMutation.mutateAsync({
        community_id: communityId,
      });
      refetch();
    } catch {
      // Error handled by mutation
    }
  };

  if (isLoading) {
    return <LoadingSpinner message="Loading communities..." />;
  }

  if (error) {
    return <ErrorDisplay error={error} title="Failed to load communities" onRetry={() => refetch()} />;
  }

  const communities = communitiesData?.results || [];

  return (
    <div className="communities-tab">
      <div className="communities-tab-header">
        <h2>Data Communities</h2>
        {!showForm && (
          <Button
 variant="primary"
 onClick={() => setShowForm(true)}>
            Create Community
          </Button>
        )}
      </div>

      {showForm && (
        <div className="community-form">
          <h3>Create Community</h3>
          <div className="form-group">
            <label htmlFor="community-name">Name *</label>
            <input
              id="community-name"
              type="text"
              value={communityName}
              onChange={(e) => setCommunityName(e.target.value)}
              placeholder="Community name (3-100 characters)"
              minLength={3}
              maxLength={100}
              required
            />
          </div>
          <div className="form-group">
            <label htmlFor="community-description">Description</label>
            <textarea
              id="community-description"
              value={communityDescription}
              onChange={(e) => setCommunityDescription(e.target.value)}
              placeholder="Community description (optional)"
              maxLength={500}
              rows={3}
            />
          </div>
          <div className="form-group">
            <label className="checkbox-label">
              <input
                type="checkbox"
                checked={isPublic}
                onChange={(e) => setIsPublic(e.target.checked)}
              />
              Public community (visible to everyone)
            </label>
          </div>
          <div className="form-actions">
            <Button
 variant="primary"
 onClick={handleCreateCommunity}
 disabled={communityName.length < 3 || createOrJoinMutation.isPending}>
              {createOrJoinMutation.isPending ? 'Creating...' : 'Create Community'}
            </Button>
            <Button
 variant="secondary"
 onClick={() => {
 setShowForm(false);
 setCommunityName('');
 setCommunityDescription('');
 setIsPublic(true);
 }}>
              Cancel
            </Button>
          </div>
        </div>
      )}

      {communities.length === 0 ? (
        <EmptyState
          title="No communities yet"
          message="Create the first data community to start collaborating!"
        />
      ) : (
        <div className="communities-list">
          {communities.map(community => (
            <div
              key={community.id}
              className="community-item"
              onClick={() => setSelectedCommunityId(
                selectedCommunityId === community.id ? null : community.id
              )}
            >
              <div className="community-header">
                <div className="community-info">
                  <h3>{community.name}</h3>
                  <div className="community-meta">
                    <span className={`visibility-badge ${community.is_public ? 'public' : 'private'}`}>
                      {community.is_public ? 'Public' : 'Private'}
                    </span>
                    <span className="member-count">
                      {community.member_count} {community.member_count === 1 ? 'member' : 'members'}
                    </span>
                  </div>
                </div>
                <Button
 variant="secondary"
 onClick={(e) => {
 e.stopPropagation();
 handleJoinCommunity(community.id);
 }}>
                  Join
                </Button>
              </div>
              {community.description && (
                <p className="community-description">{community.description}</p>
              )}
              {selectedCommunityId === community.id && membersData && (
                <div className="community-members">
                  <h4>Members ({membersData.results.length})</h4>
                  <div className="members-list">
                    {membersData.results.map(member => (
                      <div key={member.id} className="member-item">
                        <span>User {member.user_id.substring(0, 8)}...</span>
                        <span className="joined-date">
                          Joined {new Date(member.joined_at).toLocaleDateString()}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

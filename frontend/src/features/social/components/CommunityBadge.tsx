/**
 * 285.5.3.F1 — CommunityBadge component.
 *
 * Displays discussion count and community rating on asset detail pages.
 * States: loading (skeleton), error (inline), empty (hidden), normal (badge).
 */
import React, { useEffect, useState } from 'react';
import { apiClient } from '../../../shared/api/client';

interface CommunityStats {
  discussion_count: number;
  rating_avg: number;
  rating_count: number;
}

interface CommunityBadgeProps {
  assetId: string;
}

export const CommunityBadge: React.FC<CommunityBadgeProps> = ({ assetId }) => {
  const [stats, setStats] = useState<CommunityStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(false);
    apiClient
      .getClient()
      .get<CommunityStats>(`/api/v1/social/assets/${assetId}/stats/`)
      .then((resp) => {
        if (cancelled) return;
        setStats(resp.data);
      })
      .catch(() => {
        if (cancelled) return;
        setError(true);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [assetId]);

  if (loading) {
    return (
      <span className="community-badge community-badge--loading" data-testid="community-badge-loading" aria-busy="true">
        Loading community stats…
      </span>
    );
  }

  if (error) {
    return (
      <span className="community-badge community-badge--error" data-testid="community-badge-error" role="alert">
        Community stats unavailable
      </span>
    );
  }

  if (!stats || stats.discussion_count === 0) {
    return null; // empty state: hide badge when no discussions
  }

  const stars = '★'.repeat(Math.round(stats.rating_avg));
  return (
    <span className="community-badge" data-testid="community-badge" title={`${stats.rating_count} ratings`}>
      <span className="community-badge-discussions">💬 {stats.discussion_count}</span>
      <span className="community-badge-rating">{stars} {stats.rating_avg.toFixed(1)}</span>
    </span>
  );
};

export default CommunityBadge;

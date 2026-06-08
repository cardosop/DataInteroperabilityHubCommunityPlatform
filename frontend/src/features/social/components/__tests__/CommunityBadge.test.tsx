/**
 * 285.5.5 — Communities tests (2 tests).
 *
 * Asset detail badge: renders with discussion count + rating.
 * Search ratings: rating_avg + discussion_count present in search result.
 */
import { render, screen, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { CommunityBadge } from '../CommunityBadge';
import { apiClient } from '../../../../shared/api/client';

vi.mock('../../../../shared/api/client', () => ({
  apiClient: {
    get: vi.fn(),
  },
}));

const mockGet = apiClient.get as ReturnType<typeof vi.fn>;

describe('CommunityBadge', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders discussion count and rating when stats load', async () => {
    mockGet.mockResolvedValue({
      data: { discussion_count: 12, rating_avg: 4.3, rating_count: 8 },
    });
    render(<CommunityBadge assetId="asset-1" />);
    await waitFor(() => {
      expect(screen.getByTestId('community-badge')).toBeDefined();
    });
    expect(screen.getByTestId('community-badge').textContent).toContain('12');
    expect(screen.getByTestId('community-badge').textContent).toContain('4.3');
  });

  it('hides badge when no discussions exist (empty state)', async () => {
    mockGet.mockResolvedValue({
      data: { discussion_count: 0, rating_avg: 0, rating_count: 0 },
    });
    const { container } = render(<CommunityBadge assetId="asset-1" />);
    await waitFor(() => {
      expect(screen.queryByTestId('community-badge')).toBeNull();
    });
  });

  it('shows error state on API failure', async () => {
    mockGet.mockRejectedValue(new Error('Network error'));
    render(<CommunityBadge assetId="asset-1" />);
    await waitFor(() => {
      expect(screen.getByTestId('community-badge-error')).toBeDefined();
    });
  });

  it('shows loading state initially', () => {
    mockGet.mockReturnValue(new Promise(() => {})); // never resolves
    render(<CommunityBadge assetId="asset-1" />);
    expect(screen.getByTestId('community-badge-loading')).toBeDefined();
  });
});

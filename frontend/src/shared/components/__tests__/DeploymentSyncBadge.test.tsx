/**
 * DeploymentSyncBadge Component Tests — Phase 25.19
 */

import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { DeploymentSyncBadge } from '../DeploymentSyncBadge';

describe('DeploymentSyncBadge', () => {
  it('renders nothing when status is SYNCED', () => {
    const { container } = render(<DeploymentSyncBadge status="SYNCED" />);
    expect(container.innerHTML).toBe('');
  });

  it('renders nothing when status is null', () => {
    const { container } = render(<DeploymentSyncBadge status={null} />);
    expect(container.innerHTML).toBe('');
  });

  it('renders nothing when status is undefined', () => {
    const { container } = render(<DeploymentSyncBadge status={undefined} />);
    expect(container.innerHTML).toBe('');
  });

  it('renders yellow badge with "Schedule not synced" when FAILED', () => {
    render(<DeploymentSyncBadge status="FAILED" />);
    const badge = screen.getByText('Schedule not synced');
    expect(badge).toBeInTheDocument();
    expect(badge).toHaveClass('deployment-sync-badge', 'failed');
  });

  it('renders grey badge with "Sync pending" when PENDING', () => {
    render(<DeploymentSyncBadge status="PENDING" />);
    const badge = screen.getByText('Sync pending');
    expect(badge).toBeInTheDocument();
    expect(badge).toHaveClass('deployment-sync-badge', 'pending');
  });

  it('does not render retry button when onRetrySync is not provided', () => {
    render(<DeploymentSyncBadge status="FAILED" />);
    expect(screen.queryByTestId('deployment-sync-retry-btn')).not.toBeInTheDocument();
  });

  it('renders retry button when onRetrySync is provided', () => {
    render(<DeploymentSyncBadge status="FAILED" onRetrySync={() => {}} />);
    expect(screen.getByTestId('deployment-sync-retry-btn')).toBeInTheDocument();
    expect(screen.getByText('Retry sync')).toBeInTheDocument();
  });

  it('calls onRetrySync when retry button is clicked', async () => {
    const onRetrySync = vi.fn();
    const user = userEvent.setup();
    render(<DeploymentSyncBadge status="FAILED" onRetrySync={onRetrySync} />);
    await user.click(screen.getByTestId('deployment-sync-retry-btn'));
    expect(onRetrySync).toHaveBeenCalledTimes(1);
  });

  it('stops event propagation on retry click (no row navigation)', async () => {
    const onRetrySync = vi.fn();
    const onRowClick = vi.fn();
    const user = userEvent.setup();
    render(
      <div onClick={onRowClick}>
        <DeploymentSyncBadge status="FAILED" onRetrySync={onRetrySync} />
      </div>
    );
    await user.click(screen.getByTestId('deployment-sync-retry-btn'));
    expect(onRetrySync).toHaveBeenCalledTimes(1);
    expect(onRowClick).not.toHaveBeenCalled();
  });

  it('shows spinner and disables button when isSyncing is true', () => {
    render(
      <DeploymentSyncBadge status="FAILED" onRetrySync={() => {}} isSyncing />
    );
    const btn = screen.getByTestId('deployment-sync-retry-btn');
    expect(btn).toBeDisabled();
    expect(screen.getByText('Syncing...')).toBeInTheDocument();
    expect(btn.querySelector('.deployment-sync-spinner')).toBeInTheDocument();
  });

  it('renders retry button for PENDING status too', () => {
    render(<DeploymentSyncBadge status="PENDING" onRetrySync={() => {}} />);
    expect(screen.getByText('Sync pending')).toBeInTheDocument();
    expect(screen.getByText('Retry sync')).toBeInTheDocument();
  });

  it('has correct data-testid on wrapper', () => {
    render(<DeploymentSyncBadge status="FAILED" />);
    expect(screen.getByTestId('deployment-sync-badge')).toBeInTheDocument();
  });
});

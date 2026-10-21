/**
 * ActivityTimeline tests — Phase 224.3.3
 * Drives component shape via TDD. The hook is mocked; the underlying network
 * and serializer behavior are covered server-side.
 */

import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { ResourceActivityEvent } from '../types/audit';

vi.mock('../../features/audit/hooks/useAudit', () => ({
  useResourceActivity: vi.fn(),
}));

import { useResourceActivity } from '../../features/audit/hooks/useAudit';
import { ActivityTimeline } from './ActivityTimeline';

const mockHook = vi.mocked(useResourceActivity);

function event(overrides: Partial<ResourceActivityEvent> = {}): ResourceActivityEvent {
  return {
    id: overrides.id ?? 'e1',
    action: 'CREATED',
    result: 'SUCCESS',
    timestamp: '2026-04-15T12:00:00Z',
    resource_type: 'ASSET',
    resource_id: 'r1',
    actor_display_name: 'Alice',
    details: {},
    ...overrides,
  };
}

function renderTimeline() {
  return render(
    <MemoryRouter>
      <ActivityTimeline resourceType="ASSET" resourceId="r1" />
    </MemoryRouter>,
  );
}

describe('ActivityTimeline', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('shows a loading indicator while the feed is fetching', () => {
    mockHook.mockReturnValue({ data: undefined, isLoading: true, error: null } as never);
    renderTimeline();
    expect(screen.getByTestId('activity-timeline-loading')).toBeInTheDocument();
  });

  it('shows an empty state when the feed has no events', () => {
    mockHook.mockReturnValue({
      data: { results: [] },
      isLoading: false,
      error: null,
    } as never);
    renderTimeline();
    expect(screen.getByTestId('activity-timeline-empty')).toBeInTheDocument();
  });

  it('renders one entry per event with actor, action, and formatted timestamp', () => {
    mockHook.mockReturnValue({
      data: { results: [event({ id: 'e1', action: 'CREATED', actor_display_name: 'Alice' })] },
      isLoading: false,
      error: null,
    } as never);
    renderTimeline();
    const item = screen.getByTestId('activity-item-e1');
    expect(item).toHaveTextContent('CREATED');
    expect(item).toHaveTextContent('Alice');
    // <time> element used for accessible timestamp rendering
    expect(item.querySelector('time')).toHaveAttribute(
      'datetime',
      '2026-04-15T12:00:00Z',
    );
  });

  it('renders sanitized details as key/value snippet rows', () => {
    mockHook.mockReturnValue({
      data: {
        results: [event({ id: 'e1', details: { name: 'Asset v2', note: 'updated schema' } })],
      },
      isLoading: false,
      error: null,
    } as never);
    renderTimeline();
    const snippet = screen.getByTestId('activity-details-e1');
    expect(snippet).toHaveTextContent('name');
    expect(snippet).toHaveTextContent('Asset v2');
    expect(snippet).toHaveTextContent('note');
    expect(snippet).toHaveTextContent('updated schema');
  });

  it('renders an initials avatar when actor is not System', () => {
    mockHook.mockReturnValue({
      data: { results: [event({ id: 'e1', actor_display_name: 'Alice Baker' })] },
      isLoading: false,
      error: null,
    } as never);
    renderTimeline();
    expect(screen.getByTestId('activity-avatar-e1')).toHaveTextContent('AB');
  });

  it('uses a system marker avatar for system-originated events', () => {
    mockHook.mockReturnValue({
      data: { results: [event({ id: 'e1', actor_display_name: 'System' })] },
      isLoading: false,
      error: null,
    } as never);
    renderTimeline();
    const avatar = screen.getByTestId('activity-avatar-e1');
    expect(avatar).toHaveAttribute('data-system', 'true');
  });

  it('shows an error banner when the feed request fails', () => {
    mockHook.mockReturnValue({
      data: undefined,
      isLoading: false,
      error: new Error('boom'),
    } as never);
    renderTimeline();
    expect(screen.getByTestId('activity-timeline-error')).toBeInTheDocument();
  });

  it('passes resource_type/resource_id through to the hook', () => {
    mockHook.mockReturnValue({
      data: { results: [] },
      isLoading: false,
      error: null,
    } as never);
    renderTimeline();
    expect(mockHook).toHaveBeenCalledWith('ASSET', 'r1');
  });
});

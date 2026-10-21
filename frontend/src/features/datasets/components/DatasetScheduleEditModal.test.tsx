/**
 * DatasetScheduleEditModal tests — Phase 260.4.F.
 *
 * Verifies the modal-level surface contract:
 *   - does NOT render when open=false
 *   - fetches schedules filtered by asset_id (load-bearing query
 *     param; without it the modal would surface ALL tenant
 *     schedules)
 *   - renders the empty-state with a Create deep-link when 0
 *     schedules match
 *   - renders the schedule list with per-row Edit deep-link when
 *     1+ schedules match
 *   - cadence summary surfaces cron / time configuration so the
 *     user can identify schedules without clicking through
 *   - no-asset state shows defensive empty surface (parent page
 *     normally hides the CTA, but the modal renders cleanly if
 *     mounted anyway)
 *
 * Real ``useScheduledIngestionsForAsset`` + React Query — only
 * apiClient is mocked, no business-logic stubbing.
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import { type ReactNode } from 'react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import type { HttpClient } from '../../../shared/types/api';
import { DatasetScheduleEditModal } from './DatasetScheduleEditModal';

vi.mock('../../../shared/api/client');

import { apiClient } from '../../../shared/api/client';

const ASSET_ID = '11111111-1111-1111-1111-111111111111';

describe('DatasetScheduleEditModal (Phase 260.4.F)', () => {
  let queryClient: QueryClient;
  let mockClient: HttpClient;

  function wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>{children}</MemoryRouter>
      </QueryClientProvider>
    );
  }

  beforeEach(() => {
    vi.clearAllMocks();
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
        mutations: { retry: false },
      },
    });
    mockClient = apiClient.getClient();
    vi.mocked(mockClient.get).mockClear();
  });

  it('does not render when open=false', () => {
    render(
      <DatasetScheduleEditModal
        open={false}
        assetId={ASSET_ID}
        datasetName="My Dataset"
        onClose={() => {}}
      />,
      { wrapper },
    );
    expect(screen.queryByTestId('dataset-schedule-modal-body')).toBeNull();
    // No-op API: closed modal shouldn't fetch.
    expect(vi.mocked(mockClient.get)).not.toHaveBeenCalled();
  });

  it('renders no-asset empty state when assetId is null', async () => {
    render(
      <DatasetScheduleEditModal
        open={true}
        assetId={null}
        datasetName="My Dataset"
        onClose={() => {}}
      />,
      { wrapper },
    );
    expect(screen.getByTestId('dataset-schedule-modal-body')).toBeInTheDocument();
    expect(screen.getByTestId('dataset-schedule-no-asset')).toBeInTheDocument();
    // Without an assetId the hook is disabled — no fetch should fire.
    await waitFor(() => {
      expect(vi.mocked(mockClient.get)).not.toHaveBeenCalledWith(
        expect.stringContaining('/scheduled-ingestions/'),
      );
    });
  });

  it('fetches with asset_id filter and shows empty state with Create link when no schedules', async () => {
    vi.mocked(mockClient.get).mockResolvedValue({
      data: { results: [], count: 0, next: null, previous: null },
    } as never);

    render(
      <DatasetScheduleEditModal
        open={true}
        assetId={ASSET_ID}
        datasetName="My Dataset"
        onClose={() => {}}
      />,
      { wrapper },
    );

    // The asset_id query param is the load-bearing surface for the
    // dataset → schedule lookup; without it we'd surface every
    // schedule in the tenant.
    await waitFor(() => {
      expect(vi.mocked(mockClient.get)).toHaveBeenCalledWith(
        expect.stringContaining(`asset_id=${ASSET_ID}`),
      );
    });

    await waitFor(() => {
      expect(screen.getByTestId('dataset-schedule-empty-state')).toBeInTheDocument();
    });
    const createLink = screen.getByTestId('dataset-schedule-create-link');
    expect(createLink).toHaveAttribute(
      'href',
      `/scheduled-ingestions/create?asset_id=${ASSET_ID}`,
    );
  });

  it('renders schedule list with cadence summary + per-row Edit link', async () => {
    vi.mocked(mockClient.get).mockResolvedValue({
      data: {
        results: [
          {
            id: 'si-1',
            name: 'Daily Sales Feed',
            description: '',
            source_type: 'S3',
            source_config: {},
            schedule_type: 'DAILY',
            schedule_config: { time: '02:00' },
            status: 'ACTIVE',
            tenant_id: 't1',
            created_by: 'u1',
            created_at: '2025-01-01T00:00:00Z',
            updated_at: '2025-01-01T00:00:00Z',
            asset: ASSET_ID,
          },
          {
            id: 'si-2',
            name: 'Hourly Backup',
            description: '',
            source_type: 'S3',
            source_config: {},
            schedule_type: 'CUSTOM_CRON',
            schedule_config: { cron: '0 * * * *' },
            status: 'PAUSED',
            tenant_id: 't1',
            created_by: 'u1',
            created_at: '2025-01-01T00:00:00Z',
            updated_at: '2025-01-01T00:00:00Z',
            asset: ASSET_ID,
          },
        ],
        count: 2,
        next: null,
        previous: null,
      },
    } as never);

    render(
      <DatasetScheduleEditModal
        open={true}
        assetId={ASSET_ID}
        datasetName="My Dataset"
        onClose={() => {}}
      />,
      { wrapper },
    );

    await waitFor(() => {
      expect(screen.getByTestId('dataset-schedule-list')).toBeInTheDocument();
    });

    // Both schedules surfaced with their cadence + status.
    expect(screen.getByTestId('dataset-schedule-row-si-1')).toHaveTextContent('Daily Sales Feed');
    expect(screen.getByTestId('dataset-schedule-row-si-1')).toHaveTextContent(/time: 02:00/);
    expect(screen.getByTestId('dataset-schedule-row-si-1')).toHaveTextContent(/ACTIVE/);

    expect(screen.getByTestId('dataset-schedule-row-si-2')).toHaveTextContent('Hourly Backup');
    expect(screen.getByTestId('dataset-schedule-row-si-2')).toHaveTextContent(/cron: 0 \* \* \* \*/);
    expect(screen.getByTestId('dataset-schedule-row-si-2')).toHaveTextContent(/PAUSED/);

    // Per-row Edit link points at the existing scheduled-ingestion
    // edit page — the source of truth, not a duplicated form.
    expect(screen.getByTestId('dataset-schedule-edit-link-si-1')).toHaveAttribute(
      'href',
      '/scheduled-ingestions/si-1/edit',
    );
    expect(screen.getByTestId('dataset-schedule-edit-link-si-2')).toHaveAttribute(
      'href',
      '/scheduled-ingestions/si-2/edit',
    );
  });

  it('shows ErrorDisplay when the fetch fails', async () => {
    vi.mocked(mockClient.get).mockRejectedValue(new Error('Network error'));

    render(
      <DatasetScheduleEditModal
        open={true}
        assetId={ASSET_ID}
        datasetName="My Dataset"
        onClose={() => {}}
      />,
      { wrapper },
    );

    await waitFor(() => {
      expect(screen.getByText(/failed to load schedules/i)).toBeInTheDocument();
    });
  });
});

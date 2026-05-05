/**
 * Phase 250.6.E TDD pin for TenantFeatureFlagsAdminPage.
 *
 * Tests the wire contract end-to-end against a stubbed
 * tenantService (the only mock — the service is the test seam
 * because it abstracts the real fetch / network call). Pins:
 *
 *  1. Renders one row per backend-returned flag with name +
 *     description + toggle in the right state.
 *  2. Toggling a flag fires a PATCH and updates the row state.
 *  3. The audit-log section renders the most-recent events.
 *  4. Loading state during the initial fetch.
 *  5. Error state when the fetch fails.
 *  6. data-testid contract for E2E discoverability.
 */
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi, beforeEach } from 'vitest';

import { TenantFeatureFlagsAdminPage } from './TenantFeatureFlagsAdminPage';
import { tenantService } from '../../tenants/services/tenantService';

vi.mock('../../tenants/services/tenantService', () => ({
  tenantService: {
    getMeFeatureFlags: vi.fn(),
    patchMeFeatureFlags: vi.fn(),
    getMeFeatureFlagHistory: vi.fn(),
  },
}));

const mockedService = vi.mocked(tenantService);

function renderPage() {
  return render(
    <MemoryRouter>
      <TenantFeatureFlagsAdminPage />
    </MemoryRouter>,
  );
}

describe('TenantFeatureFlagsAdminPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders the loading state during initial fetch', async () => {
    mockedService.getMeFeatureFlags.mockReturnValue(
      new Promise(() => {
        // never resolves — pin the loading state
      }),
    );
    mockedService.getMeFeatureFlagHistory.mockResolvedValue({ events: [] });
    renderPage();
    expect(
      screen.getByTestId('tenant-feature-flags-admin-page-loading'),
    ).toBeInTheDocument();
  });

  it('renders one row per flag with name + description + toggle', async () => {
    mockedService.getMeFeatureFlags.mockResolvedValue({
      flags: [
        {
          name: 'asset_creation_enabled',
          value: true,
          description: 'When True (default), this tenant may create assets.',
        },
        {
          name: 'federated_import_enabled',
          value: false,
          description: 'When True, this tenant may import federated assets.',
        },
      ],
    });
    mockedService.getMeFeatureFlagHistory.mockResolvedValue({ events: [] });
    renderPage();
    // Wait for the loading state to clear.
    await waitFor(() =>
      expect(
        screen.getByTestId('tenant-feature-flags-admin-page'),
      ).toBeInTheDocument(),
    );
    // Row + toggle for each flag.
    expect(
      screen.getByTestId('tenant-feature-flag-row-asset_creation_enabled'),
    ).toBeInTheDocument();
    const assetToggle = screen.getByTestId(
      'tenant-feature-flag-toggle-asset_creation_enabled',
    ) as HTMLInputElement;
    expect(assetToggle.checked).toBe(true);
    const fedToggle = screen.getByTestId(
      'tenant-feature-flag-toggle-federated_import_enabled',
    ) as HTMLInputElement;
    expect(fedToggle.checked).toBe(false);
    // Description rendered from backend.
    expect(
      screen.getByText(/When True \(default\), this tenant may create assets/i),
    ).toBeInTheDocument();
  });

  it('PATCHes the backend when a toggle is flipped', async () => {
    mockedService.getMeFeatureFlags.mockResolvedValue({
      flags: [
        {
          name: 'federated_import_enabled',
          value: false,
          description: 'desc',
        },
      ],
    });
    mockedService.getMeFeatureFlagHistory.mockResolvedValue({ events: [] });
    mockedService.patchMeFeatureFlags.mockResolvedValue({
      flags: [
        {
          name: 'federated_import_enabled',
          value: true,
          description: 'desc',
        },
      ],
    });

    renderPage();
    const toggle = await screen.findByTestId(
      'tenant-feature-flag-toggle-federated_import_enabled',
    );
    const user = userEvent.setup();
    await user.click(toggle);

    await waitFor(() =>
      expect(mockedService.patchMeFeatureFlags).toHaveBeenCalledWith({
        federated_import_enabled: true,
      }),
    );
  });

  it('renders the audit-log history section with recent events', async () => {
    mockedService.getMeFeatureFlags.mockResolvedValue({ flags: [] });
    mockedService.getMeFeatureFlagHistory.mockResolvedValue({
      events: [
        {
          id: 'ev-1',
          action: 'TENANT_FEATURE_FLAG_UPDATED',
          actor_user_id: 'aaaaaaaabbbbccccddddeeeeffffffff',
          result: 'SUCCESS',
          created_at: '2026-05-04T10:00:00Z',
          details_json: {
            flag_name: 'federated_import_enabled',
            previous_value: false,
            new_value: true,
          },
        },
      ],
    });

    renderPage();
    await screen.findByTestId('tenant-feature-flag-history');
    expect(screen.getByTestId('history-event-ev-1')).toBeInTheDocument();
    expect(
      screen.getByText(/federated_import_enabled/),
    ).toBeInTheDocument();
  });

  it('shows the empty-state copy when there are no history events', async () => {
    mockedService.getMeFeatureFlags.mockResolvedValue({ flags: [] });
    mockedService.getMeFeatureFlagHistory.mockResolvedValue({ events: [] });
    renderPage();
    await screen.findByTestId('tenant-feature-flag-history');
    expect(
      screen.getByText(/No flag changes recorded yet/i),
    ).toBeInTheDocument();
  });

  it('shows ErrorDisplay when the initial fetch fails', async () => {
    mockedService.getMeFeatureFlags.mockRejectedValue(
      new Error('Network down'),
    );
    mockedService.getMeFeatureFlagHistory.mockResolvedValue({ events: [] });
    renderPage();
    await waitFor(() =>
      expect(
        screen.getByText(/Could not load or save tenant settings/i),
      ).toBeInTheDocument(),
    );
  });
});

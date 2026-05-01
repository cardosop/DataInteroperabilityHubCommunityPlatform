/**
 * Phase 228.F1.18 (REQ-LIN-X-002) — a11y assertions for the
 * cross-tenant lineage panel.
 *
 * The component test exercises the four render paths (loading,
 * error, empty, success) and asserts WCAG 2.1 AA basics:
 *
 * - Section landmark with `aria-label` for screen-reader navigation.
 * - `aria-busy="true"` during loading.
 * - `role="alert"` on error.
 * - `role="status"` on the truncation banner.
 * - All interactive elements (CTA button, retry button) carry an
 *   accessible name.
 *
 * The full axe-core scan is the **follow-up** when @axe-core/react
 * lands as a devDependency — this test scaffolds the assertions
 * the axe scan would also catch, so the test file is the single
 * place where a11y invariants are pinned regardless of which
 * scanner runs.
 */
import type { HttpClient } from '../../../shared/types/api';
import { type ReactNode } from 'react';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../../../shared/api/client');

import { apiClient } from '../../../shared/api/client';
import { ListingLineagePanel } from './ListingLineagePanel';

describe('ListingLineagePanel — a11y + render-state invariants', () => {
  let queryClient: QueryClient;
  let mock: HttpClient;

  function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>{children}</MemoryRouter>
      </QueryClientProvider>
    );
  }

  beforeEach(() => {
    vi.clearAllMocks();
    queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    mock = apiClient.getClient();
  });

  it('renders a labelled section landmark', async () => {
    vi.mocked(mock.get).mockResolvedValue({
      data: { results: [] }, // no entitlement → summary tier
    } as never);
    vi.mocked(mock.get).mockResolvedValueOnce({
      data: { results: [] },
    } as never);
    vi.mocked(mock.get).mockResolvedValueOnce({
      data: {
        nodes: [{ id: 'c1', type: 'contract', label: 'orders' }],
        links: [],
        truncated: false,
        detail: 'summary',
      },
    } as never);

    render(
      <Wrapper>
        <ListingLineagePanel listingId="L1" assetId="A1" />
      </Wrapper>,
    );
    // Section is exposed as a region with an accessible label.
    await waitFor(() => {
      // aria-label is the section's accessible name; fall back to
      // role-based query if testing-library detects it.
      const section = screen.getByLabelText(/data lineage for this listing/i);
      expect(section).toBeTruthy();
    });
  });

  it('marks the loading state with aria-busy', async () => {
    vi.mocked(mock.get).mockImplementation(
      () => new Promise(() => {}), // never resolves
    );
    render(
      <Wrapper>
        <ListingLineagePanel listingId="L1" assetId="A1" />
      </Wrapper>,
    );
    const busy = await screen.findByTestId('listing-lineage-panel-loading');
    expect(busy.getAttribute('aria-busy')).toBe('true');
  });

  it('renders error as an alert with named retry button', async () => {
    // Both queries fail.
    vi.mocked(mock.get).mockRejectedValue(new Error('boom'));
    render(
      <Wrapper>
        <ListingLineagePanel listingId="L1" assetId="A1" />
      </Wrapper>,
    );
    const alert = await screen.findByTestId('listing-lineage-panel-error');
    expect(alert.getAttribute('role')).toBe('alert');
    // The retry button has an accessible name (text content).
    const retry = screen.getByRole('button', { name: /retry/i });
    expect(retry).toBeTruthy();
  });

  it('renders the purchase CTA with a named button on summary tier', async () => {
    // No entitlement.
    vi.mocked(mock.get).mockResolvedValueOnce({
      data: { results: [] },
    } as never);
    // Summary lineage with at least one node + link.
    vi.mocked(mock.get).mockResolvedValueOnce({
      data: {
        nodes: [
          { id: 'c1', type: 'contract', label: 'orders' },
          { id: 'c2', type: 'contract', label: 'customers' },
        ],
        links: [{ source: 'c1', target: 'c2', edge_type: 'reference' }],
        truncated: false,
        detail: 'summary',
      },
    } as never);

    render(
      <Wrapper>
        <ListingLineagePanel listingId="L1" assetId="A1" />
      </Wrapper>,
    );
    const cta = await screen.findByTestId('listing-lineage-purchase-cta');
    expect(cta).toBeTruthy();
    const ctaButton = screen.getByRole('button', { name: /view purchase options/i });
    expect(ctaButton).toBeTruthy();
  });

  it('hides the purchase CTA on full tier (entitled buyer)', async () => {
    // ACTIVE entitlement present.
    vi.mocked(mock.get).mockResolvedValueOnce({
      data: { results: [{ id: 'e1', status: 'ACTIVE', asset: 'A1' }] },
    } as never);
    vi.mocked(mock.get).mockResolvedValueOnce({
      data: {
        nodes: [
          { id: 'c1', type: 'contract', label: 'orders' },
          { id: 'c2', type: 'contract', label: 'customers' },
        ],
        links: [
          {
            source: 'c1',
            target: 'c2',
            edge_type: 'transformation',
            transformation_ref: 'dbt_orders_v1',
            job_ref: 'airflow_run_42',
          },
        ],
        truncated: false,
        detail: 'full',
      },
    } as never);

    render(
      <Wrapper>
        <ListingLineagePanel listingId="L1" assetId="A1" />
      </Wrapper>,
    );
    await screen.findByTestId('listing-lineage-panel');
    expect(screen.queryByTestId('listing-lineage-purchase-cta')).toBeNull();
  });

  it('renders the truncation banner with role=status when truncated=true', async () => {
    vi.mocked(mock.get).mockResolvedValueOnce({
      data: { results: [] },
    } as never);
    vi.mocked(mock.get).mockResolvedValueOnce({
      data: {
        nodes: [
          { id: 'c1', type: 'contract', label: 'orders' },
          { id: 'c2', type: 'contract', label: 'customers' },
        ],
        links: [{ source: 'c1', target: 'c2', edge_type: 'reference' }],
        truncated: true,
        detail: 'summary',
      },
    } as never);

    render(
      <Wrapper>
        <ListingLineagePanel listingId="L1" assetId="A1" />
      </Wrapper>,
    );
    const banner = await screen.findByTestId('listing-lineage-truncated');
    expect(banner.getAttribute('role')).toBe('status');
  });
});

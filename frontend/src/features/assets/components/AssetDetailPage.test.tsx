/**
 * AssetDetailPage smoke test — Phase 106
 */
import type { HttpClient } from '../../../shared/types/api';
import { type ReactNode } from 'react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../../../shared/api/client');

import { apiClient } from '../../../shared/api/client';
import { AssetDetailPage } from './AssetDetailPage';

describe('AssetDetailPage', () => {
  let queryClient: QueryClient;
  let mock: HttpClient;

  function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={['/assets/test-uuid-123']}>
          <Routes>
            <Route path="/assets/:id" element={children} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>
    );
  }

  beforeEach(() => {
    vi.clearAllMocks();
    queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
    });
    mock = apiClient.getClient();
    // Default: return mock detail response for GET by ID.
    // Phase 230.1.6 — payload now includes canonical_iri so the
    // CanonicalIriCard renders.
    vi.mocked(mock.get).mockResolvedValue({
      data: {
        id: 'test-uuid-123',
        name: 'Test Item',
        status: 'ACTIVE',
        // ``visibility`` is required by the component template
        // (``asset.visibility.toLowerCase()`` at line 371) — without
        // it the render throws TypeError BEFORE the
        // CanonicalIriCard renders, masking the actual assertion.
        // The existing smoke tests (``renders without crashing``)
        // pass anyway because they only check
        // ``document.body.innerHTML.length > 0``, which is satisfied
        // by a partial render before the throw.
        visibility: 'PRIVATE',
        created_at: '2026-01-01T00:00:00Z',
        updated_at: '2026-01-01T00:00:00Z',
        canonical_iri: 'https://meshant-internal.example.com/id/asset/test-uuid-123',
      },
    });
  });

  it('renders without crashing', async () => {
    render(<AssetDetailPage />, { wrapper: Wrapper });
    expect(document.body.innerHTML.length).toBeGreaterThan(0);
  });

  it('mounts and processes initial render cycle', async () => {
    const { container } = render(<AssetDetailPage />, { wrapper: Wrapper });
    // Component should mount and start its render lifecycle
    // (loading state, data fetch, or static content)
    expect(container.children.length).toBeGreaterThan(0);
  });

  it('renders CanonicalIriCard when canonical_iri is present (Phase 230.1.6)', async () => {
    render(<AssetDetailPage />, { wrapper: Wrapper });
    await waitFor(() => {
      expect(screen.getByTestId('canonical-iri-card')).toBeInTheDocument();
    });
    expect(screen.getByTestId('canonical-iri-value')).toHaveTextContent(
      'https://meshant-internal.example.com/id/asset/test-uuid-123',
    );
  });

  it('does NOT render CanonicalIriCard when canonical_iri is absent', async () => {
    vi.mocked(mock.get).mockResolvedValue({
      data: {
        id: 'test-uuid-123',
        name: 'Test Item',
        status: 'ACTIVE',
        visibility: 'PRIVATE',
        created_at: '2026-01-01T00:00:00Z',
        updated_at: '2026-01-01T00:00:00Z',
        // canonical_iri intentionally omitted.
      },
    });
    render(<AssetDetailPage />, { wrapper: Wrapper });
    await waitFor(() => {
      // Detail page mounts (the asset name appears) but the card
      // does NOT.
      expect(screen.queryByText('Test Item')).toBeInTheDocument();
    });
    expect(screen.queryByTestId('canonical-iri-card')).not.toBeInTheDocument();
  });
});

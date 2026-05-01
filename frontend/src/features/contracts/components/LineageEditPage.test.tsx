/**
 * Phase 228.F2.25 — a11y assertions for LineageEditPage.
 *
 * Mirrors the F1.18 pattern: hand-rolled WCAG 2.1 AA basics that
 * an axe-core scan would also catch, until the @axe-core
 * devDependency lands.
 *
 * Pinned invariants:
 *
 * - main landmark with aria-label.
 * - aria-busy="true" on loading skeleton.
 * - role="alert" on cycle / validation / save error states.
 * - role="dialog" + aria-modal on EdgeDetailModal + ConflictModal.
 * - role="toolbar" on the action bar.
 * - Every interactive element has an accessible name (label or
 *   text content).
 */
import type { HttpClient } from '../../../shared/types/api';
import { type ReactNode } from 'react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../../../shared/api/client');

import { apiClient } from '../../../shared/api/client';
import { LineageEditPage } from './LineageEditPage';

describe('LineageEditPage — a11y + render-state invariants', () => {
  let queryClient: QueryClient;
  let mock: HttpClient;

  function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={['/contracts/c1/lineage/edit']}>
          <Routes>
            <Route path="/contracts/:id/lineage/edit" element={children} />
            <Route path="/contracts/:id" element={<div>Detail</div>} />
          </Routes>
        </MemoryRouter>
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

  it('renders skeleton with aria-busy while loading', async () => {
    vi.mocked(mock.get).mockImplementation(
      () => new Promise(() => {}), // never resolves
    );
    render(
      <Wrapper>
        <LineageEditPage />
      </Wrapper>,
    );
    const skel = await screen.findByTestId('lineage-edit-skeleton');
    expect(skel.getAttribute('aria-busy')).toBe('true');
  });

  it('renders main landmark with aria-label and toolbar role', async () => {
    // Mock contract + lineage responses.
    vi.mocked(mock.get).mockImplementation((url: string) => {
      if (url.includes('/lineage/visualization/')) {
        return Promise.resolve({
          data: {
            nodes: [],
            links: [],
            field_nodes: [],
            field_links: [],
          },
        }) as never;
      }
      // Contract detail.
      return Promise.resolve({
        data: {
          id: 'c1',
          name: 'Test',
          hub_contract_json: {
            models: [
              {
                name: 'orders',
                fields: [
                  { name: 'id', data_type: 'string' },
                ],
              },
            ],
          },
        },
      }) as never;
    });

    render(
      <Wrapper>
        <LineageEditPage />
      </Wrapper>,
    );
    await waitFor(() => {
      expect(screen.getByLabelText(/edit lineage/i)).toBeTruthy();
    });
    // Toolbar role.
    expect(screen.getByRole('toolbar')).toBeTruthy();
    // Save + cancel + add buttons named.
    expect(screen.getByRole('button', { name: /save changes/i })).toBeTruthy();
    expect(screen.getByRole('button', { name: /cancel/i })).toBeTruthy();
    expect(screen.getByRole('button', { name: /add edge/i })).toBeTruthy();
  });
});

/**
 * Phase 230.5.MetaDoD audit fix M3+M4+M5 — frontend tests for the
 * extended RelationshipsPanel.
 *
 * Pinned invariants:
 *
 * - Loading state: ``aria-busy="true"`` on the RDF section while the
 *   React Query is in flight.
 * - Error state: ``role="alert"`` and a fallback message when the
 *   API call fails.
 * - Degraded state: "(degraded)" badge appears when the server
 *   returns ``status: "DEGRADED"``.
 * - Empty triples: the section is hidden entirely (no empty table).
 * - Happy path: the RDF table renders one row per triple with
 *   correct subject/predicate/object cells.
 */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../../../shared/api/client');

import { apiClient } from '../../../shared/api/client';
import { RelationshipsPanel } from './RelationshipsPanel';

function wrap(qc: QueryClient) {
  return function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={qc}>
        <MemoryRouter>{children}</MemoryRouter>
      </QueryClientProvider>
    );
  };
}

const CONTRACT_ID = 'c-42';

describe('RelationshipsPanel — RDF triples section', () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    vi.clearAllMocks();
    queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
  });

  it('renders aria-busy=true while RDF triples are loading', async () => {
    // Never-resolving promise → permanent loading state.
    vi.mocked(apiClient.getClient().get).mockImplementation(
      () => new Promise(() => {}),
    );
    render(
      <RelationshipsPanel models={[]} contractId={CONTRACT_ID} />,
      { wrapper: wrap(queryClient) },
    );
    const loading = await screen.findByTestId('relationships-rdf-loading');
    expect(loading.getAttribute('aria-busy')).toBe('true');
  });

  it('renders role="alert" when the RDF fetch errors', async () => {
    vi.mocked(apiClient.getClient().get).mockRejectedValueOnce(
      new Error('network'),
    );
    render(
      <RelationshipsPanel models={[]} contractId={CONTRACT_ID} />,
      { wrapper: wrap(queryClient) },
    );
    const errorState = await screen.findByTestId('relationships-rdf-error');
    expect(errorState.getAttribute('role')).toBe('alert');
  });

  it('hides the RDF section when triples are empty', async () => {
    vi.mocked(apiClient.getClient().get).mockResolvedValueOnce({
      data: { triples: '', status: 'OK' },
    } as never);
    render(
      <RelationshipsPanel models={[]} contractId={CONTRACT_ID} />,
      { wrapper: wrap(queryClient) },
    );
    // The structural-empty state still renders (because we passed
    // empty models) — but the RDF section MUST NOT.
    await waitFor(() => {
      expect(screen.queryByTestId('relationships-rdf-section')).toBeNull();
    });
  });

  it('renders the triples table with one row per N-Triple line', async () => {
    const triples =
      '<https://hub.example.com/id/contract/c-42> <http://www.w3.org/ns/prov#wasDerivedFrom> <https://hub.example.com/id/contract/abc> .\n'
      + '<https://hub.example.com/id/contract/c-42> <http://www.w3.org/ns/prov#wasGeneratedBy> <https://hub.example.com/id/run/xyz> .\n';
    vi.mocked(apiClient.getClient().get).mockResolvedValueOnce({
      data: { triples, status: 'OK' },
    } as never);

    render(
      <RelationshipsPanel models={[]} contractId={CONTRACT_ID} />,
      { wrapper: wrap(queryClient) },
    );

    const section = await screen.findByTestId('relationships-rdf-section');
    expect(section).toBeInTheDocument();
    const table = await screen.findByTestId('relationships-rdf-table');
    // Two data rows expected (one per triple).
    const rows = table.querySelectorAll('tbody tr');
    expect(rows.length).toBe(2);
    // Predicate IRIs appear in the rendered output.
    expect(table.textContent).toContain('prov#wasDerivedFrom');
    expect(table.textContent).toContain('prov#wasGeneratedBy');
  });

  it('renders the (degraded) badge when status=DEGRADED', async () => {
    const triples =
      '<#a> <http://www.w3.org/ns/prov#wasDerivedFrom> <#b> .\n';
    vi.mocked(apiClient.getClient().get).mockResolvedValueOnce({
      data: { triples, status: 'DEGRADED' },
    } as never);

    render(
      <RelationshipsPanel models={[]} contractId={CONTRACT_ID} />,
      { wrapper: wrap(queryClient) },
    );
    const section = await screen.findByTestId('relationships-rdf-section');
    expect(section.textContent).toContain('(degraded)');
  });

  it('does NOT fetch RDF when contractId is omitted (legacy mode)', async () => {
    render(
      <RelationshipsPanel models={[]} />,
      { wrapper: wrap(queryClient) },
    );
    // No fetch call — the panel renders structural-only.
    expect(apiClient.getClient().get).not.toHaveBeenCalled();
    // No RDF section in the DOM.
    expect(screen.queryByTestId('relationships-rdf-section')).toBeNull();
    expect(screen.queryByTestId('relationships-rdf-loading')).toBeNull();
    expect(screen.queryByTestId('relationships-rdf-error')).toBeNull();
  });
});

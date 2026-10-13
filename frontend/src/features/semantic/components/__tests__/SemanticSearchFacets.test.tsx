/**
 * 284.D.2 — Unit tests for SemanticSearchFacets.
 *
 * Covers: render, filter interaction, loading, empty, error states,
 * SPARQL timeout + retry.
 */
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { describe, it, expect, vi, beforeEach } from 'vitest';
// The component uses react-i18next's useTranslation directly, which
// warns (NO_I18NEXT_INSTANCE) when no instance is reachable. Provide
// the app's shared instance so tests mirror the real I18nextProvider
// mounted at the app root.
import { I18nextProvider } from 'react-i18next';
import instance from '../../../../shared/i18n/instance';
import { SemanticSearchFacets } from '../SemanticSearchFacets';


// The component is gated behind CapabilityRoute("semantic_search"); make
// the capability available in tests (canonical pattern from
// CapabilityRoute.test.tsx) and wrap renders in a Router (CapabilityRoute
// renders <Navigate> otherwise — it may only be used inside a Router).
vi.mock('../../../../shared/hooks/useCapabilities', () => ({
  useCapabilities: () => ({
    capabilities: { semantic_search: { available: true } },
    isLoading: false,
    isCapabilityAvailable: (key: string) => key === 'semantic_search',
    getCapability: () => null,
  }),
}));

function renderFacets(props: Partial<typeof defaultProps> = {}) {
  return render(
    <I18nextProvider i18n={instance}>
      <MemoryRouter>
        <SemanticSearchFacets {...defaultProps} {...props} />
      </MemoryRouter>
    </I18nextProvider>
  );
}

const apiMocks = vi.hoisted(() => ({ get: vi.fn() }));

vi.mock('../../../../shared/api/client', () => ({
  apiClient: {
    // Stable get fn across every getClient() call — the component calls
    // getClient() per render, so a per-call fresh vi.fn() never sees the
    // test's mockResolvedValue (measured 2026-08-28).
    getClient: () => ({ get: apiMocks.get }),
  },
}));

const mockGet = apiMocks.get;

const defaultProps = {
  query: 'test query',
  selectedOntologyType: '',
  selectedRdfClass: '',
  onOntologyTypeChange: vi.fn(),
  onRdfClassChange: vi.fn(),
};

describe('SemanticSearchFacets', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders loading state initially', () => {
    mockGet.mockReturnValue(new Promise(() => {})); // never resolves
    renderFacets();
    expect(screen.getByTestId('semantic-search-facets')).toBeDefined();
  });

  it('renders empty state when no facets returned', async () => {
    mockGet.mockResolvedValue({ data: { facets: [] } });
    renderFacets();
    await waitFor(() => {
      expect(screen.getByTestId('facets-empty')).toBeDefined();
    });
  });

  it('renders ontology type facets', async () => {
    mockGet.mockResolvedValue({
      data: {
        facets: [
          {
            id: 'ontology_type',
            label: 'Ontology Type',
            items: [
              { value: 'dcat:Dataset', label: 'Dataset', count: 42 },
              { value: 'foaf:Document', label: 'Document', count: 17 },
            ],
          },
        ],
      },
    });
    renderFacets();
    await waitFor(() => {
      expect(screen.getByTestId('facet-ontology-type')).toBeDefined();
    });
    expect(screen.getByTestId('facet-ontology-type-dcat:Dataset')).toBeDefined();
  });

  it('renders RDF class facets', async () => {
    mockGet.mockResolvedValue({
      data: {
        facets: [
          {
            id: 'rdf_class',
            label: 'RDF Class',
            items: [
              { value: 'owl:Thing', label: 'Thing', count: 100 },
              { value: 'schema:CreativeWork', label: 'Creative Work', count: 33 },
            ],
          },
        ],
      },
    });
    renderFacets();
    await waitFor(() => {
      expect(screen.getByTestId('facet-rdf-class')).toBeDefined();
    });
  });

  it('highlights active filter and allows toggle off', async () => {
    const onTypeChange = vi.fn();
    mockGet.mockResolvedValue({
      data: {
        facets: [
          {
            id: 'ontology_type',
            label: 'Ontology Type',
            items: [{ value: 'dcat:Dataset', label: 'Dataset', count: 10 }],
          },
        ],
      },
    });
    render(
      <I18nextProvider i18n={instance}>
        <SemanticSearchFacets
          {...defaultProps}
          selectedOntologyType="dcat:Dataset"
          onOntologyTypeChange={onTypeChange}
        />
      </I18nextProvider>
    );
    await waitFor(() => {
      expect(screen.getByTestId('facet-ontology-type-dcat:Dataset')).toBeDefined();
    });

    const btn = screen.getByTestId('facet-ontology-type-dcat:Dataset');
    await userEvent.click(btn);
    expect(onTypeChange).toHaveBeenCalledWith('');
  });

  it('shows SPARQL timeout error with retry button', async () => {
    mockGet.mockRejectedValue({ status: 504 });
    renderFacets();
    await waitFor(() => {
      expect(screen.getByTestId('facets-error')).toBeDefined();
    });
    expect(screen.getByTestId('facets-retry-btn')).toBeDefined();
  });

  it('retries on retry button click after error', async () => {
    mockGet.mockRejectedValueOnce({ status: 504 });
    mockGet.mockResolvedValueOnce({ data: { facets: [] } });
    renderFacets();
    await waitFor(() => {
      expect(screen.getByTestId('facets-retry-btn')).toBeDefined();
    });

    await userEvent.click(screen.getByTestId('facets-retry-btn'));
    expect(mockGet).toHaveBeenCalledTimes(2);
  });

  it('does not fetch when query is empty', () => {
    mockGet.mockResolvedValue({ data: { facets: [] } });
    render(
      <I18nextProvider i18n={instance}>
        <SemanticSearchFacets {...defaultProps} query="" />
      </I18nextProvider>
    );
    expect(mockGet).not.toHaveBeenCalled();
  });
});

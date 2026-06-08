/**
 * 284.D.2 — Unit tests for SemanticSearchFacets.
 *
 * Covers: render, filter interaction, loading, empty, error states,
 * SPARQL timeout + retry.
 */
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { SemanticSearchFacets } from '../SemanticSearchFacets';
import { apiClient } from '../../../../shared/api/client';

vi.mock('../../../../shared/api/client', () => ({
  apiClient: {
    get: vi.fn(),
  },
}));

const mockGet = apiClient.get as ReturnType<typeof vi.fn>;

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
    render(<SemanticSearchFacets {...defaultProps} />);
    expect(screen.getByTestId('semantic-search-facets')).toBeDefined();
  });

  it('renders empty state when no facets returned', async () => {
    mockGet.mockResolvedValue({ data: { facets: [] } });
    render(<SemanticSearchFacets {...defaultProps} />);
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
    render(<SemanticSearchFacets {...defaultProps} />);
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
    render(<SemanticSearchFacets {...defaultProps} />);
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
      <SemanticSearchFacets
        {...defaultProps}
        selectedOntologyType="dcat:Dataset"
        onOntologyTypeChange={onTypeChange}
      />
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
    render(<SemanticSearchFacets {...defaultProps} />);
    await waitFor(() => {
      expect(screen.getByTestId('facets-error')).toBeDefined();
    });
    expect(screen.getByTestId('facets-retry-btn')).toBeDefined();
  });

  it('retries on retry button click after error', async () => {
    mockGet.mockRejectedValueOnce({ status: 504 });
    mockGet.mockResolvedValueOnce({ data: { facets: [] } });
    render(<SemanticSearchFacets {...defaultProps} />);
    await waitFor(() => {
      expect(screen.getByTestId('facets-retry-btn')).toBeDefined();
    });

    await userEvent.click(screen.getByTestId('facets-retry-btn'));
    expect(mockGet).toHaveBeenCalledTimes(2);
  });

  it('does not fetch when query is empty', () => {
    mockGet.mockResolvedValue({ data: { facets: [] } });
    render(<SemanticSearchFacets {...defaultProps} query="" />);
    expect(mockGet).not.toHaveBeenCalled();
  });
});

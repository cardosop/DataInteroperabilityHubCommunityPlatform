/**
 * 284.D.1 — SemanticSearchFacets.
 *
 * Ontology type filter, RDF class faceting, and result count per facet.
 * Shown when ``semantic_search_enabled`` and the user toggles
 * ontology-aware search. Gated behind ``CapabilityRoute capability="semantic_search"``.
 *
 * Handles SPARQL timeout (HTTP 504 / 429) with a retry button.
 */
import { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { apiClient } from '../../../shared/api/client';
import { CapabilityRoute } from '../../../shared/components/CapabilityRoute';
import { LoadingSpinner } from '../../../shared/components/LoadingSpinner';

interface FacetItem {
  value: string;
  label: string;
  count: number;
}

interface FacetGroup {
  id: string;
  label: string;
  items: FacetItem[];
}

interface SemanticSearchFacetsProps {
  query: string;
  selectedOntologyType: string;
  selectedRdfClass: string;
  onOntologyTypeChange: (value: string) => void;
  onRdfClassChange: (value: string) => void;
}

export function SemanticSearchFacets({
  query,
  selectedOntologyType,
  selectedRdfClass,
  onOntologyTypeChange,
  onRdfClassChange,
}: SemanticSearchFacetsProps) {
  const { t } = useTranslation();
  const [facetGroups, setFacetGroups] = useState<FacetGroup[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchFacets = useCallback(async () => {
    if (!query.trim()) {
      setFacetGroups([]);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const resp = await apiClient.getClient().get<{ facets: FacetGroup[] }>(
        '/api/v1/semantic/search-facets/',
        { params: { q: query } }
      );
      setFacetGroups(resp.data.facets || []);
    } catch (err: unknown) {
      const status = (err as { status?: number })?.status;
      if (status === 504 || status === 429) {
        setError(t('semanticSearch.errors.timeout', 'SPARQL query timed out. Try a more specific search or retry.'));
      } else {
        setError(t('semanticSearch.errors.facetsFailed', 'Failed to load semantic facets.'));
      }
    } finally {
      setLoading(false);
    }
  }, [query]);

  useEffect(() => {
    fetchFacets();
  }, [fetchFacets]);

  const ontologyTypes = facetGroups.find((g) => g.id === 'ontology_type')?.items || [];
  const rdfClasses = facetGroups.find((g) => g.id === 'rdf_class')?.items || [];

  return (
    <CapabilityRoute capability="semantic_search">
      <div className="semantic-search-facets" data-testid="semantic-search-facets">
        {loading && <LoadingSpinner message={t('semanticSearch.loadingFacets', 'Loading facets…')} />}

        {error && (
          <div className="semantic-facets-error" role="alert" data-testid="facets-error">
            <span>{error}</span>
            <button
              type="button"
              onClick={fetchFacets}
              data-testid="facets-retry-btn"
              className="semantic-facets-retry-btn"
            >
              {t('semanticSearch.retry', 'Retry')}
            </button>
          </div>
        )}

        {!loading && !error && facetGroups.length === 0 && query.trim() && (
          <div className="semantic-facets-empty" data-testid="facets-empty">
            {t('semanticSearch.noFacets', 'No semantic facets available for this query.')}
          </div>
        )}

        {/* Ontology Type filter */}
        {ontologyTypes.length > 0 && (
          <div className="facet-group" data-testid="facet-ontology-type">
            <h3 className="facet-group-label">{t('semanticSearch.ontologyType', 'Ontology Type')}</h3>
            <ul className="facet-list" role="listbox" aria-label={t('semanticSearch.filterByOntologyType', 'Filter by ontology type')}>
              <li key="all" className={`facet-item ${selectedOntologyType === '' ? 'facet-item--active' : ''}`}>
                <button
                  type="button"
                  role="option"
                  aria-selected={selectedOntologyType === ''}
                  onClick={() => onOntologyTypeChange('')}
                  data-testid="facet-ontology-type-all"
                >
                  {t('semanticSearch.allTypes', 'All types')}
                  <span className="facet-count">
                    {ontologyTypes.reduce((sum, f) => sum + f.count, 0)}
                  </span>
                </button>
              </li>
              {ontologyTypes.map((facet) => (
                <li
                  key={facet.value}
                  className={`facet-item ${selectedOntologyType === facet.value ? 'facet-item--active' : ''}`}
                >
                  <button
                    type="button"
                    role="option"
                    aria-selected={selectedOntologyType === facet.value}
                    onClick={() =>
                      onOntologyTypeChange(selectedOntologyType === facet.value ? '' : facet.value)
                    }
                    data-testid={`facet-ontology-type-${facet.value}`}
                  >
                    {facet.label}
                    <span className="facet-count">{facet.count}</span>
                  </button>
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* RDF Class faceting */}
        {rdfClasses.length > 0 && (
          <div className="facet-group" data-testid="facet-rdf-class">
            <h3 className="facet-group-label">{t('semanticSearch.rdfClass', 'RDF Class')}</h3>
            <ul className="facet-list" role="listbox" aria-label={t('semanticSearch.filterByRdfClass', 'Filter by RDF class')}>
              <li key="all" className={`facet-item ${selectedRdfClass === '' ? 'facet-item--active' : ''}`}>
                <button
                  type="button"
                  role="option"
                  aria-selected={selectedRdfClass === ''}
                  onClick={() => onRdfClassChange('')}
                  data-testid="facet-rdf-class-all"
                >
                  {t('semanticSearch.allClasses', 'All classes')}
                  <span className="facet-count">
                    {rdfClasses.reduce((sum, f) => sum + f.count, 0)}
                  </span>
                </button>
              </li>
              {rdfClasses.map((facet) => (
                <li
                  key={facet.value}
                  className={`facet-item ${selectedRdfClass === facet.value ? 'facet-item--active' : ''}`}
                >
                  <button
                    type="button"
                    role="option"
                    aria-selected={selectedRdfClass === facet.value}
                    onClick={() =>
                      onRdfClassChange(selectedRdfClass === facet.value ? '' : facet.value)
                    }
                    data-testid={`facet-rdf-class-${facet.value}`}
                  >
                    {facet.label}
                    <span className="facet-count">{facet.count}</span>
                  </button>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </CapabilityRoute>
  );
}

export default SemanticSearchFacets;

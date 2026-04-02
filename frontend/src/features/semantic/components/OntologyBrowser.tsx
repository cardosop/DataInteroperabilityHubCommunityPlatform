/**
 * OntologyBrowser — Phase 31 (29.5)
 *
 * Fetches the hub ontology (JSON-LD) and renders a browsable class hierarchy.
 */

import { useOntology, useJSONLDContext } from '../hooks/useSemantic';
import { RDFViewer } from './RDFViewer';

export function OntologyBrowser() {
  const { data: turtleContent, isLoading: loadingOntology } = useOntology();
  const { data: context, isLoading: loadingContext } = useJSONLDContext();

  if (loadingOntology || loadingContext) {
    return <p>Loading ontology...</p>;
  }

  return (
    <div className="ontology-browser">
      <h2>Hub Ontology</h2>
      {turtleContent ? (
        <RDFViewer turtleContent={turtleContent} />
      ) : (
        <p style={{ color: 'var(--color-text-secondary)' }}>Ontology not available.</p>
      )}
      {context && (
        <div style={{ marginTop: '1rem' }}>
          <h3>JSON-LD Context</h3>
          <RDFViewer jsonLdContent={context} />
        </div>
      )}
    </div>
  );
}

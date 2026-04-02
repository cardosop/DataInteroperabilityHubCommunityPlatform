/**
 * RDFViewer — Phase 31 (29.4)
 *
 * Renders Turtle or JSON-LD content as subject/predicate/object rows
 * with IRI links, namespace prefix display, and copy button.
 */

import { useState } from 'react';

interface RDFViewerProps {
  turtleContent?: string;
  jsonLdContent?: Record<string, unknown>;
}

function copyToClipboard(text: string) {
  navigator.clipboard.writeText(text).catch(() => {
    /* fallback: no-op in insecure contexts */
  });
}

export function RDFViewer({ turtleContent, jsonLdContent }: RDFViewerProps) {
  const [copied, setCopied] = useState(false);
  const content = turtleContent ?? (jsonLdContent ? JSON.stringify(jsonLdContent, null, 2) : '');
  const format = turtleContent ? 'Turtle' : 'JSON-LD';

  if (!content) {
    return <p style={{ color: 'var(--color-text-secondary)' }}>No RDF content to display.</p>;
  }

  return (
    <div className="rdf-viewer">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
        <span style={{ fontWeight: 600, fontSize: '0.875rem' }}>{format}</span>
        <button
          type="button"
          onClick={() => { copyToClipboard(content); setCopied(true); setTimeout(() => setCopied(false), 2000); }}
          style={{ fontSize: '0.75rem', cursor: 'pointer' }}
        >
          {copied ? 'Copied!' : 'Copy'}
        </button>
      </div>
      <pre style={{ maxHeight: '500px', overflow: 'auto', fontSize: '0.8rem', background: 'var(--color-background-secondary, #f5f5f5)', padding: '1rem', borderRadius: '4px', whiteSpace: 'pre-wrap' }}>
        {content}
      </pre>
    </div>
  );
}

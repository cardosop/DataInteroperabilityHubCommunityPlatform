/**
 * Phase 230.1.3 / REQ-SEM-DISCO-001 — canonical IRI surfacing card.
 *
 * Surfaces the resource's canonical IRI on Asset / Contract / Dataset
 * detail pages (gated on truthy `canonical_iri` from the existing
 * serializers at hub/apps/{assets,contracts,datasets}/serializers.py).
 *
 * Three actions per spec:
 *   1. Copy — writes the IRI to the clipboard via navigator.clipboard
 *      with a document.execCommand('copy') fallback for non-HTTPS
 *      or older Safari (Phase 230.1.10).
 *   2. Open-in-SPARQL — links to /semantic?tab=sparql with a
 *      URL-encoded `DESCRIBE <iri>` query.
 *   3. View-JSON-LD — opens an in-card panel calling
 *      semanticService.resolveURI(type, id) and rendering the body.
 *
 * Accessibility: <section aria-labelledby> with a heading, ARIA
 * labels on icon-only buttons, role=alert on error state.
 */
import { useState, useCallback, useId } from 'react';

import { semanticService } from '../services/semanticService';
import styles from './CanonicalIriCard.module.css';

export interface CanonicalIriCardProps {
  /** The canonical IRI to surface. Null / empty hides the card. */
  iri: string | null | undefined;
  /** Resource type passed to semanticService.resolveURI. */
  resourceType: 'asset' | 'contract' | 'dataset';
  /** Resource UUID passed to semanticService.resolveURI. */
  resourceId: string;
}

async function copyToClipboard(value: string): Promise<boolean> {
  // Modern HTTPS path — navigator.clipboard.writeText.
  const clipboard = (navigator as unknown as { clipboard?: { writeText: (s: string) => Promise<void> } })
    .clipboard;
  if (clipboard && typeof clipboard.writeText === 'function') {
    try {
      await clipboard.writeText(value);
      return true;
    } catch {
      // Permission denied / SecurityError → fall through to legacy path.
    }
  }
  // Phase 230.1.10 — document.execCommand('copy') fallback for
  // non-HTTPS contexts and older Safari (clipboard API unavailable).
  if (typeof document.execCommand === 'function') {
    const textarea = document.createElement('textarea');
    textarea.value = value;
    textarea.setAttribute('readonly', '');
    textarea.style.position = 'absolute';
    textarea.style.left = '-9999px';
    document.body.appendChild(textarea);
    textarea.select();
    let ok = false;
    try {
      ok = document.execCommand('copy');
    } catch {
      ok = false;
    }
    document.body.removeChild(textarea);
    return ok;
  }
  return false;
}

export function CanonicalIriCard({
  iri,
  resourceType,
  resourceId,
}: CanonicalIriCardProps) {
  const headingId = useId();
  const [copied, setCopied] = useState(false);
  const [panelOpen, setPanelOpen] = useState(false);
  const [panelContent, setPanelContent] = useState<unknown>(null);
  const [panelError, setPanelError] = useState<string | null>(null);
  const [panelLoading, setPanelLoading] = useState(false);

  const handleCopy = useCallback(async () => {
    if (!iri) return;
    const ok = await copyToClipboard(iri);
    if (ok) {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  }, [iri]);

  const handleViewJsonLd = useCallback(async () => {
    setPanelOpen(true);
    setPanelLoading(true);
    setPanelError(null);
    setPanelContent(null);
    try {
      const data = await semanticService.resolveURI(resourceType, resourceId);
      setPanelContent(data);
    } catch (err) {
      setPanelError(err instanceof Error ? err.message : 'Failed to load JSON-LD');
    } finally {
      setPanelLoading(false);
    }
  }, [resourceType, resourceId]);

  if (!iri) {
    return null;
  }

  // The Open-in-SPARQL link must URL-encode the IRI inside a
  // DESCRIBE clause so the SPARQL builder can pre-fill its query.
  const sparqlHref =
    '/semantic?tab=sparql&query=DESCRIBE%20%3C' +
    encodeURIComponent(iri) +
    '%3E';

  return (
    <section
      data-testid="canonical-iri-card"
      aria-labelledby={headingId}
      className={styles.card}
    >
      <h3 id={headingId} className={styles.heading}>
        Canonical IRI
      </h3>
      <code data-testid="canonical-iri-value" className={styles.iri}>
        {iri}
      </code>
      <div className={styles.actions}>
        <button
          type="button"
          data-testid="canonical-iri-copy"
          aria-label={copied ? 'Copied to clipboard' : 'Copy IRI to clipboard'}
          onClick={handleCopy}
          className={styles.button}
        >
          {copied ? 'Copied!' : 'Copy'}
        </button>
        <a
          data-testid="canonical-iri-open-sparql"
          href={sparqlHref}
          aria-label="Open SPARQL builder with DESCRIBE query for this IRI"
          className={styles.button}
        >
          Open in SPARQL
        </a>
        <button
          type="button"
          data-testid="canonical-iri-view-jsonld"
          aria-label="View JSON-LD representation"
          onClick={handleViewJsonLd}
          className={styles.button}
        >
          View JSON-LD
        </button>
      </div>
      {panelOpen && (
        <div
          data-testid="canonical-iri-jsonld-panel"
          role="region"
          aria-label="JSON-LD representation"
          className={styles.panel}
        >
          {panelLoading && <p>Loading…</p>}
          {panelError && (
            <p role="alert" className={styles.panelError}>
              {panelError}
            </p>
          )}
          {panelContent !== null && !panelLoading && !panelError && (
            <pre className={styles.panelBody}>
              {JSON.stringify(panelContent, null, 2)}
            </pre>
          )}
        </div>
      )}
    </section>
  );
}

export default CanonicalIriCard;

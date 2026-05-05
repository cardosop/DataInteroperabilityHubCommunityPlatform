/**
 * Phase 230.9 (REQ-SEM-SEO-001) — Schema.org JSON-LD injector.
 *
 * Renders a `<script type="application/ld+json">` element inside the
 * document `<head>` via `react-helmet-async`. Public pages embed
 * one of these per resource so search-engine crawlers see structured
 * data without hitting an authenticated API.
 *
 * **CSP note:** `<script type="application/ld+json">` is NOT a "valid
 * script type" per the W3C HTML spec — browsers do not execute its
 * contents (it is a data island). CSP `script-src` therefore does
 * not block it; no nginx.conf change is required. This is verified
 * empirically by Google's official Schema.org guidance and by the
 * E2E test in `frontend/e2e/journeys/seo/schemaorg-public.spec.ts`
 * which asserts the script element is present in the rendered DOM
 * even under the production-grade CSP policy.
 *
 * **Auth gate:** the parent component is responsible for ensuring
 * this is only rendered on PUBLIC pages. The spec mandates auth-gated
 * pages must NOT emit Schema.org markup (avoids leaking private
 * metadata to crawlers). A render-time guard inside this component
 * would be the wrong place — auth state is a routing concern, not a
 * presentational one.
 */
import { Helmet } from 'react-helmet-async';
import type { Thing, WithContext } from 'schema-dts';

interface SchemaOrgJsonLdProps {
  /**
   * A Schema.org-typed object suitable for embedding in
   * ``<script type="application/ld+json">``. The ``WithContext<Thing>``
   * constraint makes the compiler reject any payload that doesn't
   * carry a ``@context`` (typically ``'https://schema.org'``) and an
   * ``@type``.  Audit-fix GAP-C — was previously typed ``unknown``
   * which lost compile-time validation at the call site; with the
   * tightened type, accidentally passing a raw API response (no
   * ``@context``) fails ``tsc --noEmit`` rather than shipping a
   * malformed JSON-LD block to crawlers.
   */
  data: WithContext<Thing>;
  /** Optional ``data-*`` test id for E2E assertions. Default
   *  ``schema-org-json-ld``. */
  testId?: string;
}

export function SchemaOrgJsonLd({ data, testId = 'schema-org-json-ld' }: SchemaOrgJsonLdProps) {
  // JSON.stringify with no indent — minified payloads parse cheaper
  // for crawlers and avoid extra whitespace in the served HTML.
  const json = JSON.stringify(data);
  return (
    <Helmet>
      <script type="application/ld+json" data-testid={testId}>
        {json}
      </script>
    </Helmet>
  );
}

/**
 * Public Resources Page (Visitor persona)
 * Route: /public
 *
 * This page is intentionally minimal and safe to expose without auth.
 *
 * Phase 230.9 (REQ-SEM-SEO-001) — emits Schema.org JSON-LD describing
 * the Meshant platform as a ``DataCatalog``. Crawlers see a structured
 * description without ever hitting an authenticated API.
 */
import { Link, Navigate } from 'react-router-dom';
import { SchemaOrgJsonLd } from '../../semantic/components/SchemaOrgJsonLd';
import { mapListingToSchemaOrg } from '../../semantic/utils/schemaOrgMapper';
import './AuthPage.css';

export function PublicResourcesPage() {
  const enabledEnv = (import.meta.env.VITE_PUBLIC_RESOURCES_ENABLED as string | undefined) ?? 'true';
  if (enabledEnv !== 'true') {
    return <Navigate to="/login" replace />;
  }

  // Use relative URLs so links resolve to frontend origin (e.g. localhost:3010) and get proxied by nginx
  const openApiUrl = '/api/v1/openapi.json';
  const healthUrl = '/health';

  // Phase 230.9 — Schema.org DataCatalog for the public landing page.
  // The ``mapListingToSchemaOrg`` mapper is reused here because the
  // landing page IS conceptually a catalog entry (the platform's
  // top-level data offering); a future ``mapPlatformToSchemaOrg``
  // would be a refactor candidate but adds no information today.
  const schemaOrg = mapListingToSchemaOrg({
    id: 'meshant-public',
    name: 'Meshant Data Interoperability Hub',
    description:
      'Public landing for the Meshant Data Interoperability Hub — a data ' +
      'mesh platform for governed cross-tenant data sharing, semantic ' +
      'discovery, and contract-driven data exchange.',
    canonical_iri: 'https://meshant.com/',
    updated_at: new Date().toISOString().slice(0, 10) + 'T00:00:00Z',
    keywords: ['data mesh', 'data catalog', 'semantic web', 'sparql', 'odcs'],
  });

  return (
    <div className="auth-page" role="main">
      <SchemaOrgJsonLd data={schemaOrg} />
      <div className="auth-container">
        <h1>Public Resources</h1>
        <p style={{ marginBottom: 'var(--spacing-md)', color: 'var(--color-neutral-700)' }}>
          You can access these resources without signing in (depending on deployment configuration).
        </p>

        <ul style={{ margin: 0, paddingLeft: '1.2rem', color: 'var(--color-neutral-700)' }}>
          <li>
            <a href={openApiUrl} target="_blank" rel="noreferrer">
              OpenAPI (JSON)
            </a>
          </li>
          <li>
            <a href={healthUrl} target="_blank" rel="noreferrer">
              Health check
            </a>
          </li>
        </ul>

        <div className="auth-links">
          <Link to="/login">Sign in</Link>
        </div>
      </div>
    </div>
  );
}


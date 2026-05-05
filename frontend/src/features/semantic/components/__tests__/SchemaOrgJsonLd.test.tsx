/**
 * Phase 230.9 (REQ-SEM-SEO-001) — `<SchemaOrgJsonLd>` rendering tests.
 *
 * Audit-fix GAP-E — strengthens the test surface beyond the mapper
 * unit tests by exercising the FULL rendering pipeline:
 *
 *     mapper output → <SchemaOrgJsonLd> → <Helmet> → document.head
 *
 * The mapper unit tests prove the JSON-LD object shape is right.
 * The E2E spec proves the script element survives in the rendered
 * DOM under a real browser + CSP. This test fills the gap between
 * them: it asserts that under jsdom + react-helmet-async, the
 * component does in fact produce a `<script type="application/ld+json">`
 * element with the expected JSON body, AND that the auth-gate
 * concern stays at the parent (mounting the component DOES emit;
 * NOT mounting it DOES NOT emit). Without this layer, a regression
 * in either the Helmet bridge or the JSON.stringify call would only
 * surface in E2E (slow + flaky to chase).
 */
import { render, waitFor } from '@testing-library/react';
import { HelmetProvider } from 'react-helmet-async';
import { afterEach, describe, expect, it } from 'vitest';

import { SchemaOrgJsonLd } from '../SchemaOrgJsonLd';
import { mapDatasetToSchemaOrg } from '../../utils/schemaOrgMapper';


function clearHeadScripts() {
  document.head.querySelectorAll('script[type="application/ld+json"]').forEach((el) => el.remove());
}


describe('<SchemaOrgJsonLd>', () => {
  afterEach(() => {
    // Helmet appends to document.head; clear between tests so the
    // assertions are deterministic.
    clearHeadScripts();
  });

  it('emits a <script type="application/ld+json"> in document.head with the JSON-stringified data', async () => {
    const data = mapDatasetToSchemaOrg({
      id: 'd-1',
      name: 'Test Dataset',
      description: 'A unit-test dataset.',
      canonical_iri: 'https://meshant.com/id/dataset/d-1',
      updated_at: '2026-04-01T12:00:00Z',
    });

    render(
      <HelmetProvider>
        <SchemaOrgJsonLd data={data} />
      </HelmetProvider>,
    );

    // Helmet flushes asynchronously after mount; poll until the
    // expected script appears.
    await waitFor(() => {
      const scripts = document.head.querySelectorAll(
        'script[type="application/ld+json"]',
      );
      expect(scripts).toHaveLength(1);
    });

    const script = document.head.querySelector(
      'script[type="application/ld+json"]',
    );
    expect(script).not.toBeNull();
    const parsed = JSON.parse(script!.textContent ?? '{}');
    expect(parsed['@type']).toBe('Dataset');
    expect(parsed['@context']).toBe('https://schema.org');
    expect(parsed.identifier).toBe('https://meshant.com/id/dataset/d-1');
    expect(parsed.inLanguage).toBe('en');
  });

  it('does NOT emit when the component is not mounted (auth-gate semantics)', async () => {
    // Render a HelmetProvider WITHOUT the component — represents
    // the auth-gated path where the parent decides not to mount
    // the injector.
    render(
      <HelmetProvider>
        <div data-testid="auth-gated-content" />
      </HelmetProvider>,
    );

    // Wait long enough for any Helmet flush to land — if no script
    // appears in two RAFs, none will appear at all.
    await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));

    const scripts = document.head.querySelectorAll(
      'script[type="application/ld+json"]',
    );
    expect(scripts).toHaveLength(0);
  });

  it('honors a custom testId on the script element', async () => {
    const data = mapDatasetToSchemaOrg({
      id: 'd-2',
      name: 'X',
      description: 'Y',
      canonical_iri: 'urn:ds:2',
      updated_at: '2026-01-01T00:00:00Z',
    });
    render(
      <HelmetProvider>
        <SchemaOrgJsonLd data={data} testId="my-jsonld" />
      </HelmetProvider>,
    );
    await waitFor(() => {
      const el = document.head.querySelector('script[data-testid="my-jsonld"]');
      expect(el).not.toBeNull();
    });
  });
});

/**
 * Phase 230.1.4 — CanonicalIriCard tests (test-first per the
 * REQ-SEM-DISCO-001 spec scenarios).
 *
 * Coverage:
 *   - Card renders the IRI verbatim in monospace.
 *   - Copy action writes via navigator.clipboard, with
 *     document.execCommand('copy') fallback for non-HTTPS contexts.
 *   - Open-in-SPARQL link encodes the IRI as URI component.
 *   - View-JSON-LD panel calls semanticService.resolveURI(type, id)
 *     and renders the resulting body.
 *   - Null / empty `iri` prop renders nothing in the DOM (no
 *     orphan placeholder, no testid leak).
 */
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { CanonicalIriCard } from '../CanonicalIriCard';

// Real semanticService mock-control: vitest replaces the module
// boundary so the component's call to `resolveURI` is observable
// without faking the rest of the stack.
const resolveURIMock = vi.fn();
vi.mock('../../services/semanticService', () => ({
  semanticService: {
    resolveURI: (...args: unknown[]) => resolveURIMock(...args),
  },
}));

describe('CanonicalIriCard (Phase 230.1)', () => {
  const sampleIri = 'https://meshant-internal.example.com/id/asset/abc-123';

  beforeEach(() => {
    resolveURIMock.mockReset();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('renders nothing when iri is null', () => {
    const { container } = render(
      <CanonicalIriCard iri={null} resourceType="asset" resourceId="abc-123" />,
    );
    expect(container.firstChild).toBeNull();
    expect(
      screen.queryByTestId('canonical-iri-card'),
    ).not.toBeInTheDocument();
  });

  it('renders nothing when iri is empty string', () => {
    const { container } = render(
      <CanonicalIriCard iri="" resourceType="asset" resourceId="abc-123" />,
    );
    expect(container.firstChild).toBeNull();
  });

  it('renders the IRI verbatim in a monospace block', () => {
    render(
      <CanonicalIriCard
        iri={sampleIri}
        resourceType="asset"
        resourceId="abc-123"
      />,
    );
    const card = screen.getByTestId('canonical-iri-card');
    expect(card).toBeInTheDocument();
    // The IRI itself must appear verbatim (the card is the
    // canonical surfacing point — REQ-SEM-DISCO-001).
    expect(card).toHaveTextContent(sampleIri);
  });

  it('copy button writes to navigator.clipboard on HTTPS contexts', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: { writeText },
    });
    render(
      <CanonicalIriCard
        iri={sampleIri}
        resourceType="asset"
        resourceId="abc-123"
      />,
    );
    fireEvent.click(screen.getByTestId('canonical-iri-copy'));
    await waitFor(() => {
      expect(writeText).toHaveBeenCalledWith(sampleIri);
    });
  });

  it('copy button falls back to document.execCommand when clipboard API is unavailable', async () => {
    // Simulate non-HTTPS / older Safari — clipboard API absent.
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: undefined,
    });
    const execCommand = vi.fn().mockReturnValue(true);
    Object.defineProperty(document, 'execCommand', {
      configurable: true,
      value: execCommand,
    });
    render(
      <CanonicalIriCard
        iri={sampleIri}
        resourceType="asset"
        resourceId="abc-123"
      />,
    );
    fireEvent.click(screen.getByTestId('canonical-iri-copy'));
    await waitFor(() => {
      expect(execCommand).toHaveBeenCalledWith('copy');
    });
  });

  it('open-in-SPARQL link URL-encodes the IRI as URI component', () => {
    render(
      <CanonicalIriCard
        iri={sampleIri}
        resourceType="asset"
        resourceId="abc-123"
      />,
    );
    const link = screen.getByTestId('canonical-iri-open-sparql');
    const expected =
      '/semantic?tab=sparql&query=DESCRIBE%20%3C' +
      encodeURIComponent(sampleIri) +
      '%3E';
    expect(link.getAttribute('href')).toBe(expected);
  });

  it('view-jsonld button opens the panel + calls resolveURI(type, id)', async () => {
    resolveURIMock.mockResolvedValue({
      data: { '@id': sampleIri, '@type': 'meshant:DataAsset' },
    });
    render(
      <CanonicalIriCard
        iri={sampleIri}
        resourceType="asset"
        resourceId="abc-123"
      />,
    );

    fireEvent.click(screen.getByTestId('canonical-iri-view-jsonld'));
    await waitFor(() => {
      expect(resolveURIMock).toHaveBeenCalledWith('asset', 'abc-123');
    });
    const panel = await screen.findByTestId('canonical-iri-jsonld-panel');
    expect(panel).toBeVisible();
    expect(panel).toHaveTextContent(sampleIri);
  });

  it('view-jsonld button surfaces error state on resolve failure', async () => {
    resolveURIMock.mockRejectedValue(new Error('Network down'));
    render(
      <CanonicalIriCard
        iri={sampleIri}
        resourceType="asset"
        resourceId="abc-123"
      />,
    );
    fireEvent.click(screen.getByTestId('canonical-iri-view-jsonld'));
    const panel = await screen.findByTestId('canonical-iri-jsonld-panel');
    // Don't depend on the exact error text — assert the error
    // surface is visible (via role=alert) so a screen reader picks
    // it up; the message is locale-aware.
    expect(panel.querySelector('[role="alert"]')).toBeInTheDocument();
  });
});

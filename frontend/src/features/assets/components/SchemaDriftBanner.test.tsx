/**
 * Phase 250.2.B.5 — TDD pin for SchemaDriftBanner.
 *
 * Tests the wire contract: given a serialised SchemaDriftResult,
 * the banner renders the right severity heading, the field-name
 * lists, the type-mismatch table, and the WCAG 2.1 AA-required
 * a11y attributes (`role="alert"`, `aria-live`, `aria-label`,
 * `<th scope="col">`, `<caption>`).
 */
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { SchemaDriftBanner } from './SchemaDriftBanner';
import type { SchemaDriftPayload } from './SchemaDriftBanner';

describe('SchemaDriftBanner', () => {
  it('renders nothing when drift is null', () => {
    const { container } = render(<SchemaDriftBanner drift={null} />);
    expect(container.firstChild).toBeNull();
  });

  it('renders nothing when no drift detected', () => {
    const drift: SchemaDriftPayload = {
      detected: false,
      severity: 'NONE',
      missing_fields: [],
      extra_fields: [],
      type_mismatches: [],
      structural_incompatibility: false,
    };
    const { container } = render(<SchemaDriftBanner drift={drift} />);
    expect(container.firstChild).toBeNull();
  });

  it('renders WARN heading for extra-fields-only drift', () => {
    const drift: SchemaDriftPayload = {
      detected: true,
      severity: 'WARN',
      missing_fields: [],
      extra_fields: ['extra_audit_ts'],
      type_mismatches: [],
      structural_incompatibility: false,
    };
    render(<SchemaDriftBanner drift={drift} />);
    // Heading copy from the WARN bucket.
    expect(screen.getByRole('heading', { level: 3 })).toHaveTextContent(
      /drift detected/i,
    );
    // The data attribute pins severity for E2E + visual-regression tests.
    const banner = screen.getByTestId('schema-drift-banner');
    expect(banner.getAttribute('data-severity')).toBe('WARN');
    // Extra fields are listed.
    expect(screen.getByText('extra_audit_ts')).toBeInTheDocument();
  });

  it('renders FAIL heading for structural drift', () => {
    const drift: SchemaDriftPayload = {
      detected: true,
      severity: 'FAIL',
      missing_fields: ['email'],
      extra_fields: [],
      type_mismatches: [
        { field: 'id', contract_type: 'integer', dataset_type: 'string', compatible: false },
      ],
      structural_incompatibility: true,
    };
    render(<SchemaDriftBanner drift={drift} />);
    expect(screen.getByRole('heading', { level: 3 })).toHaveTextContent(
      /does not match/i,
    );
    const banner = screen.getByTestId('schema-drift-banner');
    expect(banner.getAttribute('data-severity')).toBe('FAIL');
    // Both buckets render.
    expect(screen.getByText('email')).toBeInTheDocument();
    // Type-mismatch row.
    expect(screen.getByText('id')).toBeInTheDocument();
    expect(screen.getByText('integer')).toBeInTheDocument();
    expect(screen.getByText('string')).toBeInTheDocument();
  });

  it('uses role="alert" + aria-live for screen-reader announcement', () => {
    const drift: SchemaDriftPayload = {
      detected: true,
      severity: 'WARN',
      missing_fields: [],
      extra_fields: ['x'],
      type_mismatches: [],
      structural_incompatibility: false,
    };
    render(<SchemaDriftBanner drift={drift} />);
    const alert = screen.getByRole('alert');
    expect(alert.getAttribute('aria-live')).toBe('polite');
    expect(alert.getAttribute('aria-label')).toBeTruthy();
  });

  it('type-mismatch table has scoped headers + caption (WCAG 1.3.1)', () => {
    const drift: SchemaDriftPayload = {
      detected: true,
      severity: 'WARN',
      missing_fields: [],
      extra_fields: [],
      type_mismatches: [
        { field: 'amount', contract_type: 'integer', dataset_type: 'long', compatible: true },
      ],
      structural_incompatibility: false,
    };
    render(<SchemaDriftBanner drift={drift} />);
    const headers = screen.getAllByRole('columnheader');
    // Each <th> must have scope="col" so AT can map cell→header.
    headers.forEach((h) => {
      expect(h.getAttribute('scope')).toBe('col');
    });
    // The compatible-yes copy renders for safe widening.
    expect(screen.getByText(/safe widening/i)).toBeInTheDocument();
  });
});

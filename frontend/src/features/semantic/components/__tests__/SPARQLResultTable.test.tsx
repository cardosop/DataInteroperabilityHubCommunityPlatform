/**
 * SPARQLResultTable Tests — Phase 37
 */

import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { SPARQLResultTable } from '../SPARQLResultTable';

describe('SPARQLResultTable', () => {
  it('renders correct column headers from vars', () => {
    render(<SPARQLResultTable vars={['s', 'p', 'o']} bindings={[]} />);
    expect(screen.getByText('s')).toBeInTheDocument();
    expect(screen.getByText('p')).toBeInTheDocument();
    expect(screen.getByText('o')).toBeInTheDocument();
  });

  it('renders correct cell values from bindings', () => {
    const bindings = [
      {
        s: { value: 'http://example.org/A', type: 'uri' },
        p: { value: 'http://www.w3.org/1999/02/22-rdf-syntax-ns#type', type: 'uri' },
        o: { value: 'http://example.org/Class', type: 'uri' },
      },
      {
        s: { value: 'http://example.org/B', type: 'uri' },
        p: { value: 'http://example.org/name', type: 'uri' },
        o: { value: 'Test', type: 'literal', datatype: 'http://www.w3.org/2001/XMLSchema#string' },
      },
    ];
    render(<SPARQLResultTable vars={['s', 'p', 'o']} bindings={bindings} />);

    expect(screen.getByText('http://example.org/A')).toBeInTheDocument();
    expect(screen.getByText('http://example.org/B')).toBeInTheDocument();
    expect(screen.getByText('Test')).toBeInTheDocument();

    // Two body rows
    const table = screen.getByTestId('sparql-result-table').querySelector('table')!;
    expect(table.querySelectorAll('tbody tr')).toHaveLength(2);
  });

  it('empty bindings renders table with headers but no body rows', () => {
    render(<SPARQLResultTable vars={['x', 'y']} bindings={[]} />);
    expect(screen.getByText('x')).toBeInTheDocument();
    expect(screen.getByText('y')).toBeInTheDocument();

    const table = screen.getByTestId('sparql-result-table').querySelector('table')!;
    expect(table.querySelectorAll('tbody tr')).toHaveLength(0);
  });
});

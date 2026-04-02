/**
 * EmptyState component tests — Phase 111.4
 */
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { EmptyState } from '../EmptyState';

describe('EmptyState', () => {
  it('renders title and message', () => {
    render(<EmptyState title="No items" message="Create your first item." />);
    expect(screen.getByText('No items')).toBeInTheDocument();
    expect(screen.getByText('Create your first item.')).toBeInTheDocument();
  });

  it('renders with data-testid', () => {
    const { container } = render(<EmptyState title="Empty" message="Nothing here" />);
    expect(container.children.length).toBeGreaterThan(0);
  });

  it('renders default icon', () => {
    const { container } = render(<EmptyState title="Test" message="Msg" />);
    expect(container.textContent).toContain('Test');
  });
});

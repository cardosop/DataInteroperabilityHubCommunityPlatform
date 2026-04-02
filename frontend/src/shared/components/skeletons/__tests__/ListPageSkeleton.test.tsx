/**
 * ListPageSkeleton tests — Phase 40 (38.7)
 *
 * Tests that the list page skeleton renders the expected structure.
 */
import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/react';
import { ListPageSkeleton } from '../ListPageSkeleton';

describe('ListPageSkeleton', () => {
  it('renders exactly 8 skeleton rows', () => {
    const { container } = render(<ListPageSkeleton />);
    const rows = container.querySelectorAll('[data-testid="skeleton-row"]');
    expect(rows.length).toBe(8);
  });

  it('each row contains a circle and two line skeletons', () => {
    const { container } = render(<ListPageSkeleton />);
    const rows = container.querySelectorAll('[data-testid="skeleton-row"]');
    for (const row of rows) {
      expect(row.querySelector('.skeleton-circle')).toBeTruthy();
      const lines = row.querySelectorAll('.skeleton-line');
      expect(lines.length).toBe(2);
    }
  });

  it('renders title and action block placeholders', () => {
    const { container } = render(<ListPageSkeleton />);
    const blocks = container.querySelectorAll('.skeleton-block');
    expect(blocks.length).toBeGreaterThanOrEqual(2);
  });
});

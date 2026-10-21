/**
 * DetailPageSkeleton component tests — Phase 111.4
 */
import { render } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { DetailPageSkeleton } from '../DetailPageSkeleton';

describe('DetailPageSkeleton', () => {
  it('renders without crashing', () => {
    const { container } = render(<DetailPageSkeleton />);
    expect(container.children.length).toBeGreaterThan(0);
  });

  it('renders skeleton blocks', () => {
    const { container } = render(<DetailPageSkeleton />);
    const skeletons = container.querySelectorAll('[aria-hidden="true"], .skeleton');
    expect(skeletons.length).toBeGreaterThan(0);
  });
});

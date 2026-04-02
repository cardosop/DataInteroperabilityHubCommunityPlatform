/**
 * Icon component tests — Phase 34 (32.7)
 */
import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/react';
import { Icon } from '../Icon';
import { Home } from '../../config/iconRegistry';

describe('Icon component', () => {
  it('renders an SVG element', () => {
    const { container } = render(<Icon icon={Home} />);
    const svg = container.querySelector('svg');
    expect(svg).toBeTruthy();
  });

  it('applies correct size for each variant', () => {
    const sizes = [
      { size: 'xs' as const, expected: 'var(--icon-size-xs, 12px)' },
      { size: 'sm' as const, expected: 'var(--icon-size-sm, 16px)' },
      { size: 'md' as const, expected: 'var(--icon-size-md, 20px)' },
      { size: 'lg' as const, expected: 'var(--icon-size-lg, 24px)' },
    ];
    for (const { size, expected } of sizes) {
      const { container } = render(<Icon icon={Home} size={size} />);
      const svg = container.querySelector('svg');
      expect(svg?.style.width).toBe(expected);
      expect(svg?.style.height).toBe(expected);
    }
  });

  it('defaults to aria-hidden=true', () => {
    const { container } = render(<Icon icon={Home} />);
    const svg = container.querySelector('svg');
    expect(svg?.getAttribute('aria-hidden')).toBe('true');
  });

  it('sets aria-hidden=false when aria-label is provided', () => {
    const { container } = render(<Icon icon={Home} aria-label="Go home" />);
    const svg = container.querySelector('svg');
    expect(svg?.getAttribute('aria-hidden')).toBe('false');
    expect(svg?.getAttribute('aria-label')).toBe('Go home');
  });

  it('passes className to the SVG', () => {
    const { container } = render(<Icon icon={Home} className="my-icon" />);
    const svg = container.querySelector('svg');
    expect(svg?.classList.contains('my-icon')).toBe(true);
  });

  it('defaults to md size', () => {
    const { container } = render(<Icon icon={Home} />);
    const svg = container.querySelector('svg');
    expect(svg?.style.width).toBe('var(--icon-size-md, 20px)');
  });
});

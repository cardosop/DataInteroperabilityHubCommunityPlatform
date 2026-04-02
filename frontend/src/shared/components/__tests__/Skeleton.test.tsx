/**
 * Skeleton tests — Phase 40 (38.7)
 *
 * Tests Skeleton.Line, Skeleton.Circle, Skeleton.Block sub-components.
 */
import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/react';
import { Skeleton } from '../Skeleton';

describe('Skeleton.Line', () => {
  it('renders a div with the skeleton shimmer CSS class', () => {
    const { container } = render(<Skeleton.Line />);
    const el = container.firstElementChild as HTMLElement;
    expect(el.tagName).toBe('DIV');
    expect(el.classList.contains('skeleton')).toBe(true);
    expect(el.classList.contains('skeleton-line')).toBe(true);
  });

  it('applies default width 100% and default height', () => {
    const { container } = render(<Skeleton.Line />);
    const el = container.firstElementChild as HTMLElement;
    expect(el.style.width).toBe('100%');
    expect(el.style.height).toBeTruthy();
  });

  it('accepts custom width and height', () => {
    const { container } = render(<Skeleton.Line width="60%" height="20px" />);
    const el = container.firstElementChild as HTMLElement;
    expect(el.style.width).toBe('60%');
    expect(el.style.height).toBe('20px');
  });

  it('has aria-hidden for accessibility', () => {
    const { container } = render(<Skeleton.Line />);
    expect(container.firstElementChild?.getAttribute('aria-hidden')).toBe('true');
  });
});

describe('Skeleton.Circle', () => {
  it('renders with skeleton-circle class', () => {
    const { container } = render(<Skeleton.Circle />);
    const el = container.firstElementChild as HTMLElement;
    expect(el.classList.contains('skeleton')).toBe(true);
    expect(el.classList.contains('skeleton-circle')).toBe(true);
  });

  it('applies correct inline style for size="48px"', () => {
    const { container } = render(<Skeleton.Circle size="48px" />);
    const el = container.firstElementChild as HTMLElement;
    expect(el.style.width).toBe('48px');
    expect(el.style.height).toBe('48px');
  });

  it('defaults to 40px', () => {
    const { container } = render(<Skeleton.Circle />);
    const el = container.firstElementChild as HTMLElement;
    expect(el.style.width).toBe('40px');
    expect(el.style.height).toBe('40px');
  });
});

describe('Skeleton.Block', () => {
  it('renders with correct height', () => {
    const { container } = render(<Skeleton.Block height="200px" />);
    const el = container.firstElementChild as HTMLElement;
    expect(el.classList.contains('skeleton')).toBe(true);
    expect(el.classList.contains('skeleton-block')).toBe(true);
    expect(el.style.height).toBe('200px');
  });

  it('applies custom borderRadius', () => {
    const { container } = render(<Skeleton.Block height="100px" borderRadius="16px" />);
    const el = container.firstElementChild as HTMLElement;
    expect(el.style.borderRadius).toBe('16px');
  });

  it('defaults width to 100%', () => {
    const { container } = render(<Skeleton.Block height="50px" />);
    const el = container.firstElementChild as HTMLElement;
    expect(el.style.width).toBe('100%');
  });
});

/**
 * Button Component Tests — Phase 33
 */

import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { Button } from '../Button';

/* Minimal SVG icon stub that behaves like a Lucide icon */
function MockIcon(props: React.SVGProps<SVGSVGElement>) {
  return <svg data-testid="mock-icon" {...props} />;
}

describe('Button', () => {
  // --- Variants ---

  it('applies btn--primary class by default', () => {
    render(<Button>Save</Button>);
    expect(screen.getByRole('button')).toHaveClass('btn', 'btn--primary', 'btn--md');
  });

  it('variant="secondary" applies correct class', () => {
    render(<Button variant="secondary">Cancel</Button>);
    expect(screen.getByRole('button')).toHaveClass('btn--secondary');
  });

  it('variant="danger" applies correct class', () => {
    render(<Button variant="danger">Delete</Button>);
    expect(screen.getByRole('button')).toHaveClass('btn--danger');
  });

  it('variant="ghost" applies correct class', () => {
    render(<Button variant="ghost">Back</Button>);
    expect(screen.getByRole('button')).toHaveClass('btn--ghost');
  });

  // --- Sizes ---

  it('size="sm" applies correct class', () => {
    render(<Button size="sm">S</Button>);
    expect(screen.getByRole('button')).toHaveClass('btn--sm');
  });

  it('size="lg" applies correct class', () => {
    render(<Button size="lg">L</Button>);
    expect(screen.getByRole('button')).toHaveClass('btn--lg');
  });

  // --- Loading state ---

  it('loading={true} renders spinner, disables button, sets aria-busy', () => {
    render(<Button loading>Saving</Button>);
    const btn = screen.getByRole('button');
    expect(btn).toBeDisabled();
    expect(btn).toHaveAttribute('aria-busy', 'true');
    expect(btn.querySelector('.btn__spinner')).toBeInTheDocument();
    expect(btn).toHaveClass('btn--loading');
  });

  it('onClick is NOT called when loading={true}', async () => {
    const onClick = vi.fn();
    const user = userEvent.setup();
    render(<Button loading onClick={onClick}>Save</Button>);
    await user.click(screen.getByRole('button'));
    expect(onClick).not.toHaveBeenCalled();
  });

  // --- Disabled state ---

  it('onClick is NOT called when disabled={true}', async () => {
    const onClick = vi.fn();
    const user = userEvent.setup();
    render(<Button disabled onClick={onClick}>Save</Button>);
    await user.click(screen.getByRole('button'));
    expect(onClick).not.toHaveBeenCalled();
  });

  // --- Icons ---

  it('leadingIcon renders before label text', () => {
    render(<Button leadingIcon={MockIcon}>Label</Button>);
    const btn = screen.getByRole('button');
    const icon = btn.querySelector('[data-testid="mock-icon"]');
    const label = btn.querySelector('.btn__label');
    expect(icon).toBeInTheDocument();
    expect(label).toBeInTheDocument();
    // Icon appears before label in DOM order
    const children = Array.from(btn.children);
    expect(children.indexOf(icon as Element)).toBeLessThan(children.indexOf(label as Element));
  });

  it('trailingIcon renders after label text', () => {
    render(<Button trailingIcon={MockIcon}>Label</Button>);
    const btn = screen.getByRole('button');
    const icon = btn.querySelector('[data-testid="mock-icon"]');
    const label = btn.querySelector('.btn__label');
    expect(icon).toBeInTheDocument();
    expect(label).toBeInTheDocument();
    const children = Array.from(btn.children);
    expect(children.indexOf(icon as Element)).toBeGreaterThan(children.indexOf(label as Element));
  });

  it('icon has aria-hidden="true"', () => {
    render(<Button leadingIcon={MockIcon}>Label</Button>);
    const icon = screen.getByTestId('mock-icon');
    expect(icon).toHaveAttribute('aria-hidden', 'true');
  });

  it('loading hides leading icon and shows spinner instead', () => {
    render(<Button loading leadingIcon={MockIcon}>Label</Button>);
    const btn = screen.getByRole('button');
    expect(btn.querySelector('.btn__spinner')).toBeInTheDocument();
    expect(btn.querySelector('[data-testid="mock-icon"]')).not.toBeInTheDocument();
  });

  // --- Defaults ---

  it('defaults to type="button"', () => {
    render(<Button>Click</Button>);
    expect(screen.getByRole('button')).toHaveAttribute('type', 'button');
  });

  it('type="submit" can be overridden', () => {
    render(<Button type="submit">Submit</Button>);
    expect(screen.getByRole('button')).toHaveAttribute('type', 'submit');
  });

  it('forwards ref', () => {
    const ref = vi.fn();
    render(<Button ref={ref}>Ref</Button>);
    expect(ref).toHaveBeenCalledWith(expect.any(HTMLButtonElement));
  });

  it('spreads additional HTML attributes', () => {
    render(<Button data-testid="custom-btn" aria-label="custom">X</Button>);
    expect(screen.getByTestId('custom-btn')).toBeInTheDocument();
    expect(screen.getByRole('button')).toHaveAttribute('aria-label', 'custom');
  });
});

/**
 * Phase 85.8 — Banner tests.
 */
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { Banner } from '../Banner';

describe('Banner', () => {
  it('renders info variant with correct class', () => {
    render(<Banner variant="info">Info msg</Banner>);
    const el = screen.getByRole('status');
    expect(el.className).toContain('banner--info');
    expect(screen.getByText('Info msg')).toBeTruthy();
  });

  it('renders warning variant', () => {
    render(<Banner variant="warning">Warn</Banner>);
    expect(screen.getByRole('status').className).toContain('banner--warning');
  });

  it('renders error variant', () => {
    render(<Banner variant="error">Err</Banner>);
    expect(screen.getByRole('status').className).toContain('banner--error');
  });

  it('renders success variant', () => {
    render(<Banner variant="success">OK</Banner>);
    expect(screen.getByRole('status').className).toContain('banner--success');
  });

  it('shows dismiss button when onDismiss provided', () => {
    const onDismiss = vi.fn();
    render(<Banner variant="info" onDismiss={onDismiss}>X</Banner>);
    const btn = screen.getByLabelText('Dismiss');
    fireEvent.click(btn);
    expect(onDismiss).toHaveBeenCalledOnce();
  });

  it('hides dismiss button when onDismiss not provided', () => {
    render(<Banner variant="info">No close</Banner>);
    expect(screen.queryByLabelText('Dismiss')).toBeNull();
  });
});

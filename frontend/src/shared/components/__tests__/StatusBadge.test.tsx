/**
 * Phase 278.K.2 — StatusBadge component tests.
 */
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { StatusBadge } from '../StatusBadge';

describe('StatusBadge', () => {
  it('renders status text from STATUS_MAP', () => {
    render(<StatusBadge status="ACTIVE" />);
    expect(screen.getByText('Active')).toBeTruthy();
  });

  it('renders icon for known status', () => {
    render(<StatusBadge status="ACTIVE" />);
    expect(screen.getByText('●')).toBeTruthy();
  });

  it('applies correct color class', () => {
    render(<StatusBadge status="ACTIVE" />);
    const el = screen.getByTestId('status-badge-active');
    expect(el.className).toContain('status-badge--green');
  });

  it('falls back to gray for unknown status', () => {
    render(<StatusBadge status="CUSTOM_STATE" />);
    const el = screen.getByTestId('status-badge-custom_state');
    expect(el.className).toContain('status-badge--gray');
    expect(screen.getByText('CUSTOM_STATE')).toBeTruthy();
  });

  it('shows tooltip from label by default', () => {
    render(<StatusBadge status="FAILED" />);
    expect(screen.getByTitle('Failed')).toBeTruthy();
  });

  it('uses custom tooltip when provided', () => {
    render(<StatusBadge status="ACTIVE" tooltip="Currently running" />);
    expect(screen.getByTitle('Currently running')).toBeTruthy();
  });

  it('uses custom icon override when provided', () => {
    render(<StatusBadge status="ACTIVE" icon="★" />);
    expect(screen.getByText('★')).toBeTruthy();
  });

  it('renders children as label override', () => {
    render(<StatusBadge status="ACTIVE">Custom Label</StatusBadge>);
    expect(screen.getByText('Custom Label')).toBeTruthy();
    expect(screen.queryByText('Active')).toBeNull();
  });

  it('handles case-insensitive status input', () => {
    render(<StatusBadge status="active" />);
    expect(screen.getByTestId('status-badge-active')).toBeTruthy();
    expect(screen.getByText('Active')).toBeTruthy();
  });

  it('renders error status with red color', () => {
    render(<StatusBadge status="FAILED" />);
    expect(screen.getByTestId('status-badge-failed').className).toContain('status-badge--red');
  });

  it('renders warning status with amber color', () => {
    render(<StatusBadge status="WARNING" />);
    expect(screen.getByTestId('status-badge-warning').className).toContain('status-badge--amber');
  });
});

/**
 * Phase 278.J.1 — HelpTip component tests.
 */
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { HelpTip } from '../HelpTip';

describe('HelpTip', () => {
  it('renders a help trigger button', () => {
    render(<HelpTip term="RLS" />);
    const trigger = screen.getByRole('button', { name: /help: rls/i });
    expect(trigger).toBeTruthy();
    expect(trigger.textContent).toBe('?');
  });

  it('shows popover on click with glossary content', () => {
    render(<HelpTip term="RLS" />);
    fireEvent.click(screen.getByRole('button', { name: /help: rls/i }));
    const popover = screen.getByRole('tooltip');
    expect(popover).toBeTruthy();
    expect(popover.textContent).toContain('Row-Level Security');
  });

  it('shows custom description when provided (overrides glossary)', () => {
    render(<HelpTip term="RLS" description="Custom help text." />);
    fireEvent.click(screen.getByRole('button', { name: /help: rls/i }));
    expect(screen.getByRole('tooltip').textContent).toContain('Custom help text.');
    expect(screen.getByRole('tooltip').textContent).not.toContain('Row-Level Security');
  });

  it('closes on Escape key', () => {
    render(<HelpTip term="RLS" />);
    fireEvent.click(screen.getByRole('button', { name: /help: rls/i }));
    expect(screen.getByRole('tooltip')).toBeTruthy();
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(screen.queryByRole('tooltip')).toBeNull();
  });

  it('closes on outside click', () => {
    render(<HelpTip term="RLS" />);
    fireEvent.click(screen.getByRole('button', { name: /help: rls/i }));
    expect(screen.getByRole('tooltip')).toBeTruthy();
    fireEvent.mouseDown(document.body);
    expect(screen.queryByRole('tooltip')).toBeNull();
  });

  it('renders learn-more link when URL is available', () => {
    render(<HelpTip term="ODCS" />);
    fireEvent.click(screen.getByRole('button', { name: /help: odcs/i }));
    const link = screen.getByText(/learn more/i);
    expect(link).toBeTruthy();
    expect(link.getAttribute('href')).toContain('opendatacontractstandard');
  });

  it('has correct aria attributes on trigger button', () => {
    render(<HelpTip term="RLS" />);
    const trigger = screen.getByRole('button', { name: /help: rls/i });
    expect(trigger.getAttribute('aria-expanded')).toBe('false');
    fireEvent.click(trigger);
    expect(trigger.getAttribute('aria-expanded')).toBe('true');
    expect(trigger.getAttribute('aria-controls')).toContain('helptip-rls');
  });

  it('renders fallback message for unknown terms', () => {
    render(<HelpTip term="UNKNOWN_TERM_XYZ" />);
    fireEvent.click(screen.getByRole('button', { name: /help: unknown_term_xyz/i }));
    expect(screen.getByRole('tooltip').textContent).toContain('No help available');
  });
});

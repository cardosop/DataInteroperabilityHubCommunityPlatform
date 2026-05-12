/**
 * Phase 276.B.110 — ThemeProvider test.
 *
 * Verifies theme toggle and localStorage persistence.
 */
import { render, screen, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import { ThemeProvider, useTheme } from './ThemeProvider';

function TestButton() {
  const { theme, toggle } = useTheme();
  return (
    <button onClick={toggle} data-testid="theme-toggle">
      {theme}
    </button>
  );
}

describe('ThemeProvider', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('defaults to light theme', () => {
    render(
      <ThemeProvider>
        <TestButton />
      </ThemeProvider>,
    );
    expect(screen.getByTestId('theme-toggle').textContent).toBe('light');
  });

  it('toggles to dark theme', async () => {
    render(
      <ThemeProvider>
        <TestButton />
      </ThemeProvider>,
    );
    await userEvent.click(screen.getByTestId('theme-toggle'));
    expect(screen.getByTestId('theme-toggle').textContent).toBe('dark');
    expect(document.documentElement.getAttribute('data-theme')).toBe('dark');
  });

  it('persists theme in localStorage', async () => {
    localStorage.setItem('meshant-theme', 'dark');
    render(
      <ThemeProvider>
        <TestButton />
      </ThemeProvider>,
    );
    expect(screen.getByTestId('theme-toggle').textContent).toBe('dark');
  });
});

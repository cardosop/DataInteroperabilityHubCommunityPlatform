/**
 * Phase 278.L.2 — useRouteFocus hook tests.
 */
import { renderHook } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { useRouteFocus } from '../useRouteFocus';

// react-router-dom pathname is read from useLocation
const mockPathname = vi.fn(() => '/test-page');
vi.mock('react-router-dom', () => ({
  useLocation: () => ({ pathname: mockPathname() }),
}));

describe('useRouteFocus', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Ensure a #main-content element exists in the DOM for focus assertions
    const existing = document.getElementById('main-content');
    if (!existing) {
      const main = document.createElement('div');
      main.id = 'main-content';
      document.body.appendChild(main);
    }
  });

  it('sets tabindex=-1 on #main-content after route change', async () => {
    const main = document.getElementById('main-content')!;
    main.removeAttribute('tabindex');

    renderHook(() => useRouteFocus());

    // The hook uses a 100ms setTimeout — wait for it
    await new Promise((r) => setTimeout(r, 150));

    expect(main.getAttribute('tabindex')).toBe('-1');
  });

  it('does not overwrite existing tabindex=-1', async () => {
    const main = document.getElementById('main-content')!;
    main.setAttribute('tabindex', '-1');
    const setAttributeSpy = vi.spyOn(main, 'setAttribute');

    renderHook(() => useRouteFocus());
    await new Promise((r) => setTimeout(r, 150));

    // setAttribute should not be called with tabindex because it was already -1
    const tabindexCalls = setAttributeSpy.mock.calls.filter(([attr]) => attr === 'tabindex');
    expect(tabindexCalls.length).toBe(0);
  });

  it('cleans up timeout on unmount', () => {
    const clearSpy = vi.spyOn(window, 'clearTimeout');
    const { unmount } = renderHook(() => useRouteFocus());
    unmount();
    expect(clearSpy).toHaveBeenCalled();
    clearSpy.mockRestore();
  });
});

/**
 * GraphCanvas tests — Phase 36 (34.6)
 */
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { GraphCanvas } from '../GraphCanvas';

if (!globalThis.ResizeObserver) {
  class ResizeObserverMock {
    observe() {}
    unobserve() {}
    disconnect() {}
  }
  globalThis.ResizeObserver = ResizeObserverMock as typeof ResizeObserver;
}

describe('GraphCanvas', () => {
  it('renders skeleton when loading=true', () => {
    const { container } = render(<GraphCanvas nodes={[]} edges={[]} loading={true} />);
    expect(container.querySelector('.skeleton-block')).toBeTruthy();
  });

  it('renders ErrorDisplay when error is set', () => {
    render(
      <GraphCanvas
        nodes={[]}
        edges={[]}
        error={new Error('Test failure')}
      />,
    );
    expect(screen.getByText(/failed to load graph/i)).toBeTruthy();
  });

  it('calls onRetry when retry button is clicked', () => {
    const onRetry = vi.fn();
    render(
      <GraphCanvas
        nodes={[]}
        edges={[]}
        error={new Error('fail')}
        onRetry={onRetry}
      />,
    );
    const retryBtn = screen.getByRole('button', { name: /retry/i });
    fireEvent.click(retryBtn);
    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it('uses a concrete canvas height for React Flow viewport', () => {
    const { container } = render(<GraphCanvas nodes={[]} edges={[]} />);
    const wrapper = container.querySelector('.graph-canvas-wrapper') as HTMLElement | null;
    expect(wrapper).toBeTruthy();
    expect(wrapper?.style.height).toBe('600px');
    expect(wrapper?.style.minHeight).toBe('600px');
  });
});

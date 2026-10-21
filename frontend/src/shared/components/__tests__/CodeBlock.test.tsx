/**
 * CodeBlock Component Tests — Phase 37
 */

import { render, screen, act, fireEvent, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { CodeBlock } from '../CodeBlock';

describe('CodeBlock', () => {
  it('renders code content', () => {
    render(<CodeBlock language="json" code='{"key":"value"}' />);
    expect(screen.getByText(/key/)).toBeInTheDocument();
  });

  it('copy button triggers clipboard write', async () => {
    // Create a fresh mock and patch navigator.clipboard
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(global.navigator, 'clipboard', {
      value: { writeText },
      configurable: true,
    });

    const code = '{"hello":"world"}';
    render(<CodeBlock language="json" code={code} />);

    // Use fireEvent instead of userEvent to avoid async timing issues
    fireEvent.click(screen.getByTestId('code-block-copy'));

    await waitFor(() => expect(writeText).toHaveBeenCalledWith(code));
  });

  it('shows Copied label after copy then reverts after 2s', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(global.navigator, 'clipboard', {
      value: { writeText },
      configurable: true,
    });

    vi.useFakeTimers({ shouldAdvanceTime: true });

    render(<CodeBlock language="plaintext" code="test" />);
    const btn = screen.getByTestId('code-block-copy');
    expect(btn).toHaveTextContent('Copy');

    fireEvent.click(btn);

    // Wait for async clipboard.writeText to resolve
    await act(async () => {
      await Promise.resolve();
    });
    expect(btn).toHaveTextContent('Copied');

    act(() => { vi.advanceTimersByTime(2100); });
    expect(btn).toHaveTextContent('Copy');

    vi.useRealTimers();
  });

  it('displays language label', () => {
    render(<CodeBlock language="turtle" code="@prefix hub: <http://example.org#> ." />);
    expect(screen.getByText('turtle')).toBeInTheDocument();
  });

  it('applies maxHeight style', () => {
    const { container } = render(<CodeBlock language="json" code="{}" maxHeight="300px" />);
    const block = container.querySelector('.code-block') as HTMLElement;
    expect(block.style.maxHeight).toBe('300px');
  });
});

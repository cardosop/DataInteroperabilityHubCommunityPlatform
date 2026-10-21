/**
 * CapabilityRoute component tests — Phase 111.4
 */
import { render } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';

// Mock useCapabilities to control capability availability
vi.mock('../../hooks/useCapabilities', () => ({
  useCapabilities: () => ({
    capabilities: { 'test.feature': { available: true } },
    isLoading: false,
    isCapabilityAvailable: (key: string) => key === 'test.feature',
    getCapability: () => null,
  }),
}));

import { CapabilityRoute } from '../CapabilityRoute';

describe('CapabilityRoute', () => {
  it('renders children when capability is available', () => {
    const { container } = render(
      <MemoryRouter>
        <CapabilityRoute capability="test.feature">
          <div>Feature Content</div>
        </CapabilityRoute>
      </MemoryRouter>
    );
    expect(container.textContent).toContain('Feature Content');
  });

  it('does not render children when capability unavailable', () => {
    const { container } = render(
      <MemoryRouter>
        <CapabilityRoute capability="nonexistent.feature">
          <div>Hidden Content</div>
        </CapabilityRoute>
      </MemoryRouter>
    );
    expect(container.textContent).not.toContain('Hidden Content');
  });
});

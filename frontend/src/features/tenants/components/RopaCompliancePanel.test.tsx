/**
 * W5.4 (MEDIUM-8) — the RoPA preview refresh caught its failures into
 * an EMPTY catch: a failed preview left the panel empty with no
 * explanation. The pin asserts the panel's error surface renders.
 */

import { render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { RopaCompliancePanel } from './RopaCompliancePanel';

vi.mock('../services/ropaService', () => ({
  ropaService: {
    preview: vi.fn(),
    history: vi.fn(),
    generate: vi.fn(),
  },
}));
vi.mock('../../../shared/hooks/useCapabilities', () => ({
  useCapabilities: () => ({
    capabilities: {},
    isLoading: false,
    isCapabilityAvailable: (key: string) => key === 'compliance_ropa',
    getCapability: () => undefined,
  }),
}));

import { ropaService } from '../services/ropaService';

describe('RopaCompliancePanel failure surfacing (MEDIUM-8)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(ropaService.preview).mockResolvedValue(null);
    vi.mocked(ropaService.history).mockResolvedValue([]);
  });

  it('renders a visible error when the preview refresh fails', async () => {
    // The component may call preview through a loadHistory/persistence
    // path depending on regulation state — make the entry-point call
    // fail and assert SOME visible error surface, never silence.
    vi.mocked(ropaService.preview).mockRejectedValue(new Error('preview rejected'));

    render(<RopaCompliancePanel />);

    await waitFor(() => {
      // ErrorDisplay renders a role=alert / error text region.
      expect(screen.getByText(/preview rejected|failed/i)).toBeInTheDocument();
    });
  });
});

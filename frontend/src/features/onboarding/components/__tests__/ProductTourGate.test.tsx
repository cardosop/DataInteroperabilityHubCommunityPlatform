/**
 * close-test-coverage-gaps 3.2 — ProductTourGate suite (Phase 278.R.6).
 *
 * REAL chain end-to-end (no hook mocks — the sibling
 * useUxV2Gate.test.ts mocks the capabilities hook; this suite drives
 * the real one): capabilitiesService singleton → useUxV2Gate →
 * usePersona → useAuthStore → ProductTour → authService.updateProfile →
 * PATCH /auth/me/. Only the API client is mocked.
 *
 * Root causes this suite pins (both fixed under 3.2):
 * - `ux_v2` was never registered as a runtime capability key (snapshot
 *   coercion + overlay + enumeration), so `useUxV2Gate()` resolved
 *   false for EVERY tenant and the tour could never mount;
 * - `authService.updateProfile` declared `has_seen_tour` in its type
 *   but dropped it from the PATCH body, so the cross-device
 *   persistence documented on the gate never reached the backend.
 */
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { capabilitiesService } from '../../../capabilities/services/capabilitiesService';
import { useAuthStore } from '../../../auth/store/authStore';
import { ProductTourGate } from '../ProductTourGate';
import type { User } from '../../../../shared/types/auth';

const mockGet = vi.fn();
const mockPatch = vi.fn();

vi.mock('../../../../shared/api/client', () => ({
  apiClient: {
    getClient: () => ({ get: mockGet, patch: mockPatch }),
    // W5.2 — the tenant reader the capabilities service resolves
    // entries by; these tests exercise the anonymous path.
    getEffectiveTenantId: () => null,
    // Transport plumbing the real authStore touches on refresh — the
    // real implementations manage module-level tenant-id getter state;
    // no-op seams in the client mock.
    setTenantIdGetter: () => {},
    clearTokens: () => {},
  },
}));

/** The runtime capability answer for THIS test (manifest is constant:
 * a non-null map so the SPA stays on the manifest path). */
let uxV2Capability = true;

function installCapabilitiesMock() {
  mockGet.mockImplementation((url: string) => {
    if (url.includes('/capabilities/manifest/')) {
      return Promise.resolve({ data: { capabilities: {} } });
    }
    if (url.includes('/capabilities/')) {
      return Promise.resolve({ data: { capabilities: { ux_v2: uxV2Capability } } });
    }
    return Promise.reject(new Error(`unexpected GET ${url}`));
  });
}

/** Prime the capabilities singleton for this test (the hook reads the
 * service's cached map on mount). */
async function primeCapabilities() {
  installCapabilitiesMock();
  await capabilitiesService.loadCapabilities(true);
}

function setLoggedInUser(overrides: Partial<User> = {}) {
  useAuthStore.setState({
    isAuthenticated: true,
    user: {
      id: 'u-tour',
      email: 'tour@example.com',
      has_seen_tour: false,
      roles: [],
      ...overrides,
    } as User,
  });
}

const ME_RESPONSE: User = {
  id: 'u-tour',
  email: 'tour@example.com',
  has_seen_tour: true,
  roles: [],
};

function renderGate() {
  return render(<ProductTourGate />);
}

describe('ProductTourGate (close-test-coverage-gaps 3.2)', () => {
  beforeEach(async () => {
    mockGet.mockReset();
    mockPatch.mockReset();
    localStorage.clear();
    uxV2Capability = true;
    useAuthStore.setState({ isAuthenticated: false, user: null });
  });

  afterEach(() => {
    useAuthStore.setState({ isAuthenticated: false, user: null });
    localStorage.clear();
  });

  it('renders nothing while the capabilities query is loading', () => {
    // Do NOT prime: the gate must stay silent (no flash) until the
    // ux_v2 capability has resolved.
    mockGet.mockReturnValue(new Promise(() => {}));
    setLoggedInUser();
    const { container } = renderGate();
    expect(container).toBeEmptyDOMElement();
  });

  it('renders nothing when ux_v2 is disabled for the tenant', async () => {
    uxV2Capability = false;
    await primeCapabilities();
    setLoggedInUser();
    const { container } = renderGate();
    await waitFor(() => {
      expect(capabilitiesService.isCapabilityAvailable('ux_v2')).toBe(false);
    });
    expect(container).toBeEmptyDOMElement();
    expect(screen.queryByTestId('product-tour')).toBeNull();
  });

  it('renders nothing when the user has already seen the tour', async () => {
    await primeCapabilities();
    setLoggedInUser({ has_seen_tour: true });
    const { container } = renderGate();
    await waitFor(() => {
      expect(capabilitiesService.isCapabilityAvailable('ux_v2')).toBe(true);
    });
    expect(container).toBeEmptyDOMElement();
    expect(screen.queryByTestId('product-tour')).toBeNull();
  });

  it('mounts the tour for a ux_v2 tenant with a fresh user', async () => {
    await primeCapabilities();
    setLoggedInUser();
    renderGate();
    await waitFor(() => {
      expect(screen.getByTestId('product-tour')).toBeDefined();
    });
    // Default persona copy (no roles → 'default').
    expect(screen.getByText('Your Assets')).toBeDefined();
  });

  it('renders persona-aware copy from the real usePersona chain', async () => {
    await primeCapabilities();
    setLoggedInUser({ roles: ['DATA_PROVIDER'] });
    renderGate();
    await waitFor(() => {
      expect(screen.getByTestId('product-tour')).toBeDefined();
    });
    // DE persona steps replace the default 'Your Assets' with
    // 'Ingest Your Data' (ProductTour TOUR_STEPS.DE).
    expect(screen.getByText('Ingest Your Data')).toBeDefined();
    expect(screen.queryByText('Your Assets')).toBeNull();
  });

  it('completing the tour PATCHes has_seen_tour to /auth/me/ and syncs the store', async () => {
    await primeCapabilities();
    setLoggedInUser();
    mockPatch.mockResolvedValue({ data: ME_RESPONSE });
    const user = userEvent.setup();
    renderGate();
    await waitFor(() => {
      expect(screen.getByTestId('product-tour')).toBeDefined();
    });

    // Walk all five steps (assets → contracts → marketplace →
    // compliance → help).
    for (let i = 0; i < 4; i++) {
      await user.click(screen.getByTestId('tour-next'));
    }
    await user.click(screen.getByTestId('tour-next')); // "Got it!"

    await waitFor(() => {
      expect(mockPatch).toHaveBeenCalledTimes(1);
    });
    // THE root-cause pin: the body must actually carry the flag.
    expect(mockPatch).toHaveBeenCalledWith('/auth/me/', { has_seen_tour: true });

    // localStorage flag written by ProductTour (immediate gate).
    expect(localStorage.getItem('meshant.tour.completed')).toBe('true');

    // Store synced with the /auth/me/ response → the gate unmounts the
    // overlay (has_seen_tour now true in the store).
    await waitFor(() => {
      expect(useAuthStore.getState().user?.has_seen_tour).toBe(true);
      expect(screen.queryByTestId('product-tour')).toBeNull();
    });
  });

  it('skipping the tour runs the same persistence path', async () => {
    await primeCapabilities();
    setLoggedInUser();
    mockPatch.mockResolvedValue({ data: ME_RESPONSE });
    const user = userEvent.setup();
    renderGate();
    await waitFor(() => {
      expect(screen.getByTestId('product-tour')).toBeDefined();
    });

    await user.click(screen.getByRole('button', { name: 'Skip tour' }));

    await waitFor(() => {
      expect(mockPatch).toHaveBeenCalledWith('/auth/me/', { has_seen_tour: true });
    });
    expect(localStorage.getItem('meshant.tour.completed')).toBe('true');
    await waitFor(() => {
      expect(screen.queryByTestId('product-tour')).toBeNull();
    });
  });

  it('closes the tour even when the backend persistence fails', async () => {
    await primeCapabilities();
    setLoggedInUser();
    mockPatch.mockRejectedValue(new Error('backend down'));
    const user = userEvent.setup();
    renderGate();
    await waitFor(() => {
      expect(screen.getByTestId('product-tour')).toBeDefined();
    });

    await user.click(screen.getByRole('button', { name: 'Skip tour' }));

    // Best-effort contract: the localStorage flag is the immediate
    // gate; the PATCH failure must not crash or leave the overlay up.
    await waitFor(() => {
      expect(localStorage.getItem('meshant.tour.completed')).toBe('true');
      expect(screen.queryByTestId('product-tour')).toBeNull();
    });
    expect(useAuthStore.getState().user?.has_seen_tour).toBe(false);
  });
});

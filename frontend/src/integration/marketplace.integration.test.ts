/**
 * Marketplace integration tests — real API, no mocks.
 * Task 7.10: Critical flow (marketplace) runs against real backend.
 * Prerequisites: Backend at VITE_API_BASE_URL; auth (login first).
 */

import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { listingService } from '../features/marketplace/services/listingService';
import { authService } from '../features/auth/services/authService';

const E2E_EMAIL = 'e2e_test@example.com';
const E2E_PASSWORD = 'TestPass123';

describe('Marketplace integration (real API)', () => {
  beforeEach(async () => {
    authService.clearAuth();
    await authService.login({ email: E2E_EMAIL, password: E2E_PASSWORD });
  });

  afterEach(async () => {
    try {
      await authService.logout();
    } catch {
      authService.clearAuth();
    }
  });

  it('list returns paginated listings', async () => {
    const result = await listingService.list({ page_size: 10 });

    expect(result).toBeDefined();
    expect(Array.isArray(result.results)).toBe(true);
    expect(typeof result.count).toBe('number');
  });

  it('search returns filtered listings', async () => {
    const result = await listingService.search('', { page_size: 5 });

    expect(result).toBeDefined();
    expect(result.results.length).toBeLessThanOrEqual(5);
  });
});

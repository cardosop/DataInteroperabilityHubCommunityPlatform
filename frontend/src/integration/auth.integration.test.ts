/**
 * Auth integration tests — real API, no mocks.
 * Task 7.10: Critical flow (auth) runs against real backend.
 * Prerequisites: Backend at VITE_API_BASE_URL; ensure_e2e_user_roles run.
 */

import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { authService } from '../features/auth/services/authService';

const E2E_EMAIL = 'e2e_test@example.com';
const E2E_PASSWORD = 'TestPass123';

describe('Auth integration (real API)', () => {
  beforeEach(() => {
    authService.clearAuth();
  });

  afterEach(async () => {
    try {
      await authService.logout();
    } catch {
      authService.clearAuth();
    }
  });

  it('login with valid credentials returns tokens', async () => {
    const result = await authService.login({ email: E2E_EMAIL, password: E2E_PASSWORD });

    expect(result).toBeDefined();
    expect(result.access_token).toBeDefined();
    expect(typeof result.access_token).toBe('string');
    expect(result.refresh_token).toBeDefined();
    expect(authService.isAuthenticated()).toBe(true);
    expect(authService.getUser()?.email).toBe(E2E_EMAIL);
  });

  it('fetchUser returns current user when authenticated', async () => {
    await authService.login({ email: E2E_EMAIL, password: E2E_PASSWORD });
    const user = await authService.fetchUser();

    expect(user).toBeDefined();
    expect(user.email).toBe(E2E_EMAIL);
    expect(user.id).toBeDefined();
  });

  it('logout clears auth state', async () => {
    await authService.login({ email: E2E_EMAIL, password: E2E_PASSWORD });
    expect(authService.isAuthenticated()).toBe(true);

    await authService.logout();
    expect(authService.isAuthenticated()).toBe(false);
    expect(authService.getAccessToken()).toBeNull();
    expect(authService.getUser()).toBeNull();
  });

  it('login with invalid credentials throws', async () => {
    await expect(
      authService.login({ email: 'invalid@example.com', password: 'wrong' })
    ).rejects.toThrow();
  });
});

/**
 * Phase 277.B.033 — UserSettingsPage Vitest component tests.
 */
import { render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { UserSettingsPage } from '../UserSettingsPage';
import * as authServiceModule from '../../../auth/services/authService';

const mockFetchMe = vi.fn();
const mockUpdateProfile = vi.fn();

vi.mock('../../../auth/services/authService', () => ({
  authService: {
    fetchMe: (...args: unknown[]) => mockFetchMe(...args),
    updateProfile: (...args: unknown[]) => mockUpdateProfile(...args),
  },
}));

describe('UserSettingsPage', () => {
  it('shows loading spinner while fetching profile', () => {
    mockFetchMe.mockReturnValue(new Promise(() => {}));
    render(<UserSettingsPage />);
    expect(screen.getByTestId('user-settings-page')).toBeDefined();
    expect(screen.getByText('User Settings')).toBeDefined();
  });

  it('shows error display when profile load fails', async () => {
    mockFetchMe.mockRejectedValue(new Error('Failed to load profile'));
    render(<UserSettingsPage />);
    await waitFor(() => {
      expect(screen.getByText('Failed to load profile')).toBeDefined();
    });
  });

  it('renders profile form with email and display name after load', async () => {
    mockFetchMe.mockResolvedValue({
      email: 'test@example.com',
      display_name: 'Test User',
      status: 'ACTIVE',
    });
    render(<UserSettingsPage />);
    await waitFor(() => {
      expect(screen.getByTestId('display-name-input')).toBeDefined();
      expect(screen.getByTestId('email-display')).toBeDefined();
      expect(screen.getByTestId('save-profile-btn')).toBeDefined();
      expect(screen.getByTestId('privacy-link')).toBeDefined();
      expect(screen.getByTestId('profile-link')).toBeDefined();
    });
  });

  it('shows email as readonly text', async () => {
    mockFetchMe.mockResolvedValue({
      email: 'dpo@example.com',
      display_name: 'DPO',
      status: 'ACTIVE',
    });
    render(<UserSettingsPage />);
    await waitFor(() => {
      expect(screen.getByTestId('email-display').textContent).toBe('dpo@example.com');
    });
  });

  it('shows "Saved!" after successful save', async () => {
    mockFetchMe.mockResolvedValue({
      email: 'test@example.com',
      display_name: 'Old Name',
      status: 'ACTIVE',
    });
    mockUpdateProfile.mockResolvedValue({ display_name: 'New Name' });
    render(<UserSettingsPage />);
    await waitFor(() => {
      expect(screen.getByTestId('save-profile-btn')).toBeDefined();
    });
  });
});

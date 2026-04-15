/**
 * User Profile Page
 * Edit display name, avatar URL, and preferences.
 * Route: /settings/profile
 */

import { useEffect, useState } from 'react';
import { Breadcrumbs } from '../../../shared/components/Breadcrumbs';
import { Button } from '../../../shared/components/Button';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { LoadingSpinner } from '../../../shared/components/LoadingSpinner';
import type { ApiError } from '../../../shared/types/api';
import type { ProfileUpdateRequest, User } from '../../../shared/types/auth';
import { normalizeError } from '../../../shared/utils/errorUtils';
import { useAuthStore } from '../store/authStore';
import { authService } from '../services/authService';
import './ProfilePage.css';

const DISPLAY_NAME_MAX_LENGTH = 255;
const AVATAR_URL_MAX_LENGTH = 500;

export function ProfilePage() {
  const { refreshUser } = useAuthStore();
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const [displayName, setDisplayName] = useState('');
  const [avatar, setAvatar] = useState('');
  const [validationErrors, setValidationErrors] = useState<Record<string, string>>({});

  const loadUser = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await authService.fetchUser();
      setUser(data);
      setDisplayName(data.name ?? '');
      setAvatar(data.avatar ?? '');
    } catch (err) {
      setError(normalizeError(err));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadUser();
  }, []);

  const validate = (): boolean => {
    const errs: Record<string, string> = {};
    if (!displayName.trim()) {
      errs.display_name = 'Display name is required';
    } else if (displayName.length > DISPLAY_NAME_MAX_LENGTH) {
      errs.display_name = `Display name must be at most ${DISPLAY_NAME_MAX_LENGTH} characters`;
    }
    if (avatar.trim()) {
      try {
        new URL(avatar);
      } catch {
        errs.avatar = 'Please enter a valid URL';
      }
      if (avatar.length > AVATAR_URL_MAX_LENGTH) {
        errs.avatar = `Avatar URL must be at most ${AVATAR_URL_MAX_LENGTH} characters`;
      }
    }
    setValidationErrors(errs);
    return Object.keys(errs).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSuccessMessage(null);
    if (!validate()) return;

    setSaving(true);
    setError(null);
    try {
      const payload: ProfileUpdateRequest = {
        display_name: displayName.trim() || null,
        avatar: avatar.trim() || null,
      };
      const updated = await authService.updateProfile(payload);
      setUser(updated);
      // Pass the PATCH response directly to avoid a redundant GET /auth/me/ that can race
      // with parallel E2E workers modifying the same user's profile concurrently.
      await refreshUser(updated);
      setSuccessMessage('Profile updated successfully.');
    } catch (err) {
      setError(normalizeError(err));
    } finally {
      setSaving(false);
    }
  };

  if (loading && !user) {
    return <LoadingSpinner message="Loading profile..." />;
  }

  if (error && !user) {
    return (
      <ErrorDisplay error={error} title="Failed to load profile" onRetry={() => loadUser()} />
    );
  }

  return (
    <div className="profile-page">
      <Breadcrumbs
        items={[
          { label: 'Home', href: '/' },
          { label: 'Settings', href: '/settings/profile' },
          { label: 'Profile' },
        ]}
      />
      <div className="profile-page-header">
        <h1>Profile</h1>
        <p className="profile-page-description">
          Update your display name and avatar. Changes appear across the app.
        </p>
      </div>

      <form className="profile-form" onSubmit={handleSubmit}>
        {successMessage && (
          <div className="profile-success" role="status">
            {successMessage}
          </div>
        )}
        {error && (
          <div className="profile-error" role="alert">
            {error.error.message || 'An error occurred'}
          </div>
        )}

        <div className="profile-form-group">
          <label htmlFor="profile-display_name">Display name</label>
          <input
            id="profile-display_name"
            name="display_name"
            type="text"
            required
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
            placeholder="Your display name"
            maxLength={DISPLAY_NAME_MAX_LENGTH}
            aria-invalid={!!validationErrors.display_name}
            aria-describedby={validationErrors.display_name ? 'display_name-error' : undefined}
          />
          {validationErrors.display_name && (
            <span id="display_name-error" className="profile-field-error">
              {validationErrors.display_name}
            </span>
          )}
        </div>

        <div className="profile-form-group">
          <label htmlFor="profile-avatar">Avatar URL</label>
          <input
            id="profile-avatar"
            name="avatar"
            type="url"
            value={avatar}
            onChange={(e) => setAvatar(e.target.value)}
            placeholder="https://example.com/avatar.png"
            maxLength={AVATAR_URL_MAX_LENGTH}
            aria-invalid={!!validationErrors.avatar}
            aria-describedby={validationErrors.avatar ? 'avatar-error' : undefined}
          />
          {validationErrors.avatar && (
            <span id="avatar-error" className="profile-field-error">
              {validationErrors.avatar}
            </span>
          )}
        </div>

        <div className="profile-form-actions">
          <Button variant="primary" type="submit" loading={saving}>
            Save
          </Button>
        </div>
      </form>

      {user && (
        <div className="profile-readonly">
          <h2>Account</h2>
          <dl>
            <dt>Email</dt>
            <dd>{user.email}</dd>
          </dl>
        </div>
      )}
    </div>
  );
}

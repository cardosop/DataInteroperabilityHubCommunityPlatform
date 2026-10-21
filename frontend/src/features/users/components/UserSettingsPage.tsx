/**
 * Phase 277.B.033 — User Settings page.
 *
 * Loads the current profile via ``authService.fetchUser``, renders the
 * email as readonly text with an editable display name, and persists
 * changes through ``authService.updateProfile``. The pinned contract
 * (loading → error → form → save) lives in
 * ``UserSettingsPage.test.tsx``.
 */
import { useEffect, useState } from 'react';
import { Button } from '../../../shared/components/Button';
import { useToast } from '../../../shared/components/Toast/useToast';
import { getErrorMessage } from '../../../shared/utils/errorUtils';
import { authService } from '../../auth/services/authService';

interface ProfilePayload {
  email: string;
  display_name?: string;
  status?: string;
  [key: string]: unknown;
}

export function UserSettingsPage() {
  const toast = useToast();
  const [profile, setProfile] = useState<ProfilePayload | null>(null);
  const [displayName, setDisplayName] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    let cancelled = false;
    authService
      .fetchUser()
      .then((user) => {
        if (cancelled) return;
        setProfile(user as unknown as ProfilePayload);
        setDisplayName(
          (user as unknown as ProfilePayload).display_name ?? user.name ?? '',
        );
        setLoading(false);
      })
      .catch(() => {
        if (cancelled) return;
        setError('Failed to load profile');
        setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const handleSave = async () => {
    setSaving(true);
    setSaved(false);
    setError(null);
    try {
      await authService.updateProfile({ display_name: displayName } as never);
      setSaved(true);
    } catch (err) {
      // W5.4 (MEDIUM-8) — a failed profile save was console-only (the
      // rejection escaped unhandled). Surface it: assertive toast + inline.
      const message = getErrorMessage(err) || 'Failed to save profile';
      setError(message);
      toast.error(`Couldn't save profile: ${message}`);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="user-settings-page" data-testid="user-settings-page">
      <h1>User Settings</h1>

      {loading && <p data-testid="user-settings-loading">Loading…</p>}

      {error && <p role="alert">{error}</p>}

      {profile && (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            void handleSave();
          }}
        >
          <div>
            <label htmlFor="display-name-input">Display name</label>
            <input
              id="display-name-input"
              data-testid="display-name-input"
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
            />
          </div>
          <p data-testid="email-display">{profile.email}</p>
          <Button
            type="submit"
            variant="primary"
            data-testid="save-profile-btn"
            disabled={saving}
          >
            {saving ? 'Saving…' : 'Save'}
          </Button>
        </form>
      )}

      {saved && <p role="status">Saved!</p>}

      <nav>
        <a href="/settings/profile" data-testid="profile-link">
          Profile
        </a>
        <a href="/settings/privacy" data-testid="privacy-link">
          Privacy
        </a>
      </nav>
    </div>
  );
}

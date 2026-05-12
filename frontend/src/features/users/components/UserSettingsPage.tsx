/**
 * Phase 276.B.100 — User Settings page stub.
 * Exposes /users/ backend API for profile/settings management.
 */
import { useState } from 'react';
import { Button } from '../../../shared/components/Button';

export function UserSettingsPage() {
  const [saved, setSaved] = useState(false);

  return (
    <div className="user-settings-page" data-testid="user-settings-page">
      <h1>User Settings</h1>
      <p>Profile and account settings. (Phase 276.B.100 — stub)</p>
      <Button variant="primary" onClick={() => setSaved(true)}>
        {saved ? 'Saved' : 'Save Settings'}
      </Button>
    </div>
  );
}

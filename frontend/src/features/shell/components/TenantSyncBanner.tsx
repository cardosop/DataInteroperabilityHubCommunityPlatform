/**
 * TenantSyncBanner — multi-tab tenant-change notification (278.C.2).
 *
 * When the user switches tenant in tab A, tab B shows a non-blocking
 * banner: "Tenant changed in another tab. [Refresh →]". Pairs with
 * the ``useActiveTenantId`` storage-event listener from 276.B.002.
 */
import { useCallback, useEffect, useState } from 'react';
import './TenantSyncBanner.css';

const STORAGE_KEY = 'auth:tenant-switch';

export function TenantSyncBanner() {
  const [show, setShow] = useState(false);

  const handleStorage = useCallback((e: StorageEvent) => {
    if (e.key === STORAGE_KEY && e.newValue) {
      setShow(true);
    }
  }, []);

  useEffect(() => {
    window.addEventListener('storage', handleStorage);
    return () => window.removeEventListener('storage', handleStorage);
  }, [handleStorage]);

  const handleRefresh = () => {
    window.location.reload();
  };

  const handleDismiss = () => {
    setShow(false);
  };

  if (!show) return null;

  return (
    <div
      className="tenant-sync-banner"
      role="alert"
      aria-live="polite"
      data-testid="tenant-sync-banner"
    >
      <span className="tenant-sync-banner__text">
        Tenant changed in another tab.
      </span>
      <button
        type="button"
        className="tenant-sync-banner__action"
        onClick={handleRefresh}
      >
        Refresh →
      </button>
      <button
        type="button"
        className="tenant-sync-banner__dismiss"
        onClick={handleDismiss}
        aria-label="Dismiss"
      >
        ✕
      </button>
    </div>
  );
}

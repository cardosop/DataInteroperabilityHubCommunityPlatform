/**
 * DeploymentSyncBadge — Phase 25.19
 *
 * Shows sync status for Prefect deployment:
 *   FAILED  → yellow warning badge
 *   PENDING → grey badge
 *   SYNCED  → hidden (nothing to show)
 *
 * Optionally renders a "Retry sync" button when status !== SYNCED.
 */

import type { DeploymentSyncStatus } from '../types/scheduledIngestion';
import './DeploymentSyncBadge.css';

interface DeploymentSyncBadgeProps {
  status: DeploymentSyncStatus | undefined | null;
  onRetrySync?: () => void;
  isSyncing?: boolean;
}

export function DeploymentSyncBadge({
  status,
  onRetrySync,
  isSyncing = false,
}: DeploymentSyncBadgeProps) {
  if (!status || status === 'SYNCED') return null;

  return (
    <span className="deployment-sync-wrapper" data-testid="deployment-sync-badge">
      {status === 'FAILED' && (
        <span className="deployment-sync-badge failed" title="Prefect deployment sync failed">
          Schedule not synced
        </span>
      )}
      {status === 'PENDING' && (
        <span className="deployment-sync-badge pending" title="Prefect deployment sync in progress">
          Sync pending
        </span>
      )}
      {onRetrySync && (
        <button
          type="button"
          className="deployment-sync-retry-btn"
          onClick={(e) => {
            e.stopPropagation();
            onRetrySync();
          }}
          disabled={isSyncing}
          aria-label="Retry deployment sync"
          data-testid="deployment-sync-retry-btn"
        >
          {isSyncing ? (
            <>
              <span className="deployment-sync-spinner" />
              Syncing...
            </>
          ) : (
            'Retry sync'
          )}
        </button>
      )}
    </span>
  );
}

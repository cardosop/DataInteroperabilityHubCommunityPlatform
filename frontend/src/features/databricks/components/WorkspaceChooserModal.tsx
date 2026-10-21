/**
 * Workspace chooser modal (task 0b.12 — JOURNEY-DB-003 step 2):
 * multi-workspace tenants pick the Databricks workspace to sign in with.
 */

import { useEffect, useState } from 'react';

import { useTranslation } from '../../../shared/i18n/useTranslation';
import { useDialogA11y } from '../../../shared/hooks/useFocusManagement';
import {
  ssoWorkspaces,
  type SsoWorkspace,
} from '../services/databricksSsoService';

interface Props {
  tenantId: string;
  onPick: (workspaceId: string) => void;
  onClose: () => void;
}

export function WorkspaceChooserModal({
  tenantId,
  onPick,
  onClose,
}: Props): React.ReactElement {
  const { t } = useTranslation();
  // W5.4 (R2-F5) — focus trap + Escape on the chooser dialog.
  const dialogRef = useDialogA11y(true, onClose);
  const [workspaces, setWorkspaces] = useState<SsoWorkspace[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoadError(null);
    setLoading(true);
    ssoWorkspaces(tenantId)
      .then((items) => {
        if (!cancelled) {
          setWorkspaces(items);
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          // W5.4 (MEDIUM-8) — the failure produced a silently EMPTY list;
          // the user saw zero workspaces with no explanation.
          setWorkspaces([]);
          setLoadError(String((err as Error)?.message ?? err) || 'Failed to load workspaces');
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [tenantId]);

  return (
    <div
      ref={dialogRef}
      role="dialog"
      aria-modal="true"
      aria-label={t('databricks.sso.chooser_title', 'Choose a Databricks workspace')}
      data-testid="databricks-chooser"
    >
      <h3>{t('databricks.sso.chooser_title', 'Choose a Databricks workspace')}</h3>
      {loading ? (
        <p>{t('databricks.sso.chooser_loading', 'Loading workspaces…')}</p>
      ) : loadError ? (
        <p role="alert">{loadError}</p>
      ) : (
        <ul>
          {workspaces.map((ws) => (
            <li key={ws.id}>
              <button
                type="button"
                className="auth-button"
                onClick={() => onPick(ws.id)}
              >
                {ws.name} ({ws.host})
              </button>
            </li>
          ))}
        </ul>
      )}
      <button type="button" onClick={onClose}>
        {t('databricks.sso.chooser_cancel', 'Cancel')}
      </button>
    </div>
  );
}

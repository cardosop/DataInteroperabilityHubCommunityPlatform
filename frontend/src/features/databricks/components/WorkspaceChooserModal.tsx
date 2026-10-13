/**
 * Workspace chooser modal (task 0b.12 — JOURNEY-DB-003 step 2):
 * multi-workspace tenants pick the Databricks workspace to sign in with.
 */

import { useEffect, useState } from 'react';

import { useTranslation } from '../../../shared/i18n/useTranslation';
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
  const [workspaces, setWorkspaces] = useState<SsoWorkspace[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    ssoWorkspaces(tenantId)
      .then((items) => {
        if (!cancelled) {
          setWorkspaces(items);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setWorkspaces([]);
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
      role="dialog"
      aria-modal="true"
      aria-label={t('databricks.sso.chooser_title', 'Choose a Databricks workspace')}
      data-testid="databricks-chooser"
    >
      <h3>{t('databricks.sso.chooser_title', 'Choose a Databricks workspace')}</h3>
      {loading ? (
        <p>{t('databricks.sso.chooser_loading', 'Loading workspaces…')}</p>
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

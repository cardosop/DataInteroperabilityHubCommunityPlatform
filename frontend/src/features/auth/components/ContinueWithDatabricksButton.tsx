/**
 * "Continue with Databricks" login button (task 0b.12 — JOURNEY-DB-003
 * step 1).
 *
 * Renders only when a tenant hint is available (the `?tenant_id=` query
 * param — the standard pre-login tenant entry) so the SSO endpoints can
 * resolve the chooser. Click → workspace chooser (or direct redirect
 * when the tenant has exactly one SSO-eligible workspace).
 */

import { useState } from 'react';
import { useSearchParams } from 'react-router-dom';

import { useTranslation } from '../../../shared/i18n/useTranslation';
import {
  DatabricksApiError,
} from '../../databricks/services/databricksService';
import { ssoLoginUrl, ssoWorkspaces } from '../../databricks/services/databricksSsoService';
import { WorkspaceChooserModal } from '../../databricks/components/WorkspaceChooserModal';

const redirectUri = () =>
  `${window.location.origin}/auth/databricks/callback`;

export function ContinueWithDatabricksButton(): React.ReactElement | null {
  const { t } = useTranslation();
  const [searchParams] = useSearchParams();
  const tenantId = searchParams.get('tenant_id');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [chooserOpen, setChooserOpen] = useState(false);

  if (!tenantId) {
    return null; // no tenant hint → the button is not actionable
  }

  const handleClick = async () => {
    setBusy(true);
    setError(null);
    try {
      const workspaces = await ssoWorkspaces(tenantId);
      if (workspaces.length === 0) {
        setError(t('databricks.sso.no_workspaces', 'No Databricks workspace is available for sign-in.'));
        return;
      }
      if (workspaces.length === 1) {
        const { login_url } = await ssoLoginUrl(
          tenantId,
          workspaces[0].id,
          redirectUri()
        );
        window.location.assign(login_url);
        return;
      }
      setChooserOpen(true);
    } catch (e) {
      const code = e instanceof DatabricksApiError ? e.code : undefined;
      setError(code ? `[${code}] ${(e as Error).message}` : String(e));
    } finally {
      setBusy(false);
    }
  };

  const handlePick = async (workspaceId: string) => {
    setBusy(true);
    try {
      const { login_url } = await ssoLoginUrl(tenantId, workspaceId, redirectUri());
      window.location.assign(login_url);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <button
        type="button"
        className="auth-button"
        data-testid="databricks-sso-button"
        onClick={() => void handleClick()}
        disabled={busy}
        aria-busy={busy}
      >
        {busy
          ? t('databricks.sso.busy', 'Connecting…')
          : t('databricks.sso.cta', 'Continue with Databricks')}
      </button>
      {error && (
        <div className="error-message" role="alert">
          {error}
        </div>
      )}
      {chooserOpen && (
        <WorkspaceChooserModal
          tenantId={tenantId}
          onPick={(id) => void handlePick(id)}
          onClose={() => setChooserOpen(false)}
        />
      )}
    </>
  );
}

/**
 * Databricks workspace management page (task 0.15).
 *
 * Lists the tenant's registered Databricks workspaces with their status,
 * and hosts the guided registration wizard (U1). When the tenant flag
 * ``databricks_control_plane_enabled`` is off, the API answers 403
 * ``DATABRICKS_CONTROL_PLANE_DISABLED`` — surfaced as a DISTINCT banner
 * (JOURNEY-DB-001 step 1), never a generic error.
 */
import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';

import { useTranslation } from '../../../shared/i18n/useTranslation';

import type { DatabricksWorkspace } from '@/shared/types/databricks';

import {
  DatabricksApiError,
  listWorkspaces,
  testWorkspace,
} from '../services/databricksService';
import { WorkspaceRegistrationWizard } from './WorkspaceRegistrationWizard';

const FLAG_DISABLED_CODE = 'DATABRICKS_CONTROL_PLANE_DISABLED';

export function WorkspaceManagementPage(): React.ReactElement {
  const { t } = useTranslation();
  const [workspaces, setWorkspaces] = useState<DatabricksWorkspace[]>([]);
  const [loading, setLoading] = useState(true);
  const [flagDisabled, setFlagDisabled] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showWizard, setShowWizard] = useState(false);
  const [testingId, setTestingId] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    setFlagDisabled(false);
    try {
      setWorkspaces(await listWorkspaces());
    } catch (e) {
      if (
        e instanceof DatabricksApiError &&
        e.code === FLAG_DISABLED_CODE
      ) {
        setFlagDisabled(true);
        setWorkspaces([]);
      } else {
        setError(e instanceof Error ? e.message : String(e));
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const handleTest = async (workspace: DatabricksWorkspace) => {
    setTestingId(workspace.id);
    setError(null);
    try {
      const result = await testWorkspace(workspace.id);
      void result;
      await load();
    } catch (e) {
      // Code parity with the wizard: operators search runbooks by the
      // machine-readable code — never drop it on the page surface.
      if (e instanceof DatabricksApiError && e.code) {
        setError(`[${e.code}] ${e.message}`);
      } else {
        setError(e instanceof Error ? e.message : String(e));
      }
    } finally {
      setTestingId(null);
    }
  };

  if (loading) {
    return <div className="warehouse-list">{t('databricks.page.loading', 'Loading Databricks workspaces…')}</div>;
  }

  if (flagDisabled) {
    return (
      <div
        className="flag-disabled-banner"
        data-testid="databricks-flag-disabled"
      >
        <h2>{t('databricks.page.title', 'Databricks workspaces')}</h2>
        <p>
          {t('databricks.page.flag_disabled_body', 'The Databricks control plane is disabled for this tenant. Contact your platform administrator to enable it.')}{' '}
          (<code>{FLAG_DISABLED_CODE}</code>)
        </p>
      </div>
    );
  }

  if (showWizard) {
    return (
      <div className="warehouse-list">
        <h2>{t('databricks.wizard.step_register_title', 'Register Databricks workspace')}</h2>
        <button type="button" onClick={() => setShowWizard(false)}>
          {t('databricks.page.back_to_workspaces', '← Back to workspaces')}
        </button>
        <WorkspaceRegistrationWizard
          onSaved={() => {
            setShowWizard(false);
            void load();
          }}
        />
      </div>
    );
  }

  return (
    <div className="warehouse-list">
      <h2>{t('databricks.page.title', 'Databricks workspaces')}</h2>
      {error && <div className="error" role="alert">{error}</div>}
      {workspaces.length === 0 ? (
        <p>{t('databricks.page.empty', 'No Databricks workspaces registered yet.')}</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Name</th>
              <th>Host</th>
              <th>Cloud</th>
              <th>Status</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {workspaces.map((ws) => (
              <tr key={ws.id}>
                <td>{ws.name}</td>
                <td>{ws.host}</td>
                <td>{ws.cloud}</td>
                <td>{ws.status_display || ws.status}</td>
                <td>
                  <button
                    type="button"
                    disabled={testingId === ws.id}
                    onClick={() => void handleTest(ws)}
                  >
                    {testingId === ws.id ? t('databricks.page.testing', 'Testing...') : t('databricks.page.test_action', 'Test')}
                  </button>
                  <Link
                    to={`/databricks/workspaces/${ws.id}/catalog`}
                    data-testid="databricks-browse-catalog"
                  >
                    {t('databricks.catalog.browse_cta', 'Browse catalog')}
                  </Link>
                  <Link
                    to={`/databricks/workspaces/${ws.id}/warehouses`}
                    data-testid="databricks-manage-warehouses"
                  >
                    {t('databricks.warehouses.title', 'SQL warehouses')}
                  </Link>{' '}
                  <Link
                    to={`/databricks/workspaces/${ws.id}/jobs`}
                    data-testid="databricks-manage-jobs"
                  >
                    {t('databricks.jobs.title', 'Databricks jobs')}
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <button
        type="button"
        className="primary"
        onClick={() => setShowWizard(true)}
      >
        {t('databricks.page.register_cta', 'Register workspace')}
      </button>
    </div>
  );
}

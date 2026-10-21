/**
 * Databricks workspace registration wizard — guided U1 flow (task 0.15).
 *
 * register → App-connection instructions → test → active
 * (JOURNEY-DB-001 / JOURNEY-DB-002 step machine).
 *
 * Step 1 collects the workspace details; the backend validates the host
 * against the *.cloud.databricks.com family allowlist + SSRF/residency
 * rules. Step 2 documents the App-connection setup and attaches a
 * credential (PAT or OAuth M2M — stored encrypted, config never echoed
 * back). Step 3 probes the connection: success moves the workspace to
 * ACTIVE; failure shows the backend's MASKED reason with a retry.
 */
import { useState } from 'react';
import { DirtyStateGuard } from '../../../shared/components/DirtyStateGuard';

import { useTranslation } from '../../../shared/i18n/useTranslation';

import {
  DatabricksCloud,
  DatabricksCredentialAuthMode,
  type DatabricksWorkspace,
} from '@/shared/types/databricks';

import {
  createCredential,
  createWorkspace,
  DatabricksApiError,
  testWorkspace,
} from '../services/databricksService';

interface Props {
  onSaved?: () => void;
}

type Step = 'details' | 'credentials' | 'test';

interface FormError {
  code?: string;
  message: string;
}

export function WorkspaceRegistrationWizard({ onSaved }: Props): React.ReactElement {
  const { t } = useTranslation();
  const [step, setStep] = useState<Step>('details');
  const [workspace, setWorkspace] = useState<DatabricksWorkspace | null>(null);

  // Step 1 state
  const [name, setName] = useState('');
  const [host, setHost] = useState('');
  const [cloud, setCloud] = useState<DatabricksCloud>(DatabricksCloud.AWS);
  const [region, setRegion] = useState('');
  const [metastoreId, setMetastoreId] = useState('');

  // Step 2 state
  const [authMode, setAuthMode] = useState<DatabricksCredentialAuthMode>(
    DatabricksCredentialAuthMode.PAT
  );
  const [token, setToken] = useState('');
  const [clientId, setClientId] = useState('');
  const [clientSecret, setClientSecret] = useState('');

  // Step 3 state
  const [latencyMs, setLatencyMs] = useState<number | null>(null);

  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<FormError | null>(null);
  // W5.4 (R2-F5) — registration inputs (incl. credentials) are unsaved
  // until the test succeeds; flag dirty on any typed value, clear on save.
  const [saved, setSaved] = useState(false);
  const dirty =
    !saved &&
    Boolean(
      name.trim() ||
        host.trim() ||
        region.trim() ||
        metastoreId.trim() ||
        token.trim() ||
        clientId.trim() ||
        clientSecret.trim(),
    );

  const fail = (e: unknown): FormError => {
    if (e instanceof DatabricksApiError) {
      return { code: e.code, message: e.message };
    }
    return { message: String(e) };
  };

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const created = await createWorkspace({
        name,
        host,
        cloud,
        region,
        ...(metastoreId ? { metastore_id: metastoreId } : {}),
      });
      setWorkspace(created);
      setStep('credentials');
    } catch (err) {
      setError(fail(err));
    } finally {
      setBusy(false);
    }
  };

  const handleCredential = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!workspace) {
      return;
    }
    setError(null);
    setBusy(true);
    try {
      await createCredential(workspace.id, {
        auth_mode: authMode,
        config:
          authMode === DatabricksCredentialAuthMode.PAT
            ? { token }
            : { client_id: clientId, client_secret: clientSecret },
      });
      setStep('test');
      await runTest(workspace.id);
    } catch (err) {
      setError(fail(err));
    } finally {
      setBusy(false);
    }
  };

  const handleChangeCredential = () => {
    // A failed test must never trap the user in a retry loop with a broken
    // credential — back to step 2 with the secrets cleared for re-entry.
    setError(null);
    setLatencyMs(null);
    setToken('');
    setClientId('');
    setClientSecret('');
    setStep('credentials');
  };

  const runTest = async (workspaceId: string) => {
    setError(null);
    setBusy(true);
    try {
      const result = await testWorkspace(workspaceId);
      setLatencyMs(result.latency_ms);
      setWorkspace((w) =>
        w ? { ...w, status: 'ACTIVE', status_display: 'Active' } : w
      );
      // Persisted — the post-save navigation must not be blocked.
      setSaved(true);
      onSaved?.();
    } catch (err) {
      setError(fail(err));
    } finally {
      setBusy(false);
    }
  };

  const errorNode = error ? (
    <div className="error" role="alert" data-testid="databricks-wizard-error">
      {error.code && <span className="error-code">[{error.code}]</span>}{' '}
      {error.message}
    </div>
  ) : null;

  if (step === 'details') {
    return (
      <form
        className="warehouse-wizard"
        data-testid="databricks-register-wizard"
        onSubmit={handleRegister}
        aria-busy={busy}
      >
        <h3 aria-current="step">{t('databricks.wizard.step_register_title', 'Register Databricks workspace')}</h3>
        {errorNode}
        <label>
          {t('databricks.wizard.name_label', 'Workspace name')}
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
            placeholder="e.g. Production analytics"
          />
        </label>
        <label>
          {t('databricks.wizard.host_label', 'Workspace host')}
          <input
            value={host}
            onChange={(e) => setHost(e.target.value)}
            required
            placeholder="e.g. dbc-xxxx.cloud.databricks.com"
          />
        </label>
        <label>
          {t('databricks.wizard.cloud_label', 'Cloud')}
          <select
            value={cloud}
            onChange={(e) => setCloud(e.target.value as DatabricksCloud)}
          >
            <option value={DatabricksCloud.AWS}>AWS</option>
            <option value={DatabricksCloud.AZURE}>Azure</option>
            <option value={DatabricksCloud.GCP}>GCP</option>
          </select>
        </label>
        <label>
          {t('databricks.wizard.region_label', 'Region')}
          <input
            value={region}
            onChange={(e) => setRegion(e.target.value)}
            required
            placeholder="e.g. us-east-1"
          />
        </label>
        <label>
          {t('databricks.wizard.metastore_label', 'Metastore ID (optional)')}
          <input
            value={metastoreId}
            onChange={(e) => setMetastoreId(e.target.value)}
            placeholder="Unity Catalog metastore id"
          />
        </label>
        <button type="submit" disabled={busy}>
          {busy ? t('databricks.wizard.registering', 'Registering...') : t('databricks.wizard.continue', 'Continue')}
        </button>
      </form>
    );
  }

  if (step === 'credentials') {
    return (
      <form
        className="warehouse-wizard"
        data-testid="databricks-register-wizard"
        onSubmit={handleCredential}
        aria-busy={busy}
      >
        <h3 aria-current="step">{t('databricks.wizard.step_credentials_title', 'Connect your app')}</h3>
        <div className="app-connection-instructions">
          <p>{t('databricks.wizard.instructions_body', 'In the Databricks workspace console, generate a personal access token (Settings → Developer → Access tokens) or register an OAuth M2M client (service principal). The Hub stores the credential encrypted at rest and never returns it.')}</p>
        </div>
        {errorNode}
        <label>
          {t('databricks.wizard.auth_mode_label', 'Auth mode')}
          <select
            value={authMode}
            onChange={(e) =>
              setAuthMode(e.target.value as DatabricksCredentialAuthMode)
            }
          >
            <option value={DatabricksCredentialAuthMode.PAT}>
              {t('databricks.wizard.auth_mode_pat', 'Personal Access Token (PAT)')}
            </option>
            <option value={DatabricksCredentialAuthMode.OAUTH_M2M}>
              {t('databricks.wizard.auth_mode_m2m', 'OAuth M2M (client credentials)')}
            </option>
          </select>
        </label>
        {authMode === DatabricksCredentialAuthMode.PAT ? (
          <label>
            {t('databricks.wizard.token_label', 'Personal access token')}
            <input
              type="password"
              value={token}
              onChange={(e) => setToken(e.target.value)}
              required
              placeholder="dapi..."
            />
          </label>
        ) : (
          <>
            <label>
              {t('databricks.wizard.client_id_label', 'Client ID')}
              <input
                value={clientId}
                onChange={(e) => setClientId(e.target.value)}
                required
              />
            </label>
            <label>
              {t('databricks.wizard.client_secret_label', 'Client secret')}
              <input
                type="password"
                value={clientSecret}
                onChange={(e) => setClientSecret(e.target.value)}
                required
              />
            </label>
          </>
        )}
        <button type="submit" disabled={busy}>
          {busy ? t('databricks.wizard.attaching', 'Attaching...') : t('databricks.wizard.attach_credential', 'Attach credential')}
        </button>
      </form>
    );
  }

  return (
    <div
      className="warehouse-wizard"
      data-testid="databricks-register-wizard"
      aria-busy={busy}
    >
      <h3 aria-current="step">{t('databricks.wizard.step_test_title', 'Test connection')}</h3>
      {workspace?.status === 'ACTIVE' ? (
        <div data-testid="databricks-active" className="success">
          <p>
            <strong>{workspace.name}</strong> is <strong>Active</strong>
            {latencyMs !== null && <> (probe latency: {latencyMs} ms)</>}.
          </p>
        </div>
      ) : (
        <>
          {errorNode}
          <p>
            {t('databricks.wizard.test_body', 'The Hub probes the workspace with the stored credential. A healthy workspace becomes ACTIVE.')}
          </p>
          <button
            type="button"
            disabled={busy}
            onClick={() => workspace && runTest(workspace.id)}
          >
            {busy ? t('databricks.wizard.testing', 'Testing...') : t('databricks.wizard.retry_test', 'Retry test')}
          </button>
          <button
            type="button"
            className="secondary"
            disabled={busy}
            onClick={handleChangeCredential}
          >
            ← Change credential
          </button>
        </>
      )}
      <DirtyStateGuard dirty={dirty} />
    </div>
  );
}

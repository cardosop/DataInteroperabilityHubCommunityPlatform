/**
 * WorkspaceRegistrationWizard tests — the guided U1 flow
 * (register → App-connection instructions → test → active).
 *
 * Pins the step machine contract:
 *  - step 1 registers the workspace (name/host/cloud/region),
 *  - step 2 shows the App-connection instructions and creates the
 *    credential (PAT or OAuth M2M),
 *  - step 3 tests the connection: success → ACTIVE + latency; masked
 *    failure → the backend's human message + a Retry affordance,
 *  - backend validation errors (e.g. DATABRICKS_HOST_NOT_ALLOWED)
 *    surface with their code.
 */
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { createMemoryRouter, RouterProvider } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { DatabricksApiError } from '../services/databricksService';
import { WorkspaceRegistrationWizard } from './WorkspaceRegistrationWizard';

vi.mock('../services/databricksService', () => ({
  DatabricksApiError: class extends Error {
    code?: string;
    constructor(message: string, code?: string) {
      super(message);
      this.code = code;
    }
  },
  createWorkspace: vi.fn(),
  createCredential: vi.fn(),
  testWorkspace: vi.fn(),
}));

import {
  createCredential,
  createWorkspace,
  testWorkspace,
} from '../services/databricksService';

const mockCreate = vi.mocked(createWorkspace);

// W5.4 — the wizard renders DirtyStateGuard, which requires the data
// router (useBlocker). Standalone renders wrap in a memory data router,
// the same context the app provides via createBrowserRouter.
function renderWizard(onSaved: () => void) {
  const router = createMemoryRouter(
    [{ path: '/', element: <WorkspaceRegistrationWizard onSaved={onSaved} /> }],
    { initialEntries: ['/'] },
  );
  return render(<RouterProvider router={router} />);
}
const mockCredential = vi.mocked(createCredential);
const mockTest = vi.mocked(testWorkspace);

beforeEach(() => {
  vi.clearAllMocks();
});

async function fillStepOne(): Promise<void> {
  await userEvent.type(
    screen.getByLabelText(/Workspace name/i),
    'prod-analytics'
  );
  await userEvent.type(
    screen.getByLabelText(/Workspace host/i),
    'dbc-111.cloud.databricks.com'
  );
  await userEvent.selectOptions(screen.getByLabelText(/Cloud/i), 'AWS');
  await userEvent.type(screen.getByLabelText(/Region/i), 'us-east-1');
  await userEvent.click(screen.getByRole('button', { name: /Continue/ }));
}

describe('WorkspaceRegistrationWizard', () => {
  it('registers the workspace from step 1 and advances to the connection instructions', async () => {
    mockCreate.mockResolvedValue({
      id: 'w1',
      tenant: 't1',
      name: 'prod-analytics',
      host: 'dbc-111.cloud.databricks.com',
      cloud: 'AWS',
      region: 'us-east-1',
      metastore_id: null,
      status: 'REGISTERED',
      status_display: 'Registered',
      created_at: '2026-09-01T00:00:00Z',
      updated_at: '2026-09-01T00:00:00Z',
    });
    render(
      <WorkspaceRegistrationWizard
        onSaved={vi.fn()}
      />
    );
    await fillStepOne();
    expect(mockCreate).toHaveBeenCalledWith({
      name: 'prod-analytics',
      host: 'dbc-111.cloud.databricks.com',
      cloud: 'AWS',
      region: 'us-east-1',
    });
    // Step 2 — App-connection instructions.
    expect(
      await screen.findByText(/Connect your app/i)
    ).toBeInTheDocument();
  });

  it('creates a PAT credential in step 2 and tests in step 3 → ACTIVE', async () => {
    mockCreate.mockResolvedValue({
      id: 'w1',
      tenant: 't1',
      name: 'prod-analytics',
      host: 'dbc-111.cloud.databricks.com',
      cloud: 'AWS',
      region: 'us-east-1',
      metastore_id: null,
      status: 'REGISTERED',
      status_display: 'Registered',
      created_at: '2026-09-01T00:00:00Z',
      updated_at: '2026-09-01T00:00:00Z',
    });
    mockCredential.mockResolvedValue({
      id: 'c1',
      workspace: 'w1',
      auth_mode: 'PAT',
      auth_mode_display: 'Personal Access Token',
      expires_at: null,
      last_rotated_at: null,
      created_at: '2026-09-01T00:00:00Z',
      updated_at: '2026-09-01T00:00:00Z',
    });
    mockTest.mockResolvedValue({ status: 'ok', latency_ms: 34 });

    renderWizard(vi.fn());
    await fillStepOne();

    await userEvent.type(screen.getByLabelText(/Personal access token/i), 'dapi-secret');
    await userEvent.click(screen.getByRole('button', { name: /Attach credential/ }));

    expect(mockCredential).toHaveBeenCalledWith('w1', {
      auth_mode: 'PAT',
      config: { token: 'dapi-secret' },
    });

    // Step 3 — test connection → ACTIVE + latency.
    expect(await screen.findByText(/Active/)).toBeInTheDocument();
    expect(mockTest).toHaveBeenCalledWith('w1');
    expect(await screen.findByText(/34/)).toBeInTheDocument();
  });

  it('surfaces backend validation errors with their code', async () => {
    mockCreate.mockRejectedValue(
      new DatabricksApiError(
        "Host 'attacker.example.com' is not a Databricks workspace host.",
        'DATABRICKS_HOST_NOT_ALLOWED'
      )
    );
    renderWizard(vi.fn());
    await fillStepOne();
    expect(
      await screen.findByText(/DATABRICKS_HOST_NOT_ALLOWED/)
    ).toBeInTheDocument();
  });

  it('shows the masked test failure and a retry affordance', async () => {
    mockCreate.mockResolvedValue({
      id: 'w1',
      tenant: 't1',
      name: 'prod-analytics',
      host: 'dbc-111.cloud.databricks.com',
      cloud: 'AWS',
      region: 'us-east-1',
      metastore_id: null,
      status: 'REGISTERED',
      status_display: 'Registered',
      created_at: '2026-09-01T00:00:00Z',
      updated_at: '2026-09-01T00:00:00Z',
    });
    mockCredential.mockResolvedValue({
      id: 'c1',
      workspace: 'w1',
      auth_mode: 'PAT',
      auth_mode_display: 'Personal Access Token',
      expires_at: null,
      last_rotated_at: null,
      created_at: '2026-09-01T00:00:00Z',
      updated_at: '2026-09-01T00:00:00Z',
    });
    mockTest.mockRejectedValue(
      new DatabricksApiError(
        'Credentials rejected by workspace',
        'DATABRICKS_AUTH_FAILED'
      )
    );
    renderWizard(vi.fn());
    await fillStepOne();
    await userEvent.type(screen.getByLabelText(/Personal access token/i), 'dapi-bad');
    await userEvent.click(screen.getByRole('button', { name: /Attach credential/ }));

    expect(
      await screen.findByText(/Credentials rejected by workspace/)
    ).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: /Retry test/i })
    ).toBeInTheDocument();
  });

  it('offers a path back to the credentials step after a failed test', async () => {
    mockCreate.mockResolvedValue({
      id: 'w1',
      tenant: 't1',
      name: 'prod-analytics',
      host: 'dbc-111.cloud.databricks.com',
      cloud: 'AWS',
      region: 'us-east-1',
      metastore_id: null,
      status: 'REGISTERED',
      status_display: 'Registered',
      created_at: '2026-09-01T00:00:00Z',
      updated_at: '2026-09-01T00:00:00Z',
    });
    mockCredential.mockResolvedValue({
      id: 'c1',
      workspace: 'w1',
      auth_mode: 'PAT',
      auth_mode_display: 'Personal Access Token',
      expires_at: null,
      last_rotated_at: null,
      created_at: '2026-09-01T00:00:00Z',
      updated_at: '2026-09-01T00:00:00Z',
    });
    mockTest.mockRejectedValue(
      new DatabricksApiError(
        'Credentials rejected by workspace',
        'DATABRICKS_AUTH_FAILED'
      )
    );
    renderWizard(vi.fn());
    await fillStepOne();
    await userEvent.type(screen.getByLabelText(/Personal access token/i), 'dapi-bad');
    await userEvent.click(screen.getByRole('button', { name: /Attach credential/ }));
    await screen.findByText(/Credentials rejected by workspace/);

    // A failed test must not trap the user in an infinite retry loop with
    // the same broken credential — back to step 2, secrets cleared.
    await userEvent.click(
      screen.getByRole('button', { name: /Change credential/ })
    );
    expect(await screen.findByText(/Connect your app/i)).toBeInTheDocument();
    await userEvent.type(
      screen.getByLabelText(/Personal access token/i),
      'dapi-good'
    );
    await userEvent.click(screen.getByRole('button', { name: /Attach credential/ }));
    expect(mockCredential).toHaveBeenCalledTimes(2);
    expect(mockCredential).toHaveBeenLastCalledWith('w1', {
      auth_mode: 'PAT',
      config: { token: 'dapi-good' },
    });
  });
});

describe('WorkspaceRegistrationWizard — a11y + i18n (task 0.18)', () => {
  const workspace = {
    id: 'w1',
    tenant: 't1',
    name: 'prod-analytics',
    host: 'dbc-111.cloud.databricks.com',
    cloud: 'AWS' as const,
    region: 'us-east-1',
    metastore_id: null,
    status: 'REGISTERED' as const,
    status_display: 'Registered',
    created_at: '2026-09-01T00:00:00Z',
    updated_at: '2026-09-01T00:00:00Z',
  };

  it('marks the active step heading with aria-current="step"', async () => {
    mockCreate.mockResolvedValue(workspace);
    renderWizard(vi.fn());
    expect(
      screen.getByRole('heading', { name: /Register Databricks workspace/ })
    ).toHaveAttribute('aria-current', 'step');
  });

  it('surfaces aria-busy on the form while a step is submitting', async () => {
    let resolveCreate!: (value: unknown) => void;
    mockCreate.mockReturnValue(new Promise((resolve) => (resolveCreate = resolve)));
    renderWizard(vi.fn());
    await fillStepOne();
    expect(
      screen.getByTestId('databricks-register-wizard')
    ).toHaveAttribute('aria-busy', 'true');
    resolveCreate(workspace);
    await screen.findByText(/Connect your app/i);
    expect(
      screen.getByTestId('databricks-register-wizard')
    ).toHaveAttribute('aria-busy', 'false');
  });

  it('registers the databricks.* namespace in the en locale registry', async () => {
    const { ALL_I18N_EN } = await import('../../../shared/i18n/locales/en');
    for (const key of [
      'databricks.wizard.step_register_title',
      'databricks.wizard.name_label',
      'databricks.wizard.host_label',
      'databricks.wizard.step_credentials_title',
      'databricks.wizard.step_test_title',
      'databricks.page.title',
      'databricks.page.register_cta',
    ]) {
      expect(ALL_I18N_EN[key], `${key} missing from en locale`).toBeTruthy();
    }
  });
});

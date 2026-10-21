/**
 * WorkspaceManagementPage tests (openspec add-databricks-control-plane
 * task 0.15).
 *
 * UI contract pins:
 *  - the registered workspace list renders name/host/status,
 *  - the empty state surfaces the "Register workspace" call-to-action,
 *  - a 403 DATABRICKS_CONTROL_PLANE_DISABLED renders a DISTINCT banner
 *    with the code (JOURNEY-DB-001 step 1) — not a generic error.
 */
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { DatabricksApiError } from '../services/databricksService';
import { WorkspaceManagementPage } from './WorkspaceManagementPage';

vi.mock('../services/databricksService', () => ({
  DatabricksApiError: class extends Error {
    code?: string;
    constructor(message: string, code?: string) {
      super(message);
      this.code = code;
    }
  },
  listWorkspaces: vi.fn(),
  testWorkspace: vi.fn(),
}));

import { listWorkspaces } from '../services/databricksService';

const mockList = vi.mocked(listWorkspaces);

beforeEach(() => {
  vi.clearAllMocks();
});

describe('WorkspaceManagementPage', () => {
  it('renders registered workspaces with name, host, and status', async () => {
    mockList.mockResolvedValue([
      {
        id: 'w1',
        tenant: 't1',
        name: 'prod-analytics',
        host: 'dbc-111.cloud.databricks.com',
        cloud: 'AWS',
        region: 'us-east-1',
        metastore_id: null,
        status: 'ACTIVE',
        status_display: 'Active',
        created_at: '2026-09-01T00:00:00Z',
        updated_at: '2026-09-01T00:00:00Z',
      },
    ]);
    render(
      <MemoryRouter>
        <WorkspaceManagementPage />
      </MemoryRouter>
    );
    expect(await screen.findByText('prod-analytics')).toBeInTheDocument();
    expect(screen.getByText('dbc-111.cloud.databricks.com')).toBeInTheDocument();
    expect(screen.getByText(/Active/)).toBeInTheDocument();
  });

  it('renders the register call-to-action in the empty state', async () => {
    mockList.mockResolvedValue([]);
    render(
      <MemoryRouter>
        <WorkspaceManagementPage />
      </MemoryRouter>
    );
    expect(await screen.findByText(/No Databricks workspaces/)).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: /Register workspace/i })
    ).toBeInTheDocument();
  });

  it('surfaces the DATABRICKS_CONTROL_PLANE_DISABLED banner distinctly', async () => {
    mockList.mockRejectedValue(
      new DatabricksApiError(
        'Databricks control plane is disabled for this tenant',
        'DATABRICKS_CONTROL_PLANE_DISABLED'
      )
    );
    render(
      <MemoryRouter>
        <WorkspaceManagementPage />
      </MemoryRouter>
    );
    const banner = await screen.findByTestId('databricks-flag-disabled');
    expect(banner).toHaveTextContent('DATABRICKS_CONTROL_PLANE_DISABLED');
    // A disabled tenant gets NO register CTA.
    expect(
      screen.queryByRole('button', { name: /Register workspace/i })
    ).not.toBeInTheDocument();
  });

  it('opens the registration wizard from the CTA and refreshes the list on save', async () => {
    mockList.mockResolvedValue([]);
    render(
      <MemoryRouter>
        <WorkspaceManagementPage />
      </MemoryRouter>
    );
    const cta = await screen.findByRole('button', { name: /Register workspace/i });
    await userEvent.click(cta);
    // The wizard's first step is visible.
    expect(await screen.findByTestId('databricks-register-wizard')).toBeInTheDocument();
  });

  it('shows the masked test failure WITH its machine-readable code', async () => {
    const ws = {
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
    mockList.mockResolvedValue([ws]);
    const { testWorkspace } = await import('../services/databricksService');
    const mockTest = vi.mocked(testWorkspace);
    mockTest.mockRejectedValue(
      new DatabricksApiError(
        'Credentials rejected by workspace',
        'DATABRICKS_AUTH_FAILED'
      )
    );
    render(
      <MemoryRouter>
        <WorkspaceManagementPage />
      </MemoryRouter>
    );
    await userEvent.click(await screen.findByRole('button', { name: /Test/ }));
    // The wizard surfaces codes — the page's alert must keep parity so
    // operators can search the code in runbooks.
    expect(
      await screen.findByText(/DATABRICKS_AUTH_FAILED/)
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Credentials rejected by workspace/)
    ).toBeInTheDocument();
  });

  it('runs the connection test from the row action and reloads the list', async () => {
    const ws = {
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
    mockList.mockResolvedValue([ws]);
    const { testWorkspace } = await import('../services/databricksService');
    const mockTest = vi.mocked(testWorkspace);
    mockTest.mockResolvedValue({ status: 'ok', latency_ms: 5 });

    render(
      <MemoryRouter>
        <WorkspaceManagementPage />
      </MemoryRouter>
    );
    await userEvent.click(await screen.findByRole('button', { name: /Test/ }));
    expect(mockTest).toHaveBeenCalledWith('w1');
    expect(mockList).toHaveBeenCalledTimes(2); // initial load + post-test reload
  });
});

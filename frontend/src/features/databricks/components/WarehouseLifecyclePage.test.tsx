/**
 * WarehouseLifecyclePage tests (openspec add-databricks-sql-warehouses
 * task 3.7) — the U5 non-blocking lifecycle contract.
 *
 * UI contract pins:
 *  - the mirror list renders each warehouse with its state, type and size,
 *  - Start/Stop are offered per state (never on DELETING),
 *  - an action is NON-BLOCKING: the row flips to in-flight (aria-busy,
 *    button disabled) while the call is in flight and renders the NEW
 *    state when it lands,
 *  - a failed action renders the machine-readable CODE in the alert
 *    (the 0.15 review parity fix),
 *  - a 403 DATABRICKS_CONTROL_PLANE_DISABLED renders the flag banner.
 */
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { DatabricksApiError, listWarehouses, startWarehouse } from '../services/warehouseService';
import { WarehouseLifecyclePage } from './WarehouseLifecyclePage';

vi.mock('../services/warehouseService', () => ({
  DatabricksApiError: class extends Error {
    code?: string;
    constructor(message: string, code?: string) {
      super(message);
      this.code = code;
    }
  },
  listWarehouses: vi.fn(),
  startWarehouse: vi.fn(),
  stopWarehouse: vi.fn(),
}));

const mockList = vi.mocked(listWarehouses);
const mockStart = vi.mocked(startWarehouse);

const STOPPED_ROW = {
  warehouse_id: 'wh-1',
  name: 'analytics',
  state: 'STOPPED',
  serverless: true,
  size: null,
  auto_stop_mins: 30,
};

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/databricks/workspaces/ws-1/warehouses']}>
      <Routes>
        <Route path="/databricks/workspaces/:workspaceId/warehouses" element={<WarehouseLifecyclePage />} />
      </Routes>
    </MemoryRouter>
  );
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe('WarehouseLifecyclePage', () => {
  it('renders each warehouse with its state, type and size', async () => {
    mockList.mockResolvedValue([
      STOPPED_ROW,
      { ...STOPPED_ROW, warehouse_id: 'wh-2', name: 'etl', state: 'RUNNING', serverless: false, size: 'M' },
    ]);
    renderPage();

    await screen.findByText('analytics');
    expect(screen.getByText('STOPPED')).toBeInTheDocument();
    expect(screen.getByText('etl')).toBeInTheDocument();
    expect(screen.getByText('RUNNING')).toBeInTheDocument();
    expect(screen.getByText('serverless')).toBeInTheDocument();
    expect(screen.getByText('M')).toBeInTheDocument();
  });

  it('offers Start for a STOPPED row and Stop for a RUNNING row — never for DELETING', async () => {
    mockList.mockResolvedValue([
      STOPPED_ROW,
      { ...STOPPED_ROW, warehouse_id: 'wh-2', name: 'etl', state: 'RUNNING' },
      { ...STOPPED_ROW, warehouse_id: 'wh-3', name: 'gone', state: 'DELETING' },
    ]);
    renderPage();

    await screen.findByText('analytics');
    expect(screen.getAllByText('Start').length).toBe(1);
    expect(screen.getAllByText('Stop').length).toBe(1);
    expect(screen.queryByText('Start', { selector: 'button[data-warehouse="wh-3"]' })).toBeNull();
  });

  it('runs an action non-blocking: in-flight first, then the NEW state renders', async () => {
    mockList.mockResolvedValue([STOPPED_ROW]);
    let resolveStart: (row: typeof STOPPED_ROW) => void = () => {};
    mockStart.mockReturnValue(
      new Promise((resolve) => {
        resolveStart = resolve;
      })
    );
    renderPage();

    await screen.findByText('analytics');
    const user = userEvent.setup();
    await user.click(screen.getByText('Start'));

    // Non-blocking: the row is in-flight while the call is pending.
    await waitFor(() => {
      expect(screen.getByText('Start', { selector: 'button' })).toBeDisabled();
    });

    resolveStart({ ...STOPPED_ROW, state: 'STARTING' });
    await waitFor(() => {
      expect(screen.getByText('STARTING')).toBeInTheDocument();
    });
  });

  it('renders the machine-readable code in the failure alert', async () => {
    mockList.mockResolvedValue([STOPPED_ROW]);
    mockStart.mockRejectedValue(
      new DatabricksApiError('Warehouse start failed', 'DATABRICKS_AUTH_FAILED')
    );
    renderPage();

    await screen.findByText('analytics');
    const user = userEvent.setup();
    await user.click(screen.getByText('Start'));

    await waitFor(() => {
      expect(screen.getByText(/DATABRICKS_AUTH_FAILED/)).toBeInTheDocument();
    });
  });

  it('surfaces the flag-disabled banner with its code', async () => {
    mockList.mockRejectedValue(
      new DatabricksApiError('databricks control plane disabled', 'DATABRICKS_CONTROL_PLANE_DISABLED')
    );
    renderPage();

    await waitFor(() => {
      expect(screen.getByText(/DATABRICKS_CONTROL_PLANE_DISABLED/)).toBeInTheDocument();
    });
  });
});

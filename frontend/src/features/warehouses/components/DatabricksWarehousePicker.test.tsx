/**
 * DatabricksWarehousePicker tests (openspec wire-databricks-dlt-movement
 * task 6.8, design D8) — the workspace+warehouse picker replacing the
 * placeholder http_path.
 *
 * UI contract pins:
 *  - the picker renders the workspace list from the real API service,
 *  - selecting a workspace loads its mirrored SQL warehouses,
 *  - selecting a warehouse emits the DERIVED `/sql/1.0/warehouses/{id}`
 *    path (the 3.6 derivation contract — the STORED value),
 *  - the chosen workspace's host rides along for the source config,
 *  - NO free-text http_path input exists — the path is never hand-typed,
 *  - editing a stored path pre-selects the matching warehouse,
 *  - a failed warehouse load renders the machine-readable CODE.
 *
 * The sanctioned seams are the service modules (the repo's frontend
 * convention — the UI logic itself is real).
 */
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { DatabricksApiError, listWarehouses } from '../../databricks/services/warehouseService';
import { listWorkspaces } from '../../databricks/services/databricksService';
import { DatabricksWarehousePicker } from './DatabricksWarehousePicker';
import { deriveWarehouseHttpPath, warehouseIdFromHttpPath } from '../httpPath';

vi.mock('../../databricks/services/warehouseService', () => ({
  DatabricksApiError: class extends Error {
    code?: string;
    constructor(message: string, code?: string) {
      super(message);
      this.code = code;
    }
  },
  listWarehouses: vi.fn(),
}));

vi.mock('../../databricks/services/databricksService', () => ({
  listWorkspaces: vi.fn(),
}));

const mockWorkspaces = vi.mocked(listWorkspaces);
const mockWarehouses = vi.mocked(listWarehouses);

const WORKSPACE_A = {
  id: 'ws-1',
  tenant: 't-1',
  name: 'Prod Workspace',
  host: 'prod.cloud.databricks.com',
  cloud: 'AWS',
  region: 'us-east-1',
  metastore_id: null,
  status: 'ACTIVE',
  status_display: 'Active',
  created_at: '2026-01-01T00:00:00Z',
};

const WAREHOUSE_1 = {
  warehouse_id: 'wh-1',
  name: 'analytics',
  state: 'RUNNING',
  serverless: true,
  size: null,
  auto_stop_mins: 30,
};

const WAREHOUSE_2 = {
  warehouse_id: 'wh-2',
  name: 'etl',
  state: 'STOPPED',
  serverless: false,
  size: 'Large',
  auto_stop_mins: 15,
};

function renderPicker(props: Partial<Parameters<typeof DatabricksWarehousePicker>[0]> = {}) {
  const onChange = props.onChange ?? vi.fn();
  const onHostChange = props.onHostChange ?? vi.fn();
  const utils = render(
    <DatabricksWarehousePicker
      onChange={onChange}
      onHostChange={onHostChange}
      value={props.value}
    />,
  );
  return { onChange, onHostChange, ...utils };
}

beforeEach(() => {
  vi.clearAllMocks();
  mockWorkspaces.mockResolvedValue([WORKSPACE_A]);
  mockWarehouses.mockResolvedValue([WAREHOUSE_1, WAREHOUSE_2]);
});

describe('DatabricksWarehousePicker', () => {
  it('renders the workspace list from the API', async () => {
    renderPicker();

    await waitFor(() =>
      expect(screen.getByRole('option', { name: 'Prod Workspace' })).toBeTruthy(),
    );
    expect(mockWorkspaces).toHaveBeenCalledTimes(1);
  });

  it('loads the warehouses of the selected workspace', async () => {
    renderPicker();
    await waitFor(() => expect(screen.getByRole('combobox', { name: /workspace/i })).toBeTruthy());

    await userEvent.selectOptions(
      screen.getByRole('combobox', { name: /workspace/i }),
      'ws-1',
    );

    await waitFor(() => expect(screen.getByRole('option', { name: 'analytics' })).toBeTruthy());
    expect(mockWarehouses).toHaveBeenCalledWith('ws-1');
  });

  it('emits the DERIVED http_path when a warehouse is selected', async () => {
    const { onChange } = renderPicker();
    await waitFor(() => expect(screen.getByRole('combobox', { name: /workspace/i })).toBeTruthy());

    await userEvent.selectOptions(
      screen.getByRole('combobox', { name: /workspace/i }),
      'ws-1',
    );
    await waitFor(() => expect(screen.getByRole('combobox', { name: /warehouse/i })).toBeTruthy());

    await userEvent.selectOptions(
      screen.getByRole('combobox', { name: /warehouse/i }),
      'wh-2',
    );

    expect(onChange).toHaveBeenCalledWith('/sql/1.0/warehouses/wh-2');
  });

  it('emits the workspace host for the source config', async () => {
    const { onHostChange } = renderPicker();
    await waitFor(() => expect(screen.getByRole('combobox', { name: /workspace/i })).toBeTruthy());

    await userEvent.selectOptions(
      screen.getByRole('combobox', { name: /workspace/i }),
      'ws-1',
    );

    expect(onHostChange).toHaveBeenCalledWith('prod.cloud.databricks.com');
  });

  it('has NO free-text http_path input — the path is never hand-typed', async () => {
    renderPicker();
    await waitFor(() => expect(screen.getByRole('combobox', { name: /workspace/i })).toBeTruthy());

    const textboxes = screen.queryAllByRole('textbox');
    const pathInputs = textboxes.filter(
      (el) =>
        /http.?path/i.test((el as HTMLInputElement).getAttribute('name') ?? '') ||
        /sql\/1\.0\/warehouses/i.test((el as HTMLInputElement).placeholder ?? ''),
    );
    expect(pathInputs).toHaveLength(0);
  });

  it('editing a stored path pre-selects the matching warehouse', async () => {
    renderPicker({ value: '/sql/1.0/warehouses/wh-1' });
    await waitFor(() => expect(screen.getByRole('combobox', { name: /workspace/i })).toBeTruthy());

    // The stored path carries only the warehouse id — the workspace picker
    // stays on the placeholder until the user picks one; the warehouse
    // select pre-selects once its list loads.
    await userEvent.selectOptions(
      screen.getByRole('combobox', { name: /workspace/i }),
      'ws-1',
    );
    await waitFor(() =>
      expect(screen.getByRole('combobox', { name: /warehouse/i })).toHaveValue('wh-1'),
    );
  });

  it('renders the machine-readable CODE when the warehouse list fails', async () => {
    mockWarehouses.mockRejectedValue(
      new DatabricksApiError('Control plane disabled', 'DATABRICKS_CONTROL_PLANE_DISABLED'),
    );
    renderPicker();
    await waitFor(() => expect(screen.getByRole('combobox', { name: /workspace/i })).toBeTruthy());

    await userEvent.selectOptions(
      screen.getByRole('combobox', { name: /workspace/i }),
      'ws-1',
    );

    await waitFor(() =>
      expect(screen.getByText(/DATABRICKS_CONTROL_PLANE_DISABLED/)).toBeTruthy(),
    );
  });
});

describe('the 3.6 http_path derivation helpers', () => {
  it('derives the stored path and parses it back', () => {
    const path = deriveWarehouseHttpPath('wh-9');
    expect(path).toBe('/sql/1.0/warehouses/wh-9');
    expect(warehouseIdFromHttpPath(path)).toBe('wh-9');
  });

  it('parses non-path values to undefined (never a hand-typed string)', () => {
    expect(warehouseIdFromHttpPath('anything-else')).toBeUndefined();
    expect(warehouseIdFromHttpPath('/sql/1.0/warehouses/')).toBeUndefined();
  });
});

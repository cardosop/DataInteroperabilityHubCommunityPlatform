/**
 * Pins for CatalogBrowserPage (openspec add-databricks-control-plane
 * task 1.9) — the U3 catalog browser: breadcrumbs, search, kind
 * filters, virtual scrolling, per-table live effective permissions,
 * and the mirror-freshness marker.
 *
 * The service layer is stubbed at the module boundary (the wire
 * contract is pinned by ucCatalogService.test.ts); these pins drive
 * the real component state machine through user events.
 */
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { CatalogBrowserPage } from './CatalogBrowserPage';

vi.mock('../services/ucCatalogService', () => ({
  listCatalogs: vi.fn(),
  listSchemas: vi.fn(),
  listTables: vi.fn(),
  listExternalLocations: vi.fn(),
  listStorageCredentials: vi.fn(),
  getTableDetail: vi.fn(),
  DatabricksApiError: class DatabricksApiError extends Error {
    readonly code?: string;
    readonly httpStatus?: number;
    constructor(message: string, code?: string, httpStatus?: number) {
      super(message);
      this.name = 'DatabricksApiError';
      this.code = code;
      this.httpStatus = httpStatus;
    }
  },
}));

import {
  getTableDetail,
  listCatalogs,
  listSchemas,
  listTables,
} from '../services/ucCatalogService';

const mockCatalogs = vi.mocked(listCatalogs);
const mockSchemas = vi.mocked(listSchemas);
const mockTables = vi.mocked(listTables);
const mockDetail = vi.mocked(getTableDetail);

const SYNC_FRESH = new Date().toISOString();
const SYNC_STALE = new Date(Date.now() - 25 * 3600 * 1000).toISOString();

const CATALOGS = [
  { id: 'c1', name: 'main', catalog_type: 'MANAGED', full_name: 'main', synced_at: SYNC_FRESH },
  {
    id: 'c2',
    name: 'analytics',
    catalog_type: 'MANAGED',
    full_name: 'analytics',
    synced_at: SYNC_STALE,
  },
];

const SCHEMAS = [
  { id: 's1', name: 'sales', full_name: 'main.sales', synced_at: SYNC_FRESH },
];

const TABLES = [
  {
    id: 't1',
    name: 'orders',
    table_type: 'MANAGED',
    full_name: 'main.sales.orders',
    synced_at: SYNC_FRESH,
  },
];

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/databricks/workspaces/ws-1/catalog']}>
      <Routes>
        <Route
          path="/databricks/workspaces/:workspaceId/catalog"
          element={<CatalogBrowserPage />}
        />
      </Routes>
    </MemoryRouter>
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  mockCatalogs.mockResolvedValue(CATALOGS);
  mockSchemas.mockResolvedValue(SCHEMAS);
  mockTables.mockResolvedValue(TABLES);
  mockDetail.mockResolvedValue({
    id: 't1',
    name: 'orders',
    table_type: 'MANAGED',
    full_name: 'main.sales.orders',
    catalog: 'main',
    schema: 'sales',
    columns: [
      { name: 'id', type_text: 'BIGINT' },
      { name: 'total', type_text: 'DECIMAL(18,2)' },
    ],
    owner: 'admin@example.com',
    synced_at: SYNC_FRESH,
    effective_permissions: {
      privilege_assignments: [{ principal: 'admin@example.com', privileges: ['SELECT'] }],
    },
  });
});

describe('CatalogBrowserPage breadcrumbs', () => {
  it('renders the root breadcrumb and the current level', async () => {
    renderPage();
    expect(await screen.findByText('main')).toBeInTheDocument();
    const nav = screen.getByRole('navigation', { name: /catalog breadcrumbs/i });
    expect(nav).toBeInTheDocument();
  });

  it('drills catalog → schema and marks the current crumb', async () => {
    const user = userEvent.setup();
    renderPage();
    await user.click(await screen.findByText('main'));
    expect(await screen.findByText('main.sales')).toBeInTheDocument();
    expect(mockSchemas).toHaveBeenCalledWith('ws-1', 'c1');
    const current = screen.getByRole('navigation').querySelector('[aria-current="page"]');
    expect(current?.textContent).toContain('main');
  });

  it('the catalog crumb navigates back to the catalog level', async () => {
    const user = userEvent.setup();
    renderPage();
    await user.click(await screen.findByText('main'));
    await screen.findByText('main.sales');
    // The 'Catalog' crumb navigates back to the catalogs level.
    await user.click(screen.getByRole('button', { name: 'Catalog' }));
    expect(await screen.findByText('analytics')).toBeInTheDocument();
  });
});

describe('CatalogBrowserPage search and filters', () => {
  it('filters the current list client-side by name', async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByText('analytics');
    await user.type(screen.getByRole('searchbox', { name: /search/i }), 'analyt');
    expect(screen.getByText('analytics')).toBeInTheDocument();
    expect(screen.queryByText('main')).not.toBeInTheDocument();
  });

  it('kind tabs filter the schema-scoped listing', async () => {
    const user = userEvent.setup();
    renderPage();
    await user.click(await screen.findByText('main'));
    await user.click(await screen.findByText('main.sales'));
    expect(await screen.findByText('main.sales.orders')).toBeInTheDocument();
    expect(mockTables).toHaveBeenLastCalledWith('ws-1', 's1', 'tables');
    await user.click(screen.getByRole('tab', { name: /views/i }));
    expect(mockTables).toHaveBeenLastCalledWith('ws-1', 's1', 'views');
  });
});

describe('CatalogBrowserPage virtual scrolling', () => {
  it('renders only the windowed subset of a long listing', async () => {
    const many = Array.from({ length: 500 }, (_, i) => ({
      id: `t${i}`,
      name: `table_${i}`,
      table_type: 'MANAGED',
      full_name: `main.sales.table_${i}`,
      synced_at: SYNC_FRESH,
    }));
    mockTables.mockResolvedValue(many);
    const user = userEvent.setup();
    renderPage();
    await user.click(await screen.findByText('main'));
    await user.click(await screen.findByText('main.sales'));
    await screen.findByText('main.sales.table_0');
    // A row far outside the initial window must NOT be in the DOM —
    // react-window virtualizes (no full 500-row render).
    expect(screen.queryByText('main.sales.table_499')).not.toBeInTheDocument();
  });
});

describe('CatalogBrowserPage table detail + permissions', () => {
  it('opens the detail panel with columns and the live effective permissions', async () => {
    const user = userEvent.setup();
    renderPage();
    await user.click(await screen.findByText('main'));
    await user.click(await screen.findByText('main.sales'));
    await user.click(await screen.findByText('main.sales.orders'));
    const panel = await screen.findByTestId('uc-table-detail');
    expect(panel).toHaveTextContent('main.sales.orders');
    expect(panel).toHaveTextContent(/id — BIGINT/);
    expect(panel).toHaveTextContent(/total — DECIMAL\(18,2\)/);
    expect(panel).toHaveTextContent('admin@example.com');
    expect(panel).toHaveTextContent('SELECT');
  });

  it('surfaces the fail-closed OBO code when the permissions call fails', async () => {
    const { DatabricksApiError } = await import('../services/ucCatalogService');
    mockDetail.mockRejectedValue(
      new DatabricksApiError('sign in with Databricks', 'DATABRICKS_OBO_REFRESH_FAILED', 502)
    );
    const user = userEvent.setup();
    renderPage();
    await user.click(await screen.findByText('main'));
    await user.click(await screen.findByText('main.sales'));
    await user.click(await screen.findByText('main.sales.orders'));
    expect(await screen.findByText(/DATABRICKS_OBO_REFRESH_FAILED/)).toBeInTheDocument();
  });
});

describe('CatalogBrowserPage a11y', () => {
  it('rows are real buttons — keyboard users can drill in', async () => {
    const user = userEvent.setup();
    renderPage();
    const rowButton = await screen.findByRole('button', { name: /main/ });
    await user.click(rowButton);
    expect(await screen.findByText('main.sales')).toBeInTheDocument();
    expect(mockSchemas).toHaveBeenCalledWith('ws-1', 'c1');
  });

  it('kind tabs move the selection with arrow keys (APG)', async () => {
    const user = userEvent.setup();
    renderPage();
    await user.click(await screen.findByText('main'));
    await user.click(await screen.findByText('main.sales'));
    await screen.findByText('main.sales.orders');
    const tablesTab = screen.getByRole('tab', { name: /tables/i });
    tablesTab.focus();
    await user.keyboard('{ArrowRight}');
    expect(screen.getByRole('tab', { name: /views/i })).toHaveAttribute(
      'aria-selected',
      'true'
    );
    expect(mockTables).toHaveBeenLastCalledWith('ws-1', 's1', 'views');
  });

  it('an empty effective-permissions answer renders None (not blank)', async () => {
    mockDetail.mockResolvedValue({
      id: 't1',
      name: 'orders',
      table_type: 'MANAGED',
      full_name: 'main.sales.orders',
      catalog: 'main',
      schema: 'sales',
      columns: [],
      owner: 'admin@example.com',
      synced_at: SYNC_FRESH,
      effective_permissions: { privilege_assignments: [] },
    });
    const user = userEvent.setup();
    renderPage();
    await user.click(await screen.findByText('main'));
    await user.click(await screen.findByText('main.sales'));
    await user.click(await screen.findByText('main.sales.orders'));
    const panel = await screen.findByTestId('uc-table-detail');
    expect(panel).toHaveTextContent('None');
  });
});

describe('CatalogBrowserPage freshness marker', () => {
  it('marks ONLY the stale mirror rows', async () => {
    renderPage();
    await screen.findByText('analytics');
    // analytics synced 25h ago → stale marker; main synced now → none.
    expect(screen.getAllByLabelText(/stale/i)).toHaveLength(1);
    const staleRow = screen.getByText('analytics').closest('[role="listitem"]');
    expect(staleRow?.querySelector('[aria-label*="stale"]')).not.toBeNull();
  });
});

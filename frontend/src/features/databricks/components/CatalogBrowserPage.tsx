/**
 * CatalogBrowserPage (openspec add-databricks-control-plane task 1.9)
 * — the U3 Unity Catalog browser.
 *
 * Mirror-first browse of a workspace's UC estate through the 1.3 browse
 * endpoints: catalogs → schemas → schema objects (tables/views/volumes/
 * models) with client-side search, kind tabs, react-window virtual
 * scrolling for large listings, per-table LIVE effective permissions
 * (OBO-backed — the fail-closed code surfaces), breadcrumbs, and the
 * mirror-freshness marker (stale when the row's synced_at is older than
 * the sync schedule).
 */
import { useCallback, useEffect, useMemo, useState } from 'react';
import { useParams } from 'react-router-dom';
import { List, type RowComponentProps } from 'react-window';

import { useTranslation } from '../../../shared/i18n/useTranslation';
import type {
  UCCatalog,
  UCObjectKind,
  UCSchema,
  UCTableDetail,
} from '../../../shared/types/databricks';
import {
  DatabricksApiError,
  getTableDetail,
  listCatalogs,
  listSchemas,
  listTables,
} from '../services/ucCatalogService';

/** The daily UC metadata sync schedule (task 1.5's CronJob default). */
const SYNC_STALE_AFTER_MS = 25 * 3600 * 1000;

const KINDS: UCObjectKind[] = ['tables', 'views', 'volumes', 'models'];

interface BrowseRow {
  id: string;
  name: string;
  full_name: string;
  synced_at: string | null;
}

function isStale(syncedAt: string | null): boolean {
  if (!syncedAt) {
    return true;
  }
  return Date.now() - new Date(syncedAt).getTime() > SYNC_STALE_AFTER_MS;
}

function matches(row: BrowseRow, query: string): boolean {
  if (!query) {
    return true;
  }
  const q = query.toLowerCase();
  return (
    row.name.toLowerCase().includes(q) || row.full_name.toLowerCase().includes(q)
  );
}

export function CatalogBrowserPage(): React.ReactElement {
  const { t } = useTranslation();
  const { workspaceId = '' } = useParams<{ workspaceId: string }>();

  const [catalogs, setCatalogs] = useState<UCCatalog[]>([]);
  const [schemas, setSchemas] = useState<UCSchema[]>([]);
  const [rows, setRows] = useState<BrowseRow[]>([]);
  const [level, setLevel] = useState<'catalogs' | 'schemas' | 'objects'>('catalogs');
  const [catalog, setCatalog] = useState<UCCatalog | null>(null);
  const [schema, setSchema] = useState<UCSchema | null>(null);
  const [kind, setKind] = useState<UCObjectKind>('tables');
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [detail, setDetail] = useState<UCTableDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState<DatabricksApiError | null>(null);

  const loadCatalogs = useCallback(async () => {
    setLoading(true);
    setLoadError(null);
    try {
      setCatalogs(await listCatalogs(workspaceId));
      setLevel('catalogs');
      setCatalog(null);
      setSchema(null);
      setDetail(null);
      setDetailError(null);
    } catch (err) {
      setLoadError(
        err instanceof DatabricksApiError
          ? `[${err.code ?? 'ERROR'}] ${err.message}`
          : 'Failed to load the catalog list'
      );
    } finally {
      setLoading(false);
    }
  }, [workspaceId]);

  useEffect(() => {
    void loadCatalogs();
  }, [loadCatalogs]);

  const openCatalog = useCallback(
    async (selected: UCCatalog) => {
      setLoading(true);
      setLoadError(null);
      try {
        setCatalog(selected);
        setSchemas(await listSchemas(workspaceId, selected.id));
        setLevel('schemas');
        setSchema(null);
        setDetail(null);
        setDetailError(null);
        setQuery('');
      } catch (err) {
        setLoadError(
          err instanceof DatabricksApiError
            ? `[${err.code ?? 'ERROR'}] ${err.message}`
            : 'Failed to load schemas'
        );
      } finally {
        setLoading(false);
      }
    },
    [workspaceId]
  );

  const openSchema = useCallback(
    async (selected: UCSchema, selectedKind: UCObjectKind = kind) => {
      setLoading(true);
      setLoadError(null);
      try {
        setSchema(selected);
        setKind(selectedKind);
        const objects = await listTables(workspaceId, selected.id, selectedKind);
        setRows(objects.map((o) => ({ ...o, full_name: o.full_name || o.name })));
        setLevel('objects');
        setDetail(null);
        setDetailError(null);
        setQuery('');
      } catch (err) {
        setLoadError(
          err instanceof DatabricksApiError
            ? `[${err.code ?? 'ERROR'}] ${err.message}`
            : 'Failed to load the schema objects'
        );
      } finally {
        setLoading(false);
      }
    },
    [workspaceId, kind]
  );

  const switchKind = useCallback(
    async (selectedKind: UCObjectKind) => {
      if (!schema) {
        return;
      }
      await openSchema(schema, selectedKind);
    },
    [openSchema, schema]
  );

  const openTable = useCallback(
    async (table: BrowseRow) => {
      setDetailLoading(true);
      setDetailError(null);
      setDetail(null);
      try {
        setDetail(await getTableDetail(workspaceId, table.id));
      } catch (err) {
        setDetailError(
          err instanceof DatabricksApiError ? err : new DatabricksApiError(String(err))
        );
      } finally {
        setDetailLoading(false);
      }
    },
    [workspaceId]
  );

  const visible = useMemo(() => {
    if (level === 'catalogs') {
      return catalogs
        .map((c) => ({ id: c.id, name: c.name, full_name: c.full_name, synced_at: c.synced_at }))
        .filter((row) => matches(row, query));
    }
    if (level === 'schemas') {
      return schemas
        .map((s) => ({ id: s.id, name: s.name, full_name: s.full_name, synced_at: s.synced_at }))
        .filter((row) => matches(row, query));
    }
    return rows.filter((row) => matches(row, query));
  }, [level, catalogs, schemas, rows, query]);

  const onRowClick = useCallback(
    (row: BrowseRow) => {
      if (level === 'catalogs') {
        const selected = catalogs.find((c) => c.id === row.id);
        if (selected) {
          void openCatalog(selected);
        }
      } else if (level === 'schemas') {
        const selected = schemas.find((s) => s.id === row.id);
        if (selected) {
          void openSchema(selected);
        }
      } else {
        void openTable(row);
      }
    },
    [level, catalogs, schemas, openCatalog, openSchema, openTable]
  );

  const breadcrumbs = [
    { label: t('databricks.catalog.root_crumb', 'Catalog'), level: 'catalogs' as const },
    ...(catalog
      ? [{ label: catalog.name, level: 'schemas' as const }]
      : []),
    ...(schema ? [{ label: schema.name, level: 'objects' as const }] : []),
  ];

  // react-window v2's row component contract: index + style +
  // ariaAttributes (role="listitem"/aria-posinset/aria-setsize) come from
  // the List itself; rowProps carries the page data.
  const renderRow = ({
    index,
    style,
    ariaAttributes,
    rows: rowData,
    onRowClick: clickRow,
  }: RowComponentProps<{
    rows: BrowseRow[];
    onRowClick: (row: BrowseRow) => void;
  }>) => {
    const row = rowData[index];
    return (
      <div {...ariaAttributes} style={style} className="uc-browse-row">
        <button
          type="button"
          className="uc-browse-row-button"
          onClick={() => clickRow(row)}
        >
          <span className="uc-browse-row-name">{row.full_name || row.name}</span>
          {isStale(row.synced_at) && (
            <span role="status" aria-label="stale mirror" className="uc-stale-marker">
              ⚠
            </span>
          )}
        </button>
      </div>
    );
  };

  return (
    <div className="catalog-browser-page" data-testid="catalog-browser-page">
      <nav aria-label={t('databricks.catalog.breadcrumbs_label', 'Catalog breadcrumbs')}>
        {breadcrumbs.map((crumb, i) => (
          <span key={crumb.level}>
            {i > 0 && <span aria-hidden="true"> / </span>}
            <button
              type="button"
              aria-current={i === breadcrumbs.length - 1 ? 'page' : undefined}
              onClick={() => {
                if (crumb.level === 'catalogs') {
                  void loadCatalogs();
                } else if (crumb.level === 'schemas' && catalog) {
                  void openCatalog(catalog);
                } else if (crumb.level === 'objects' && schema) {
                  void openSchema(schema);
                }
              }}
            >
              {crumb.label}
            </button>
          </span>
        ))}
      </nav>

      <input
        type="search"
        aria-label={t('databricks.catalog.search_label', 'Search the current listing')}
        placeholder={t('databricks.catalog.search_placeholder', 'Search by name…')}
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        className="uc-browse-search"
      />

      {level === 'objects' && (
        <div
          role="tablist"
          aria-label={t('databricks.catalog.kind_tabs', 'Object kind')}
          onKeyDown={(e) => {
            // WAI-ARIA APG tabs: ArrowLeft/ArrowRight move the selection
            // (and focus) between the kind tabs; Home/End jump the ends.
            if (e.key !== 'ArrowRight' && e.key !== 'ArrowLeft' && e.key !== 'Home' && e.key !== 'End') {
              return;
            }
            e.preventDefault();
            const current = KINDS.indexOf(kind);
            let next = current;
            if (e.key === 'ArrowRight') {
              next = (current + 1) % KINDS.length;
            } else if (e.key === 'ArrowLeft') {
              next = (current - 1 + KINDS.length) % KINDS.length;
            } else if (e.key === 'Home') {
              next = 0;
            } else {
              next = KINDS.length - 1;
            }
            const target = KINDS[next];
            void switchKind(target);
            (
              (e.currentTarget as HTMLElement).querySelector(
                `[role="tab"]:nth-child(${next + 1})`
              ) as HTMLButtonElement | null
            )?.focus();
          }}
        >
          {KINDS.map((k) => (
            <button
              key={k}
              type="button"
              role="tab"
              aria-selected={kind === k}
              onClick={() => void switchKind(k)}
            >
              {k}
            </button>
          ))}
        </div>
      )}

      {loading && <span aria-busy="true">{t('databricks.catalog.loading', 'Loading…')}</span>}
      {loadError && (
        <div className="error-display" data-testid="catalog-browse-error">
          {loadError}
        </div>
      )}

      <div role="list" aria-label={t('databricks.catalog.list_label', 'Catalog objects')}>
        {visible.length > 0 && (
          <List
            style={{ height: 320, width: '100%' }}
            rowCount={visible.length}
            rowHeight={36}
            rowComponent={renderRow}
            rowProps={{ rows: visible, onRowClick }}
          />
        )}
        {!loading && !loadError && visible.length === 0 && (
          <span>{t('databricks.catalog.empty', 'No objects found.')}</span>
        )}
      </div>

      {detail && (
        <section
          aria-label={t('databricks.catalog.detail_label', 'Table detail')}
          data-testid="uc-table-detail"
        >
          <h3>{detail.full_name}</h3>
          <dl>
            <dt>{t('databricks.catalog.detail_owner', 'Owner')}</dt>
            <dd>{detail.owner}</dd>
            <dt>{t('databricks.catalog.detail_type', 'Type')}</dt>
            <dd>{detail.table_type}</dd>
          </dl>
          <h4>{t('databricks.catalog.detail_columns', 'Columns')}</h4>
          <ul>
            {(detail.columns ?? []).map((column) => (
              <li key={String(column.name)}>
                {String(column.name)}
                {column.type_text ? ` — ${String(column.type_text)}` : ''}
              </li>
            ))}
          </ul>
          <h4>{t('databricks.catalog.detail_permissions', 'My effective permissions')}</h4>
          {(detail.effective_permissions?.privilege_assignments?.length ?? 0) > 0 ? (
            detail.effective_permissions!.privilege_assignments!.map((assignment) => (
              <p key={assignment.principal}>
                {assignment.principal}: {assignment.privileges.join(', ')}
              </p>
            ))
          ) : (
            <p>{t('databricks.catalog.detail_no_permissions', 'None')}</p>
          )}
        </section>
      )}
      {detailLoading && <span aria-busy="true">{t('databricks.catalog.loading', 'Loading…')}</span>}
      {detailError && (
        <div className="error-display" data-testid="uc-detail-error">
          {detailError.code ? `[${detailError.code}] ` : ''}
          {detailError.message}
        </div>
      )}
    </div>
  );
}

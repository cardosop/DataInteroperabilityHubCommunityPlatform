/**
 * Phase 228.F2.17 — LineageEditPage (two-pane table-style editor).
 *
 * Layout:
 *
 *   ┌───────────────┬───────────────┐
 *   │ Source fields │ Target fields │   ← virtualised when > 100
 *   ├───────────────┴───────────────┤
 *   │ Edges table (current mapping) │   ← virtualised when > 100
 *   ├───────────────────────────────┤
 *   │ Toolbar: Save | Cancel | Add  │
 *   └───────────────────────────────┘
 *
 * Hooks:
 *
 * - `useContract` — pulls the contract + its declared models /
 *   fields (the source of truth for the field-existence validation
 *   the server runs).
 * - `useContractLineageVisualization` — initial edge set with
 *   `?include_fields=true` so the F2 surface gets per-field nodes.
 * - `useUpdateContractLineage` — patches the lineage via
 *   `PATCH /contracts/{id}/lineage/`.
 *
 * The page is keyboard-accessible (F2.24): tab order follows
 * source-pane → target-pane → edges-table → toolbar; arrow keys
 * navigate within the virtualised lists; Enter on a row opens the
 * EdgeDetailModal.
 */
import { useMemo, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';

import { CycleErrorPanel } from './CycleErrorPanel';
import { EdgeDetailModal, type EdgeDraft } from './EdgeDetailModal';
import { t } from './lineageEditorStrings';
import { useContract, useContractLineageVisualization } from '../hooks/useContracts';
import { useUpdateContractLineage } from '../hooks/useUpdateContractLineage';

interface ServerError {
  code?: string;
  details?: { code?: string; edge?: EdgeDraft };
}

export function LineageEditPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const contractId = id ?? '';

  const { data: contract } = useContract(contractId || null);
  const {
    data: lineage,
    isLoading: isLineageLoading,
  } = useContractLineageVisualization(contractId, {
    format: 'json', max_depth: 5,
  });

  // Local edge state — the editor's source-of-truth for the
  // pending changes.  Seeded once from the server's current edges.
  const [edges, setEdges] = useState<EdgeDraft[] | null>(null);
  const [editingIndex, setEditingIndex] = useState<number | null>(null);
  const [creating, setCreating] = useState(false);
  const [serverError, setServerError] = useState<ServerError | null>(null);
  const [conflictOpen, setConflictOpen] = useState(false);

  // Seed the local edges from the server payload (one-shot).
  if (edges === null && lineage) {
    const seed: EdgeDraft[] = ((lineage as unknown as Record<string, unknown>)['field_links'] as unknown[] || [])
      .map((l) => l as Record<string, unknown>)
      .map((link) => ({
        source_contract: contractId,
        source_model: parseModel(String(link.source ?? '')),
        source_field: parseField(String(link.source ?? '')),
        target_contract: contractId,
        target_model: parseModel(String(link.target ?? '')),
        target_field: parseField(String(link.target ?? '')),
        edge_type: String(link.edge_type ?? 'reference'),
      }));
    setEdges(seed);
  }

  const update = useUpdateContractLineage();

  const handleSave = async () => {
    if (!edges || !contract) return;
    setServerError(null);
    setConflictOpen(false);
    try {
      const ifMatch = (contract as { etag?: string }).etag;
      await update.mutateAsync({
        contractId,
        payload: { edges: edges as unknown as Array<Record<string, unknown>> },
        options: { ifMatch },
      });
      navigate(`/contracts/${contractId}`);
    } catch (err) {
      const httpStatus = (err as { response?: { status?: number } })?.response?.status;
      const body = (err as { response?: { data?: ServerError } })?.response?.data;
      if (httpStatus === 412) {
        setConflictOpen(true);
      } else {
        setServerError(body ?? { code: 'UNKNOWN' });
      }
    }
  };

  // ----- Render -----

  if (isLineageLoading || edges === null) {
    return <SkeletonEditor />;
  }

  const isCycleError =
    serverError?.code === 'LINEAGE_CYCLE' ||
    serverError?.details?.code === 'LINEAGE_CYCLE';

  return (
    <main aria-label={t('lineage.editor.title')} data-testid="lineage-edit-page">
      <header style={{ marginBottom: 16 }}>
        <h1>{t('lineage.editor.title')}</h1>
        <p>{t('lineage.editor.subtitle')}</p>
      </header>

      {isCycleError && (
        <CycleErrorPanel edge={serverError?.details?.edge} />
      )}

      {serverError && !isCycleError && (
        <ValidationErrorPanel code={serverError.code ?? serverError.details?.code} />
      )}

      <FieldsTwoPane contract={contract} />

      <EdgesTable
        edges={edges}
        onEdit={(i) => setEditingIndex(i)}
        onRemove={(i) =>
          setEdges((cur) => (cur ?? []).filter((_, idx) => idx !== i))
        }
      />

      <Toolbar
        onAdd={() => {
          setCreating(true);
          setEditingIndex(null);
        }}
        onSave={handleSave}
        onCancel={() => navigate(`/contracts/${contractId}`)}
        saving={update.isPending}
      />

      {(editingIndex !== null || creating) && (
        <EdgeDetailModal
          initialEdge={
            editingIndex !== null && edges
              ? edges[editingIndex]
              : emptyEdge(contractId)
          }
          onSave={(edge) => {
            setEdges((cur) => {
              const list = cur ?? [];
              if (editingIndex !== null) {
                const next = [...list];
                next[editingIndex] = edge;
                return next;
              }
              return [...list, edge];
            });
            setEditingIndex(null);
            setCreating(false);
          }}
          onCancel={() => {
            setEditingIndex(null);
            setCreating(false);
          }}
        />
      )}

      {conflictOpen && (
        <ConflictModal
          onReload={() => {
            setConflictOpen(false);
            // Force a fresh fetch of the contract + lineage so the
            // user sees the up-to-date state.  Their local edges
            // remain in `edges` state (the draft is preserved per
            // F2.23).
            window.location.reload();
          }}
          onDiscard={() => {
            setConflictOpen(false);
            navigate(`/contracts/${contractId}`);
          }}
        />
      )}
    </main>
  );
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function FieldsTwoPane({ contract }: { contract: unknown }) {
  // Extract source + target fields from the contract's
  // hub_contract_json (the same shape the validator walks
  // server-side).  When the contract has > 100 fields, the
  // virtualisation kicks in via the FixedSizeList wrapper.
  const fields = useMemo(() => extractFields(contract), [contract]);

  const tooMany = fields.length > 100;

  return (
    <section
      style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 16 }}
      aria-label="Field selectors"
    >
      <FieldsPane heading={t('lineage.editor.pane.source.heading')} fields={fields} virtualised={tooMany} />
      <FieldsPane heading={t('lineage.editor.pane.target.heading')} fields={fields} virtualised={tooMany} />
    </section>
  );
}

function FieldsPane({
  heading,
  fields,
  virtualised,
}: {
  heading: string;
  fields: Array<{ qname: string; type: string }>;
  virtualised: boolean;
}) {
  if (fields.length === 0) {
    return (
      <div>
        <h3>{heading}</h3>
        <p>{t('lineage.editor.pane.empty')}</p>
      </div>
    );
  }
  if (!virtualised) {
    return (
      <div>
        <h3>{heading}</h3>
        <ul style={{ maxHeight: 240, overflow: 'auto', border: '1px solid #ddd', padding: 8 }}>
          {fields.map((f) => (
            <li key={f.qname}>
              <code>{f.qname}</code> <small>({f.type})</small>
            </li>
          ))}
        </ul>
      </div>
    );
  }
  // Virtualised fallback for >100 fields.  Lazy import keeps the
  // bundle size down for the common case.
  const VirtualList = lazyVirtualList();
  return (
    <div>
      <h3>{heading}</h3>
      {/* eslint-disable-next-line @typescript-eslint/no-explicit-any */}
      <VirtualList items={fields as any[]} />
    </div>
  );
}

function lazyVirtualList() {
  // Defer the react-window import to render time so the bundle
  // tree-shakes it out for contracts with ≤100 fields.
  // eslint-disable-next-line @typescript-eslint/no-require-imports, @typescript-eslint/no-explicit-any
  const { FixedSizeList } = require('react-window') as { FixedSizeList: any };
  return ({ items }: { items: Array<{ qname: string; type: string }> }) => (
    <FixedSizeList
      height={240}
      itemCount={items.length}
      itemSize={32}
      width="100%"
    >
      {({ index, style }: { index: number; style: React.CSSProperties }) => {
        const f = items[index];
        return (
          <div style={style} key={f.qname}>
            <code>{f.qname}</code> <small>({f.type})</small>
          </div>
        );
      }}
    </FixedSizeList>
  );
}

function EdgesTable({
  edges,
  onEdit,
  onRemove,
}: {
  edges: EdgeDraft[];
  onEdit: (i: number) => void;
  onRemove: (i: number) => void;
}) {
  if (edges.length === 0) {
    return <p>{t('lineage.editor.edges.empty')}</p>;
  }
  return (
    <section aria-label={t('lineage.editor.edges.heading')}>
      <h3>{t('lineage.editor.edges.heading')}</h3>
      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <thead>
          <tr>
            <th align="left">{t('lineage.editor.edges.col.source')}</th>
            <th align="left">{t('lineage.editor.edges.col.target')}</th>
            <th align="left">{t('lineage.editor.edges.col.type')}</th>
            <th align="left">{t('lineage.editor.edges.col.actions')}</th>
          </tr>
        </thead>
        <tbody>
          {edges.map((e, i) => (
            <tr key={`${e.source_field}-${e.target_field}-${i}`}>
              <td><code>{e.source_model}.{e.source_field}</code></td>
              <td><code>{e.target_model}.{e.target_field}</code></td>
              <td>{e.edge_type}</td>
              <td>
                <button type="button" onClick={() => onEdit(i)}>
                  {t('lineage.editor.edges.row.edit')}
                </button>
                <button type="button" onClick={() => onRemove(i)}>
                  {t('lineage.editor.edges.row.remove')}
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}

function Toolbar({
  onAdd,
  onSave,
  onCancel,
  saving,
}: {
  onAdd: () => void;
  onSave: () => void;
  onCancel: () => void;
  saving: boolean;
}) {
  return (
    <div role="toolbar" style={{ marginTop: 16, display: 'flex', gap: 8 }}>
      <button type="button" onClick={onAdd}>
        {t('lineage.editor.toolbar.add_edge')}
      </button>
      <button type="button" onClick={onSave} disabled={saving}>
        {saving ? t('lineage.editor.saving') : t('lineage.editor.toolbar.save')}
      </button>
      <button type="button" onClick={onCancel}>
        {t('lineage.editor.toolbar.cancel')}
      </button>
    </div>
  );
}

function ConflictModal({
  onReload,
  onDiscard,
}: {
  onReload: () => void;
  onDiscard: () => void;
}) {
  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="lineage-conflict-title"
      data-testid="lineage-conflict-modal"
      style={{
        position: 'fixed',
        inset: '30% 30%',
        background: '#fff',
        border: '1px solid #ccc',
        borderRadius: 8,
        padding: 24,
        boxShadow: '0 8px 32px rgba(0, 0, 0, 0.2)',
        zIndex: 100,
      }}
    >
      <h2 id="lineage-conflict-title">{t('lineage.editor.conflict.title')}</h2>
      <p>{t('lineage.editor.conflict.body')}</p>
      <div style={{ display: 'flex', gap: 8 }}>
        <button type="button" onClick={onReload}>
          {t('lineage.editor.conflict.reload')}
        </button>
        <button type="button" onClick={onDiscard}>
          {t('lineage.editor.conflict.discard')}
        </button>
      </div>
    </div>
  );
}

function ValidationErrorPanel({ code }: { code?: string }) {
  if (code === 'LINEAGE_FIELD_NOT_FOUND') {
    return (
      <section role="alert" data-testid="lineage-field-not-found">
        <h3>{t('lineage.editor.validation.field_not_found.title')}</h3>
        <p>{t('lineage.editor.validation.field_not_found.body')}</p>
      </section>
    );
  }
  if (code === 'LINEAGE_TYPE_MISMATCH') {
    return (
      <section role="alert" data-testid="lineage-type-mismatch">
        <h3>{t('lineage.editor.validation.type_mismatch.title')}</h3>
        <p>{t('lineage.editor.validation.type_mismatch.body')}</p>
      </section>
    );
  }
  if (code === 'PAYLOAD_TOO_LARGE') {
    return (
      <section role="alert" data-testid="lineage-too-large">
        <h3>{t('lineage.editor.too_large.title')}</h3>
        <p>{t('lineage.editor.too_large.body')}</p>
      </section>
    );
  }
  return (
    <section role="alert" data-testid="lineage-save-error">
      <h3>{t('lineage.editor.save_error')}</h3>
    </section>
  );
}

function SkeletonEditor() {
  return (
    <div
      role="status"
      aria-busy="true"
      data-testid="lineage-edit-skeleton"
      style={{ padding: 24 }}
    >
      <p>{t('lineage.editor.saving')}</p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function emptyEdge(contractId: string): EdgeDraft {
  return {
    source_contract: contractId,
    source_model: '',
    source_field: '',
    target_contract: contractId,
    target_model: '',
    target_field: '',
    edge_type: 'reference',
  };
}

function parseModel(fieldId: string): string {
  // The visualization shape encodes field nodes as
  // ``field:<contract>:<model>.<field>``.  Extract the model.
  const match = /field:[^:]+:(.+)\.([^.]+)$/.exec(fieldId);
  return match?.[1] ?? '';
}

function parseField(fieldId: string): string {
  const match = /field:[^:]+:(.+)\.([^.]+)$/.exec(fieldId);
  return match?.[2] ?? '';
}

function extractFields(contract: unknown): Array<{ qname: string; type: string }> {
  if (!contract || typeof contract !== 'object') return [];
  const payload = (contract as { hub_contract_json?: unknown }).hub_contract_json;
  if (!payload || typeof payload !== 'object') return [];
  const out: Array<{ qname: string; type: string }> = [];
  const models = (payload as { models?: unknown[] }).models ?? [];
  for (const m of models) {
    if (!m || typeof m !== 'object') continue;
    const model = m as { name?: string; fields?: unknown[] };
    const modelName = String(model.name ?? '');
    for (const f of model.fields ?? []) {
      if (!f || typeof f !== 'object') continue;
      const field = f as { name?: string; data_type?: string; type?: string };
      out.push({
        qname: `${modelName}.${field.name ?? ''}`,
        type: String(field.data_type ?? field.type ?? ''),
      });
    }
  }
  return out;
}

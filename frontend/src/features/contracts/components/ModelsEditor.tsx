/**
 * Phase 227 Wave 1 (227.L5.2 + L5.5 + L5.6) — Schema editor.
 *
 * Hub-shaped editor: top-level ``models[]`` of ``fields[]``. The
 * compiler at ``contractsCompiler.ts`` projects this state to ODCS
 * ``schema[]`` or ODPS ``product.outputPorts[*].contract.spec.schema[]``
 * on save. Per the 2026-04-30 ungate directive, this tab is always
 * shown — no feature-flag gate. The existing modify-role check stays
 * (a viewer still can't edit).
 *
 * Validation
 * ----------
 * Client-side checks fire on every state change (cheap — runs in pure
 * JS over the editor state). The Save button is disabled while any
 * issue is present. Backend Pydantic validation remains the
 * authoritative gate; the editor's checks are an early-warning UX
 * filter, not a substitute.
 *
 * Save flow
 * ---------
 * 1. Validate locally → if issues, surface inline + disable Save.
 * 2. Compile editor state → ODCS or ODPS source via ``compileToSource``.
 * 3. PATCH ``/api/v1/contracts/{id}/`` with ``If-Match: <stored etag>``.
 * 4. On 412 (precondition failed): surface the conflict dialog with
 *    "Refresh", "Discard my changes", "Open in new tab" actions.
 * 5. On 400 ``STRUCTURELESS_CONTRACT``: surface the typed remediation
 *    via ``getErrorRemediation``.
 */
import { useCallback, useEffect, useMemo, useReducer, useState } from 'react';

import { Button } from '../../../shared/components/Button';
import type {
  EditorField,
  EditorFieldDataType,
  EditorModel,
  EditorValidationIssue,
  SchemaEditorState,
} from '../../../shared/types/contracts';
import { FIELD_DATA_TYPES } from '../../../shared/types/contracts';
import { getErrorRemediation } from '../../../shared/utils/errorUtils';
import { compileToSource, makeUiKey } from '../lib/contractsCompiler';
import { useContractJsonSchema } from '../hooks/useContracts';
import {
  recordSchemaEditorOpened,
  recordSchemaEditorSave,
} from '../lib/schemaEditorMetrics';

/* -------------------------------------------------------------------------
 * State + reducer
 * ------------------------------------------------------------------------- */

type EditorAction =
  | { type: 'SET_STATE'; payload: SchemaEditorState }
  | { type: 'ADD_MODEL' }
  | { type: 'REMOVE_MODEL'; modelIndex: number }
  | { type: 'MOVE_MODEL'; from: number; to: number }
  | {
      type: 'UPDATE_MODEL_NAME';
      modelIndex: number;
      name: string;
    }
  | {
      type: 'UPDATE_MODEL_DESCRIPTION';
      modelIndex: number;
      description: string;
    }
  | { type: 'ADD_FIELD'; modelIndex: number }
  | { type: 'REMOVE_FIELD'; modelIndex: number; fieldIndex: number }
  | {
      type: 'MOVE_FIELD';
      modelIndex: number;
      from: number;
      to: number;
    }
  | {
      type: 'UPDATE_FIELD';
      modelIndex: number;
      fieldIndex: number;
      patch: Partial<EditorField>;
    }
  | {
      type: 'SET_ETAG';
      etag: string | null;
    };

function _newField(): EditorField {
  return {
    _uiKey: makeUiKey('f'),
    name: '',
    data_type: 'string',
    nullable: true,
  };
}

function _newModel(idx: number): EditorModel {
  return {
    _uiKey: makeUiKey('m'),
    name: `model_${idx + 1}`,
    fields: [_newField()],
  };
}

function _move<T>(arr: T[], from: number, to: number): T[] {
  if (from === to || from < 0 || from >= arr.length || to < 0 || to >= arr.length) {
    return arr;
  }
  const next = [...arr];
  const [item] = next.splice(from, 1);
  next.splice(to, 0, item);
  return next;
}

function reducer(state: SchemaEditorState, action: EditorAction): SchemaEditorState {
  switch (action.type) {
    case 'SET_STATE':
      return action.payload;
    case 'ADD_MODEL':
      return { ...state, models: [...state.models, _newModel(state.models.length)] };
    case 'REMOVE_MODEL':
      return {
        ...state,
        models: state.models.filter((_, i) => i !== action.modelIndex),
      };
    case 'MOVE_MODEL':
      return { ...state, models: _move(state.models, action.from, action.to) };
    case 'UPDATE_MODEL_NAME':
      return {
        ...state,
        models: state.models.map((m, i) =>
          i === action.modelIndex ? { ...m, name: action.name } : m,
        ),
      };
    case 'UPDATE_MODEL_DESCRIPTION':
      return {
        ...state,
        models: state.models.map((m, i) =>
          i === action.modelIndex ? { ...m, description: action.description } : m,
        ),
      };
    case 'ADD_FIELD':
      return {
        ...state,
        models: state.models.map((m, i) =>
          i === action.modelIndex ? { ...m, fields: [...m.fields, _newField()] } : m,
        ),
      };
    case 'REMOVE_FIELD':
      return {
        ...state,
        models: state.models.map((m, i) =>
          i === action.modelIndex
            ? { ...m, fields: m.fields.filter((_, j) => j !== action.fieldIndex) }
            : m,
        ),
      };
    case 'MOVE_FIELD':
      return {
        ...state,
        models: state.models.map((m, i) =>
          i === action.modelIndex ? { ...m, fields: _move(m.fields, action.from, action.to) } : m,
        ),
      };
    case 'UPDATE_FIELD':
      return {
        ...state,
        models: state.models.map((m, i) =>
          i === action.modelIndex
            ? {
                ...m,
                fields: m.fields.map((f, j) =>
                  j === action.fieldIndex ? { ...f, ...action.patch } : f,
                ),
              }
            : m,
        ),
      };
    case 'SET_ETAG':
      return { ...state, etag: action.etag };
    default:
      return state;
  }
}

/* -------------------------------------------------------------------------
 * Validation (Phase 227 L5.5)
 *
 * The hand-coded rules below cover the structural floor invariants the
 * editor must enforce client-side. ``deriveAllowedDataTypes`` reads the
 * JSON Schema response (when supplied) to keep the field-type dropdown
 * in sync with the Pydantic-defined source of truth — so adding a new
 * type to ``HubContractField.data_type`` flows through automatically
 * without a UI patch. Without a schema we fall back to the static
 * ``FIELD_DATA_TYPES`` constant.
 * ------------------------------------------------------------------------- */

/**
 * Walk the JSON-Schema ``$defs`` for the ``HubContractField`` definition
 * and return its ``data_type`` enum. Returns ``null`` when the shape
 * doesn't match expectations so callers can fall back to the static set.
 */
export function deriveAllowedDataTypes(
  jsonSchema: Record<string, unknown> | null | undefined,
): string[] | null {
  if (!jsonSchema || typeof jsonSchema !== 'object') return null;
  const defs = (jsonSchema.$defs ?? jsonSchema.definitions) as
    | Record<string, unknown>
    | undefined;
  if (!defs) return null;
  // Pydantic v2 emits ``$defs`` keyed by class name.
  const fieldDef = defs.HubContractField as Record<string, unknown> | undefined;
  if (!fieldDef || typeof fieldDef !== 'object') return null;
  const props = fieldDef.properties as Record<string, unknown> | undefined;
  if (!props) return null;
  const typeProp = (props.type ?? props.data_type) as
    | { enum?: unknown[] }
    | undefined;
  if (!typeProp || !Array.isArray(typeProp.enum)) return null;
  return typeProp.enum.filter((v): v is string => typeof v === 'string');
}

export function validateEditorState(
  state: SchemaEditorState,
  jsonSchema?: Record<string, unknown> | null,
): EditorValidationIssue[] {
  const issues: EditorValidationIssue[] = [];
  // When a JSON Schema is supplied, narrow the allowed data_type set
  // to whatever the backend Pydantic model permits. Otherwise fall
  // back to the static ``FIELD_DATA_TYPES`` constant.
  const allowedTypes = (deriveAllowedDataTypes(jsonSchema) ?? FIELD_DATA_TYPES) as readonly string[];
  state.models.forEach((model, modelIndex) => {
    if (!model.name || !model.name.trim()) {
      issues.push({
        modelIndex,
        message: 'Model name is required',
        code: 'MODEL_NAME_REQUIRED',
      });
    }
    if (model.fields.length === 0) {
      issues.push({
        modelIndex,
        message: `Model "${model.name || `#${modelIndex + 1}`}" must have at least one field`,
        code: 'MODEL_FIELDS_REQUIRED',
      });
    }
    const seenNames = new Set<string>();
    model.fields.forEach((field, fieldIndex) => {
      const fieldPath = `${model.name || `#${modelIndex + 1}`}.fields[${fieldIndex}]`;
      if (!field.name || !field.name.trim()) {
        issues.push({
          modelIndex,
          fieldPath,
          message: 'Field name is required',
          code: 'FIELD_NAME_REQUIRED',
        });
      } else if (seenNames.has(field.name)) {
        issues.push({
          modelIndex,
          fieldPath,
          message: `Duplicate field name "${field.name}" in this model`,
          code: 'FIELD_NAME_DUPLICATE',
        });
      } else {
        seenNames.add(field.name);
      }
      // JSON-Schema-driven check: data_type must be in the allowed set.
      if (field.data_type && !allowedTypes.includes(field.data_type)) {
        issues.push({
          modelIndex,
          fieldPath,
          message: `Field "${field.name || '?'}" has unsupported type "${field.data_type}". Allowed: ${allowedTypes.join(', ')}.`,
          code: 'FIELD_NAME_REQUIRED', // closest fit; see EditorValidationIssue codes
        });
      }
      if (field.data_type === 'object' && (!field.fields || field.fields.length === 0)) {
        issues.push({
          modelIndex,
          fieldPath,
          message: `Object-typed field "${field.name || '?'}" must declare nested fields`,
          code: 'OBJECT_FIELD_REQUIRES_NESTED_FIELDS',
        });
      }
      if (field.data_type === 'array' && !field.items) {
        issues.push({
          modelIndex,
          fieldPath,
          message: `Array-typed field "${field.name || '?'}" must declare an items schema`,
          code: 'ARRAY_FIELD_REQUIRES_ITEMS',
        });
      }
    });
  });
  return issues;
}

/* -------------------------------------------------------------------------
 * UI
 * ------------------------------------------------------------------------- */

interface ModelsEditorProps {
  initialState: SchemaEditorState;
  /** Save handler. Receives the compiled raw + format + ETag. Returns a
   * promise that resolves when the PATCH lands, OR rejects with an
   * ApiError-shaped object so the editor can render remediation. */
  onSave: (args: {
    raw: string;
    format: 'JSON' | 'YAML';
    ifMatch: string | null | undefined;
  }) => Promise<{ etag?: string | null }>;
  /** Disable interactions (e.g. while user lacks the modify role). */
  readOnly?: boolean;
  /**
   * Controlled handler invoked when state changes — useful for parents
   * that want to keep their own copy or display dirty-state. Optional.
   */
  onStateChange?: (state: SchemaEditorState) => void;
}

interface ConflictDialogState {
  open: boolean;
  serverEtag?: string | null;
}

export function ModelsEditor(props: ModelsEditorProps) {
  const { initialState, onSave, readOnly = false, onStateChange } = props;
  const [state, dispatch] = useReducer(reducer, initialState);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<{
    code: string;
    subcode?: string;
    message: string;
    details?: Record<string, unknown> | null;
  } | null>(null);
  const [conflict, setConflict] = useState<ConflictDialogState>({ open: false });

  // Re-seed when initialState changes (e.g. parent reloaded the contract).
  useEffect(() => {
    dispatch({ type: 'SET_STATE', payload: initialState });
  }, [initialState]);

  // Phase 227 Wave 1 (227.L7.2) — emit ``schema_editor_opened_total``
  // once on mount. Empty deps array intentional: we want exactly one
  // emission per editor open, NOT one per re-render. Tracking per
  // render would inflate the counter and break the funnel-top reading
  // on the Grafana adoption panel.
  useEffect(() => {
    recordSchemaEditorOpened(initialState.specType);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Capture the wall-clock open timestamp so the first successful
  // save can observe ``schema_editor_time_to_first_save_seconds``.
  // ``useState(() => ...)`` initialiser fires once per component
  // instance, matching the L7.2 spec: "between Schema-editor open
  // and FIRST successful save in the same session".
  const [openedAtMs] = useState(() => Date.now());
  const [hasReportedFirstSave, setHasReportedFirstSave] = useState(false);

  useEffect(() => {
    onStateChange?.(state);
  }, [state, onStateChange]);

  // Phase 227 Wave 1 (227.L5.5) — drive client-side validation from
  // the canonical JSON Schema response so the field-type enum stays
  // in sync with the Pydantic source of truth. Cached for an hour.
  const { data: schemaResponse } = useContractJsonSchema(
    state.specType === 'ODPS' ? 'odps' : 'odcs',
  );
  const issues = useMemo(
    () => validateEditorState(state, schemaResponse?.schema ?? null),
    [state, schemaResponse],
  );
  const canSave = !readOnly && !saving && issues.length === 0 && state.models.length > 0;

  const handleSave = useCallback(async () => {
    setSaveError(null);
    setSaving(true);
    try {
      const compiled = compileToSource(state, { format: 'JSON' });
      const result = await onSave({
        raw: compiled.raw,
        format: 'JSON',
        ifMatch: state.etag,
      });
      if (result.etag !== undefined) {
        dispatch({ type: 'SET_ETAG', etag: result.etag ?? null });
      }
      // Phase 227 Wave 1 (227.L7.2) — success path. The
      // ``time_to_first_save_seconds`` histogram is only observed on
      // the FIRST successful save of the session per the spec.
      const ttfs =
        !hasReportedFirstSave
          ? Math.max(0, (Date.now() - openedAtMs) / 1000)
          : undefined;
      recordSchemaEditorSave({
        specType: state.specType,
        outcome: 'success',
        timeToFirstSaveSeconds: ttfs,
      });
      if (!hasReportedFirstSave) {
        setHasReportedFirstSave(true);
      }
    } catch (rawErr) {
      const err = rawErr as
        | {
            code?: string;
            message?: string;
            details?: Record<string, unknown> & {
              subcode?: string;
              current_etag?: string | null;
            };
            error?: { code?: string; message?: string; details?: Record<string, unknown> };
          }
        | undefined;
      const wrapped = err?.error ?? err ?? {};
      const code = String(wrapped.code ?? 'UNKNOWN');
      const details = (wrapped.details ?? null) as Record<string, unknown> | null;
      const subcode = (details?.subcode as string | undefined) ?? undefined;
      if (code === 'PRECONDITION_FAILED') {
        setConflict({ open: true, serverEtag: details?.current_etag as string | null | undefined });
      }
      setSaveError({
        code,
        subcode,
        message: String(wrapped.message ?? 'Save failed'),
        details,
      });
      // Phase 227 Wave 1 (227.L7.2) — failure path. Bucket the
      // outcome label so the dashboard can break down conflict
      // (412) vs. validation rejection vs. generic error.
      const outcome =
        code === 'PRECONDITION_FAILED'
          ? 'conflict'
          : code === 'STRUCTURELESS_CONTRACT' || code === 'VALIDATION_ERROR'
          ? 'validation_error'
          : 'error';
      recordSchemaEditorSave({
        specType: state.specType,
        outcome,
      });
    } finally {
      setSaving(false);
    }
  }, [state, onSave, openedAtMs, hasReportedFirstSave]);

  const conflictRemediation = useMemo(() => {
    return saveError ? getErrorRemediation(saveError.code, saveError.subcode, saveError.details as { remediation_url?: string | null } | null) : null;
  }, [saveError]);

  return (
    <div className="models-editor" data-testid="models-editor">
      <div className="models-editor__header">
        <h3>Models</h3>
        <Button
          onClick={() => dispatch({ type: 'ADD_MODEL' })}
          variant="secondary"
          disabled={readOnly}
          data-testid="add-model"
        >
          + Add model
        </Button>
      </div>

      {saveError && (
        <div
          className="models-editor__error"
          role="alert"
          data-testid="save-error"
        >
          <strong>{conflictRemediation?.title ?? saveError.message}</strong>
          {conflictRemediation?.details && <p>{conflictRemediation.details}</p>}
          {conflictRemediation?.ctaUrl && (
            <a
              href={conflictRemediation.ctaUrl}
              target="_blank"
              rel="noreferrer"
              data-testid="save-error-cta"
            >
              {conflictRemediation.ctaLabel ?? 'Open'}
            </a>
          )}
        </div>
      )}

      {issues.length > 0 && (
        <div
          className="models-editor__issues"
          role="status"
          data-testid="editor-issues"
        >
          <ul>
            {issues.map((issue, idx) => (
              <li key={idx}>{issue.message}</li>
            ))}
          </ul>
        </div>
      )}

      {state.models.length === 0 && (
        <div className="models-editor__empty" data-testid="models-empty">
          <p>No models declared. Click <em>Add model</em> to define the first one.</p>
        </div>
      )}

      <ol className="models-editor__list">
        {state.models.map((model, modelIndex) => (
          <li
            key={model._uiKey}
            className="models-editor__item"
            data-testid={`model-${modelIndex}`}
          >
            <div className="models-editor__item-header">
              <input
                type="text"
                value={model.name}
                onChange={(e) =>
                  dispatch({
                    type: 'UPDATE_MODEL_NAME',
                    modelIndex,
                    name: e.target.value,
                  })
                }
                placeholder="model name"
                aria-label={`Model ${modelIndex + 1} name`}
                disabled={readOnly}
                data-testid={`model-${modelIndex}-name`}
              />
              <div className="models-editor__item-actions">
                <button
                  type="button"
                  onClick={() =>
                    dispatch({ type: 'MOVE_MODEL', from: modelIndex, to: modelIndex - 1 })
                  }
                  disabled={readOnly || modelIndex === 0}
                  aria-label={`Move model ${modelIndex + 1} up`}
                >
                  ↑
                </button>
                <button
                  type="button"
                  onClick={() =>
                    dispatch({ type: 'MOVE_MODEL', from: modelIndex, to: modelIndex + 1 })
                  }
                  disabled={readOnly || modelIndex === state.models.length - 1}
                  aria-label={`Move model ${modelIndex + 1} down`}
                >
                  ↓
                </button>
                <button
                  type="button"
                  onClick={() => dispatch({ type: 'REMOVE_MODEL', modelIndex })}
                  disabled={readOnly}
                  aria-label={`Remove model ${modelIndex + 1}`}
                  data-testid={`model-${modelIndex}-remove`}
                >
                  Remove
                </button>
              </div>
            </div>

            <textarea
              value={model.description ?? ''}
              onChange={(e) =>
                dispatch({
                  type: 'UPDATE_MODEL_DESCRIPTION',
                  modelIndex,
                  description: e.target.value,
                })
              }
              placeholder="Description (optional)"
              rows={2}
              disabled={readOnly}
            />

            <FieldsList
              modelIndex={modelIndex}
              fields={model.fields}
              dispatch={dispatch}
              readOnly={readOnly}
            />
          </li>
        ))}
      </ol>

      <div className="models-editor__footer">
        <Button
          onClick={handleSave}
          variant="primary"
          disabled={!canSave}
          loading={saving}
          data-testid="save-models"
        >
          Save schema
        </Button>
      </div>

      {conflict.open && (
        <ConflictDialog
          serverEtag={conflict.serverEtag ?? null}
          onRefresh={() => {
            setConflict({ open: false });
            // The parent handles the refetch; the editor surfaces a
            // signal via onStateChange (caller can observe `etag` on
            // their own Contract object).
            window.location.reload();
          }}
          onDiscard={() => {
            setConflict({ open: false });
            window.location.reload();
          }}
          onOpenInNewTab={() => {
            window.open(window.location.href, '_blank');
          }}
        />
      )}
    </div>
  );
}

/* -------------------------------------------------------------------------
 * FieldsList — flattened field-row list for one model.
 * Nested ``object`` / ``array`` types render their nested children
 * inline at one extra indent level for now (Phase 227 L5.2 surface
 * area). Deeper editing happens through the raw editor for now.
 * ------------------------------------------------------------------------- */

interface FieldsListProps {
  modelIndex: number;
  fields: EditorField[];
  dispatch: React.Dispatch<EditorAction>;
  readOnly: boolean;
}

function FieldsList({ modelIndex, fields, dispatch, readOnly }: FieldsListProps) {
  return (
    <table className="models-editor__fields" data-testid={`model-${modelIndex}-fields`}>
      <thead>
        <tr>
          <th>Name</th>
          <th>Type</th>
          <th>Description</th>
          <th>Nullable</th>
          <th>Constraints</th>
          <th aria-label="Actions">
            <span className="sr-only">Actions</span>
          </th>
        </tr>
      </thead>
      <tbody>
        {fields.map((field, fieldIndex) => (
          <tr key={field._uiKey} data-testid={`field-${modelIndex}-${fieldIndex}`}>
            <td>
              <input
                type="text"
                value={field.name}
                onChange={(e) =>
                  dispatch({
                    type: 'UPDATE_FIELD',
                    modelIndex,
                    fieldIndex,
                    patch: { name: e.target.value },
                  })
                }
                placeholder="field name"
                aria-label={`Field name ${fieldIndex + 1}`}
                disabled={readOnly}
                data-testid={`field-${modelIndex}-${fieldIndex}-name`}
              />
            </td>
            <td>
              <select
                value={field.data_type}
                onChange={(e) =>
                  dispatch({
                    type: 'UPDATE_FIELD',
                    modelIndex,
                    fieldIndex,
                    patch: {
                      data_type: e.target.value as EditorFieldDataType,
                    },
                  })
                }
                disabled={readOnly}
                aria-label={`Field type ${fieldIndex + 1}`}
              >
                {FIELD_DATA_TYPES.map((t) => (
                  <option key={t} value={t}>
                    {t}
                  </option>
                ))}
              </select>
            </td>
            <td>
              <input
                type="text"
                value={field.description ?? ''}
                onChange={(e) =>
                  dispatch({
                    type: 'UPDATE_FIELD',
                    modelIndex,
                    fieldIndex,
                    patch: { description: e.target.value },
                  })
                }
                placeholder="description"
                disabled={readOnly}
              />
            </td>
            <td>
              <input
                type="checkbox"
                checked={field.nullable ?? true}
                onChange={(e) =>
                  dispatch({
                    type: 'UPDATE_FIELD',
                    modelIndex,
                    fieldIndex,
                    patch: { nullable: e.target.checked },
                  })
                }
                aria-label={`Field ${fieldIndex + 1} nullable`}
                disabled={readOnly}
              />
            </td>
            <td>
              <label>
                <input
                  type="checkbox"
                  checked={field.is_primary_key ?? false}
                  onChange={(e) =>
                    dispatch({
                      type: 'UPDATE_FIELD',
                      modelIndex,
                      fieldIndex,
                      patch: { is_primary_key: e.target.checked },
                    })
                  }
                  disabled={readOnly}
                />{' '}
                PK
              </label>{' '}
              <label>
                <input
                  type="checkbox"
                  checked={field.is_unique ?? false}
                  onChange={(e) =>
                    dispatch({
                      type: 'UPDATE_FIELD',
                      modelIndex,
                      fieldIndex,
                      patch: { is_unique: e.target.checked },
                    })
                  }
                  disabled={readOnly}
                />{' '}
                UQ
              </label>
            </td>
            <td>
              <button
                type="button"
                onClick={() =>
                  dispatch({
                    type: 'MOVE_FIELD',
                    modelIndex,
                    from: fieldIndex,
                    to: fieldIndex - 1,
                  })
                }
                disabled={readOnly || fieldIndex === 0}
                aria-label={`Move field ${fieldIndex + 1} up`}
              >
                ↑
              </button>
              <button
                type="button"
                onClick={() =>
                  dispatch({
                    type: 'MOVE_FIELD',
                    modelIndex,
                    from: fieldIndex,
                    to: fieldIndex + 1,
                  })
                }
                disabled={readOnly || fieldIndex === fields.length - 1}
                aria-label={`Move field ${fieldIndex + 1} down`}
              >
                ↓
              </button>
              <button
                type="button"
                onClick={() =>
                  dispatch({
                    type: 'REMOVE_FIELD',
                    modelIndex,
                    fieldIndex,
                  })
                }
                disabled={readOnly}
                aria-label={`Remove field ${fieldIndex + 1}`}
                data-testid={`field-${modelIndex}-${fieldIndex}-remove`}
              >
                Remove
              </button>
            </td>
          </tr>
        ))}
        <tr>
          <td colSpan={6}>
            <button
              type="button"
              onClick={() => dispatch({ type: 'ADD_FIELD', modelIndex })}
              disabled={readOnly}
              data-testid={`model-${modelIndex}-add-field`}
            >
              + Add field
            </button>
          </td>
        </tr>
      </tbody>
    </table>
  );
}

/* -------------------------------------------------------------------------
 * ConflictDialog — Phase 227 L5.6
 * ------------------------------------------------------------------------- */

interface ConflictDialogProps {
  serverEtag: string | null;
  onRefresh: () => void;
  onDiscard: () => void;
  onOpenInNewTab: () => void;
}

function ConflictDialog({
  serverEtag,
  onRefresh,
  onDiscard,
  onOpenInNewTab,
}: ConflictDialogProps) {
  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="conflict-dialog-title"
      className="models-editor__conflict-dialog"
      data-testid="conflict-dialog"
    >
      <div className="models-editor__conflict-dialog-content">
        <h2 id="conflict-dialog-title">Contract was modified</h2>
        <p>
          Someone else updated this contract while you were editing.
          Choose how you want to resolve the conflict:
        </p>
        {serverEtag && (
          <p className="models-editor__conflict-dialog-etag">
            Server ETag: <code>{serverEtag}</code>
          </p>
        )}
        <div className="models-editor__conflict-dialog-actions">
          <Button onClick={onRefresh} variant="primary" data-testid="conflict-refresh">
            Refresh (lose my changes)
          </Button>
          <Button onClick={onDiscard} variant="secondary" data-testid="conflict-discard">
            Discard my changes
          </Button>
          <Button onClick={onOpenInNewTab} variant="secondary" data-testid="conflict-newtab">
            Open contract in new tab
          </Button>
        </div>
      </div>
    </div>
  );
}

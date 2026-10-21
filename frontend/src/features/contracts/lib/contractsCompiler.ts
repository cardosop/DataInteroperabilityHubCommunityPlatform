/**
 * Phase 227 Wave 1 (227.L5.1) — contracts compiler.
 *
 * Bidirectional bridge between the Schema-editor's hub-shaped state
 * (``SchemaEditorState`` — models[*].fields[*]) and the source spec the
 * contract is stored as (ODCS or ODPS embedding ODCS).
 *
 * Two responsibilities
 * --------------------
 * * :func:`compileToSource` — projects ``SchemaEditorState`` → JSON or
 *   YAML source matching ``specType`` / ``specVersion``. ODCS path
 *   emits ``schema.fields[]`` (single-model) or ``models[*].fields[]``
 *   (multi-model). ODPS path emits
 *   ``product.outputPorts[*].contract.spec.schema.fields[]`` — i.e. an
 *   inline ODCS contract embedded in the first outputPort.
 * * :func:`parseFromSource` — reverse direction. Accepts the raw source
 *   string + format hint and returns a ``SchemaEditorState`` ready for
 *   the editor to consume.
 *
 * Design notes
 * ------------
 * The compiler is intentionally lossy on round-trip for fields the
 * editor doesn't model (e.g. ``servers[]``, ``team``, ``slaProperties``).
 * Callers preserve the original raw and merge editor-controlled keys
 * into it — see ``ContractEditorPage`` for the merge.
 */

import yaml from 'js-yaml';

import type {
  EditorField,
  EditorFieldDataType,
  EditorModel,
  SchemaEditorState,
} from '../../../shared/types/contracts';

let _uiKeyCounter = 0;

/** Generate a stable client-side React key for the editor. */
export function makeUiKey(prefix = 'k'): string {
  _uiKeyCounter += 1;
  return `${prefix}-${_uiKeyCounter}-${Math.random().toString(36).slice(2, 8)}`;
}

/* -------------------------------------------------------------------------
 * Compile (editor state → ODCS/ODPS source)
 * ------------------------------------------------------------------------- */

interface CompileOptions {
  /** Output format. Defaults to JSON. */
  format?: 'JSON' | 'YAML';
  /**
   * When true, the compiler merges into ``state.originalRaw`` (parsed)
   * so unrecognised top-level keys (servers, team, etc.) survive the
   * round-trip. Defaults to true.
   */
  preserveOriginal?: boolean;
}

export interface CompileResult {
  /** The serialised contract source, ready for PATCH. */
  raw: string;
  /** The doc as a plain object — useful for tests + dry-run normalize. */
  doc: Record<string, unknown>;
}

function _editorFieldToOdcs(field: EditorField): Record<string, unknown> {
  const out: Record<string, unknown> = {
    name: field.name,
    // Emit the canonical ODCS ``type`` key (alias of HubContract data_type).
    type: field.data_type,
  };
  if (field.description != null) out.description = field.description;
  if (field.nullable != null) out.nullable = field.nullable;
  if (field.format != null) out.format = field.format;
  if (field.pattern != null) out.pattern = field.pattern;
  if (field.enum != null) out.enum = field.enum;
  if (field.default !== undefined) out.default = field.default;
  if (field.min_length != null) out.minLength = field.min_length;
  if (field.max_length != null) out.maxLength = field.max_length;
  if (field.minimum != null) out.minimum = field.minimum;
  if (field.maximum != null) out.maximum = field.maximum;
  if (field.is_primary_key) out.primaryKey = true;
  if (field.is_unique) out.unique = true;
  if (field.is_indexed) out.is_indexed = true;
  // Recurse into nested objects/arrays.
  if (field.data_type === 'object' && field.fields && field.fields.length > 0) {
    // Use ``properties`` (post-v3.0.x) — the recursive walker also
    // accepts ``fields`` for older versions, but we emit the modern
    // shape on save. Matches the precedence rule in
    // ``_extract_nested_object_children`` (Phase 227 L2.5).
    const properties: Record<string, unknown> = {};
    for (const child of field.fields) {
      const compiled = _editorFieldToOdcs(child);
      const { name: childName, ...rest } = compiled;
      properties[String(childName)] = rest;
    }
    out.properties = properties;
  }
  if (field.data_type === 'array' && field.items) {
    const compiled = _editorFieldToOdcs(field.items);
    const { name: _ignored, ...rest } = compiled;
    void _ignored;
    out.items = rest;
  }
  return out;
}

function _editorModelToOdcsSchemaEntry(
  model: EditorModel,
): Record<string, unknown> {
  return {
    name: model.name,
    ...(model.description ? { description: model.description } : {}),
    ...(model.primary_key && model.primary_key.length > 0
      ? { primary_key: [...model.primary_key] }
      : {}),
    ...(model.tags && model.tags.length > 0 ? { tags: [...model.tags] } : {}),
    fields: model.fields.map(_editorFieldToOdcs),
  };
}

function _serialise(
  doc: Record<string, unknown>,
  format: 'JSON' | 'YAML',
): string {
  if (format === 'YAML') {
    return yaml.dump(doc, { noRefs: true, lineWidth: 120 });
  }
  return JSON.stringify(doc, null, 2);
}

function _parseRaw(raw: string | undefined): Record<string, unknown> {
  if (!raw) return {};
  // Try JSON first; fall back to YAML.
  try {
    const parsed = JSON.parse(raw);
    return parsed && typeof parsed === 'object' && !Array.isArray(parsed)
      ? (parsed as Record<string, unknown>)
      : {};
  } catch {
    /* fallthrough */
  }
  try {
    const parsed = yaml.load(raw);
    return parsed && typeof parsed === 'object' && !Array.isArray(parsed)
      ? (parsed as Record<string, unknown>)
      : {};
  } catch {
    return {};
  }
}

export function compileToSource(
  state: SchemaEditorState,
  opts: CompileOptions = {},
): CompileResult {
  const format = opts.format ?? 'JSON';
  const preserveOriginal = opts.preserveOriginal ?? true;
  const baseDoc = preserveOriginal ? _parseRaw(state.originalRaw) : {};

  if (state.specType === 'ODCS') {
    const odcsDoc: Record<string, unknown> = {
      ...baseDoc,
      apiVersion: (baseDoc.apiVersion as string) ?? `v${state.specVersion}`,
      kind: (baseDoc.kind as string) ?? 'DataContract',
      id: (baseDoc.id as string) ?? state.info.name ?? 'contract',
      name: state.info.name ?? (baseDoc.name as string) ?? '',
      version: state.info.version ?? (baseDoc.version as string) ?? '1.0.0',
      status: state.info.status ?? (baseDoc.status as string) ?? 'active',
    };
    if (state.info.description) {
      odcsDoc.description = state.info.description;
    }
    // ODCS schema[] is a list of model entries; emit one per editor model.
    odcsDoc.schema = state.models.map(_editorModelToOdcsSchemaEntry);
    return { raw: _serialise(odcsDoc, format), doc: odcsDoc };
  }

  // ODPS path — embed the editor state as the first outputPort's
  // ``contract.spec.schema``. We do NOT split into multiple outputPorts
  // because the editor is hub-shaped (one models[] list); a richer ODPS
  // editor would expose port-level metadata separately.
  const product = (baseDoc.product as Record<string, unknown> | undefined) ?? {};
  const odpsDoc: Record<string, unknown> = {
    ...baseDoc,
    product: {
      ...product,
      details: (product.details as unknown) ?? {
        en: {
          productID: state.info.name ?? 'product',
          name: state.info.name ?? 'product',
          productVersion: state.info.version ?? '1.0.0',
          ...(state.info.description
            ? { description: state.info.description }
            : {}),
        },
      },
      outputPorts: [
        {
          name: state.info.name ?? 'output',
          contract: {
            spec: {
              apiVersion: 'odcs.io/v3.0.2',
              kind: 'DataContract',
              id: state.info.name ?? 'embedded',
              name: state.info.name ?? 'embedded',
              version: state.info.version ?? '1.0.0',
              status: state.info.status ?? 'active',
              schema: state.models.map(_editorModelToOdcsSchemaEntry),
            },
          },
        },
      ],
    },
  };
  // Preserve the existing ``schema`` URL from the original raw if any.
  if (typeof baseDoc.schema === 'string') {
    odpsDoc.schema = baseDoc.schema;
  }
  if (typeof baseDoc.version === 'string' && !odpsDoc.version) {
    odpsDoc.version = baseDoc.version;
  }
  return { raw: _serialise(odpsDoc, format), doc: odpsDoc };
}

/* -------------------------------------------------------------------------
 * Parse (ODCS/ODPS source → editor state)
 * ------------------------------------------------------------------------- */

const _DATA_TYPE_LOOKUP: Set<string> = new Set([
  'string',
  'integer',
  'number',
  'boolean',
  'date',
  'date-time',
  'time',
  'object',
  'array',
]);

function _coerceDataType(raw: unknown): EditorFieldDataType {
  if (typeof raw !== 'string') return 'string';
  const lower = raw.toLowerCase();
  if (_DATA_TYPE_LOOKUP.has(lower)) return lower as EditorFieldDataType;
  // Aliases.
  if (lower === 'integer' || lower === 'int') return 'integer';
  if (lower === 'datetime') return 'date-time';
  if (lower === 'bool') return 'boolean';
  return 'string';
}

function _odcsFieldToEditor(name: string, raw: Record<string, unknown>): EditorField {
  const dataType = _coerceDataType(raw.type ?? raw.data_type);
  const out: EditorField = {
    _uiKey: makeUiKey('f'),
    name,
    data_type: dataType,
  };
  if (typeof raw.description === 'string') out.description = raw.description;
  if (typeof raw.nullable === 'boolean') out.nullable = raw.nullable;
  if (typeof raw.format === 'string') out.format = raw.format;
  if (typeof raw.pattern === 'string') out.pattern = raw.pattern;
  if (Array.isArray(raw.enum)) out.enum = raw.enum as Array<string | number>;
  if (raw.default !== undefined) out.default = raw.default;
  const minLen = (raw.minLength ?? raw.min_length) as number | undefined;
  if (typeof minLen === 'number') out.min_length = minLen;
  const maxLen = (raw.maxLength ?? raw.max_length) as number | undefined;
  if (typeof maxLen === 'number') out.max_length = maxLen;
  if (typeof raw.minimum === 'number') out.minimum = raw.minimum;
  if (typeof raw.maximum === 'number') out.maximum = raw.maximum;
  if (raw.primaryKey === true || raw.primary_key === true || raw.is_primary_key === true) {
    out.is_primary_key = true;
  }
  if (raw.unique === true || raw.is_unique === true) out.is_unique = true;
  if (raw.is_indexed === true) out.is_indexed = true;

  // Recurse into nested object children.
  if (dataType === 'object') {
    const properties = raw.properties as Record<string, unknown> | undefined;
    if (properties && typeof properties === 'object') {
      out.fields = Object.entries(properties).map(([childName, childRaw]) =>
        _odcsFieldToEditor(
          childName,
          (childRaw as Record<string, unknown>) ?? {},
        ),
      );
    } else if (Array.isArray(raw.fields)) {
      // Older ODCS dialects use a list under ``fields``.
      out.fields = (raw.fields as Array<Record<string, unknown>>).map((f) =>
        _odcsFieldToEditor(String(f.name ?? ''), f),
      );
    }
  }
  if (dataType === 'array') {
    const items = raw.items as Record<string, unknown> | undefined;
    if (items && typeof items === 'object') {
      out.items = _odcsFieldToEditor('items', items);
    }
  }
  return out;
}

function _odcsSchemaEntryToEditorModel(
  entry: Record<string, unknown>,
  fallbackName: string,
): EditorModel {
  const fields = Array.isArray(entry.fields)
    ? (entry.fields as Array<Record<string, unknown>>).map((f) =>
        _odcsFieldToEditor(String(f.name ?? ''), f),
      )
    : [];
  return {
    _uiKey: makeUiKey('m'),
    name: typeof entry.name === 'string' && entry.name ? entry.name : fallbackName,
    description: typeof entry.description === 'string' ? entry.description : undefined,
    fields,
    primary_key: Array.isArray(entry.primary_key)
      ? (entry.primary_key as string[])
      : undefined,
    tags: Array.isArray(entry.tags) ? (entry.tags as string[]) : undefined,
  };
}

interface ParseOptions {
  specType: 'ODCS' | 'ODPS';
  specVersion?: string;
  /** Optional ETag from the GET response — stored for If-Match on save. */
  etag?: string | null;
}

export function parseFromSource(
  raw: string,
  opts: ParseOptions,
): SchemaEditorState {
  const doc = _parseRaw(raw);
  const state: SchemaEditorState = {
    specType: opts.specType,
    specVersion: opts.specVersion ?? '',
    info: {
      name: typeof doc.name === 'string' ? doc.name : undefined,
      description: typeof doc.description === 'string' ? doc.description : undefined,
      version: typeof doc.version === 'string' ? doc.version : undefined,
      status: typeof doc.status === 'string' ? doc.status : undefined,
    },
    models: [],
    etag: opts.etag ?? null,
    originalRaw: raw,
  };

  if (opts.specType === 'ODCS') {
    const schema = doc.schema;
    if (Array.isArray(schema)) {
      state.models = schema.map((entry, idx) =>
        _odcsSchemaEntryToEditorModel(
          (entry as Record<string, unknown>) ?? {},
          `model_${idx + 1}`,
        ),
      );
    } else if (schema && typeof schema === 'object') {
      // Single-schema dict shape — wrap as one model.
      state.models = [
        _odcsSchemaEntryToEditorModel(
          schema as Record<string, unknown>,
          (typeof doc.name === 'string' ? doc.name : 'default'),
        ),
      ];
    }
    return state;
  }

  // ODPS — pull fields from outputPorts[*].contract.spec.schema.
  const product = doc.product as Record<string, unknown> | undefined;
  if (!product) return state;
  const outputPorts = product.outputPorts;
  if (!Array.isArray(outputPorts)) return state;
  const models: EditorModel[] = [];
  outputPorts.forEach((portRaw, portIdx) => {
    const port = portRaw as Record<string, unknown> | undefined;
    if (!port) return;
    const portName = typeof port.name === 'string' ? port.name : `port_${portIdx + 1}`;
    const contract = port.contract as Record<string, unknown> | undefined;
    const spec = contract?.spec as Record<string, unknown> | undefined;
    const portSchema = spec?.schema;
    if (Array.isArray(portSchema)) {
      portSchema.forEach((entry, idx) => {
        models.push(
          _odcsSchemaEntryToEditorModel(
            (entry as Record<string, unknown>) ?? {},
            `${portName}_${idx + 1}`,
          ),
        );
      });
    } else if (portSchema && typeof portSchema === 'object') {
      models.push(
        _odcsSchemaEntryToEditorModel(
          portSchema as Record<string, unknown>,
          portName,
        ),
      );
    }
  });
  state.models = models;
  return state;
}

/** Convenience round-trip helper used in tests. */
export function roundTrip(
  state: SchemaEditorState,
  format: 'JSON' | 'YAML' = 'JSON',
): SchemaEditorState {
  const compiled = compileToSource(state, { format, preserveOriginal: false });
  return parseFromSource(compiled.raw, {
    specType: state.specType,
    specVersion: state.specVersion,
    etag: state.etag,
  });
}

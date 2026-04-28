/**
 * OpenAPI Drift — pure-logic helpers for Phase 226.F4.
 *
 * The drift-detection contract (per task description):
 *   "Fetches /api/v1/openapi.json, hashes canonical JSON, diffs against
 *    committed snapshot. Rename/remove of documented field → PR-time
 *    failure."
 *
 * Naive byte-level hashing of the full schema would trip on every
 * description-string edit, every example-value tweak, and every server
 * URL flip between staging vs. prod. That would make the gate noisy
 * without surfacing the real signal: changes to the **API SHAPE** —
 * paths, methods, parameter names + types, request/response schemas,
 * component property names + types, required-field sets.
 *
 * This module separates the two concerns:
 *
 *   1. `extractSchemaShape(schema)` — produces a structural summary
 *      that captures only the parts that matter for client-API
 *      compatibility. Description edits and server URL flips do NOT
 *      change the shape; renaming a field, dropping a required
 *      property, or changing a parameter type DOES.
 *
 *   2. `canonicalize(value)` — recursively sorts object keys so two
 *      semantically-equal objects produce byte-identical JSON.
 *
 *   3. `hashCanonical(canonical)` — sha256 of the canonical string.
 *      The committed snapshot stores this hash plus the lightweight
 *      shape summary; on drift the spec runs `diffShapes` to print a
 *      human-readable diff so PR reviewers see exactly what changed.
 *
 * All functions are synchronous, side-effect-free, and exported so
 * `_guards.spec.ts` can unit-test every branch without booting a
 * browser or hitting the network.
 */

import { createHash } from 'crypto';

/**
 * Top-level OpenAPI 3.x schema shape. Untyped value-types kept loose —
 * we intentionally accept the live `/api/v1/openapi.json` payload
 * without trying to constrain every nested type.
 */
export type OpenAPISchema = {
  openapi?: string;
  info?: Record<string, unknown> & { version?: string; title?: string };
  paths?: Record<string, Record<string, unknown>>;
  components?: {
    schemas?: Record<string, ComponentSchemaShape>;
    [k: string]: unknown;
  };
  servers?: unknown;
  security?: unknown;
  tags?: unknown;
  [k: string]: unknown;
};

interface ComponentSchemaShape {
  type?: string;
  properties?: Record<string, { type?: string; format?: string; $ref?: string; nullable?: boolean }>;
  required?: string[];
  enum?: unknown[];
  $ref?: string;
  items?: { type?: string; $ref?: string };
  [k: string]: unknown;
}

interface OperationShape {
  /** Sorted list of path-/query-/header-parameter shape descriptors. */
  parameters: Array<{ name: string; in: string; required: boolean; type: string }>;
  /** Optional request body shape. */
  requestBody?: { required: boolean; contentTypes: string[]; ref?: string };
  /** status code → schema $ref or content type fallback. */
  responses: Record<string, { contentTypes: string[]; ref?: string }>;
  /** operationId, useful for renaming-detection. */
  operationId?: string;
  /** True iff `deprecated: true` on the operation. */
  deprecated: boolean;
}

export interface SchemaShape {
  /** OpenAPI version, e.g. "3.0.3". */
  openapi: string;
  /** API version pulled from `info.version` — drives major-bump signalling. */
  apiVersion?: string;
  /** path → method → OperationShape. Sorted by path then by method for stable hashing. */
  paths: Record<string, Record<string, OperationShape>>;
  /** component schema name → property summary. Sorted. */
  components: Record<
    string,
    {
      type?: string;
      properties: Array<{ name: string; type: string; required: boolean; ref?: string }>;
      enum?: unknown[];
    }
  >;
  /** Cardinality at capture time — useful for high-level sanity checks. */
  totals: { paths: number; operations: number; components: number };
}

const HTTP_METHODS = new Set([
  'get',
  'post',
  'put',
  'patch',
  'delete',
  'options',
  'head',
  'trace',
]);

/**
 * Recursively sort object keys so semantically-equal objects produce
 * byte-identical JSON. Arrays preserve their order — element order is
 * meaningful in OpenAPI (e.g. `parameters` ordering, response status
 * keys are stringified anyway). Non-plain values (strings, numbers,
 * null) pass through unchanged.
 */
export function canonicalize(value: unknown): unknown {
  if (value === null || typeof value !== 'object') return value;
  if (Array.isArray(value)) return value.map(canonicalize);
  const sorted: Record<string, unknown> = {};
  for (const k of Object.keys(value as Record<string, unknown>).sort()) {
    sorted[k] = canonicalize((value as Record<string, unknown>)[k]);
  }
  return sorted;
}

/**
 * Hash any value via sha256 of its canonical JSON form.
 *
 * Returned as lowercase hex so snapshots stay diff-stable across
 * platforms and the substring matcher in `report_uc_journey_test_coverage.py`
 * can be reused for hash-comparison if the team wants in the future.
 */
export function hashCanonical(value: unknown): string {
  const canonical = JSON.stringify(canonicalize(value));
  return createHash('sha256').update(canonical, 'utf8').digest('hex');
}

/**
 * Extract a parameter's drift-relevant fields. Strips description / example /
 * style / explode etc. so doc-only edits don't trigger a hash change.
 */
function shapeParameter(p: Record<string, unknown>): OperationShape['parameters'][number] {
  const schema = (p.schema as Record<string, unknown>) ?? {};
  const type =
    typeof schema.type === 'string'
      ? (schema.type as string)
      : typeof schema.$ref === 'string'
        ? (schema.$ref as string)
        : 'unknown';
  return {
    name: String(p.name ?? ''),
    in: String(p.in ?? ''),
    required: Boolean(p.required),
    type,
  };
}

function shapeRequestBody(rb: Record<string, unknown> | undefined): OperationShape['requestBody'] {
  if (!rb) return undefined;
  const content = (rb.content as Record<string, unknown>) ?? {};
  const contentTypes = Object.keys(content).sort();
  let ref: string | undefined;
  for (const ct of contentTypes) {
    const media = content[ct] as Record<string, unknown>;
    const sch = media?.schema as Record<string, unknown> | undefined;
    if (sch && typeof sch.$ref === 'string') {
      ref = sch.$ref;
      break;
    }
  }
  return { required: Boolean(rb.required), contentTypes, ref };
}

function shapeResponses(
  resp: Record<string, unknown> | undefined,
): OperationShape['responses'] {
  if (!resp) return {};
  const out: OperationShape['responses'] = {};
  for (const code of Object.keys(resp).sort()) {
    const body = (resp[code] as Record<string, unknown>) ?? {};
    const content = (body.content as Record<string, unknown>) ?? {};
    const contentTypes = Object.keys(content).sort();
    let ref: string | undefined;
    for (const ct of contentTypes) {
      const media = content[ct] as Record<string, unknown>;
      const sch = media?.schema as Record<string, unknown> | undefined;
      if (sch && typeof sch.$ref === 'string') {
        ref = sch.$ref;
        break;
      }
    }
    out[code] = { contentTypes, ref };
  }
  return out;
}

function shapeOperation(op: Record<string, unknown>): OperationShape {
  const params = Array.isArray(op.parameters) ? (op.parameters as Record<string, unknown>[]) : [];
  return {
    parameters: params
      .map(shapeParameter)
      .sort((a, b) => `${a.in}:${a.name}`.localeCompare(`${b.in}:${b.name}`)),
    requestBody: shapeRequestBody(op.requestBody as Record<string, unknown> | undefined),
    responses: shapeResponses(op.responses as Record<string, unknown> | undefined),
    operationId: typeof op.operationId === 'string' ? op.operationId : undefined,
    deprecated: Boolean(op.deprecated),
  };
}

function shapeComponentSchema(s: ComponentSchemaShape | undefined): SchemaShape['components'][string] {
  if (!s) return { type: undefined, properties: [], enum: undefined };
  const required = new Set(Array.isArray(s.required) ? s.required : []);
  const props = s.properties ?? {};
  const properties = Object.keys(props)
    .sort()
    .map((name) => {
      const p = props[name] ?? {};
      const type =
        typeof p.type === 'string'
          ? p.type
          : typeof p.$ref === 'string'
            ? `$ref:${p.$ref}`
            : 'unknown';
      const ref = typeof p.$ref === 'string' ? p.$ref : undefined;
      return { name, type, required: required.has(name), ref };
    });
  return {
    type: s.type,
    properties,
    enum: Array.isArray(s.enum) ? [...s.enum].map(String).sort() : undefined,
  };
}

/**
 * Reduce a full OpenAPI 3.x document to its drift-relevant shape.
 *
 * What gets captured:
 *   - openapi version
 *   - info.version
 *   - paths × methods → operationId, parameters (name/in/required/type),
 *     requestBody $ref + content types, response $refs + content types,
 *     deprecated flag
 *   - components.schemas → property names + types + required + enum
 *
 * What gets **discarded**:
 *   - All description / summary / example fields (description-only edits
 *     don't break clients)
 *   - servers / security / tags (deployment-specific or doc-grouping)
 *   - info.title / info.contact / info.license (doc metadata)
 */
export function extractSchemaShape(schema: OpenAPISchema): SchemaShape {
  const paths: SchemaShape['paths'] = {};
  let opCount = 0;
  for (const path of Object.keys(schema.paths ?? {}).sort()) {
    const pathItem = schema.paths![path] ?? {};
    const ops: Record<string, OperationShape> = {};
    for (const method of Object.keys(pathItem).sort()) {
      if (!HTTP_METHODS.has(method.toLowerCase())) continue;
      ops[method.toLowerCase()] = shapeOperation(
        pathItem[method] as Record<string, unknown>,
      );
      opCount++;
    }
    if (Object.keys(ops).length > 0) paths[path] = ops;
  }

  const components: SchemaShape['components'] = {};
  const compSchemas = schema.components?.schemas ?? {};
  for (const name of Object.keys(compSchemas).sort()) {
    components[name] = shapeComponentSchema(compSchemas[name]);
  }

  return {
    openapi: typeof schema.openapi === 'string' ? schema.openapi : 'unknown',
    apiVersion:
      typeof schema.info?.version === 'string' ? (schema.info.version as string) : undefined,
    paths,
    components,
    totals: {
      paths: Object.keys(paths).length,
      operations: opCount,
      components: Object.keys(components).length,
    },
  };
}

/**
 * Diff two SchemaShape values into a human-readable change list.
 *
 * Emits one bullet per breaking / non-breaking change. Categories:
 *   - REMOVED-PATH        path disappeared
 *   - ADDED-PATH          new path
 *   - REMOVED-OP          path × method disappeared
 *   - ADDED-OP            path × method added
 *   - PARAM-RENAMED       parameter name changed (in:name pair changed)
 *   - PARAM-TYPE-CHANGED  parameter type changed
 *   - PARAM-REQUIRED      parameter became required
 *   - REQUESTBODY-REQUIRED requestBody required toggled
 *   - REMOVED-COMPONENT   schema component disappeared
 *   - REMOVED-PROPERTY    property removed from a component
 *   - PROPERTY-TYPE-CHANGED  property type changed
 *   - PROPERTY-NEWLY-REQUIRED  property became required
 */
export function diffShapes(prev: SchemaShape, next: SchemaShape): string[] {
  const out: string[] = [];

  if (prev.openapi !== next.openapi) {
    out.push(`OPENAPI-VERSION: ${prev.openapi} → ${next.openapi}`);
  }
  if (prev.apiVersion !== next.apiVersion) {
    out.push(`API-VERSION: ${prev.apiVersion ?? 'unset'} → ${next.apiVersion ?? 'unset'}`);
  }

  const allPaths = new Set([...Object.keys(prev.paths), ...Object.keys(next.paths)]);
  for (const p of [...allPaths].sort()) {
    const a = prev.paths[p];
    const b = next.paths[p];
    if (!a) {
      out.push(`ADDED-PATH: ${p}`);
      continue;
    }
    if (!b) {
      out.push(`REMOVED-PATH: ${p}`);
      continue;
    }
    const allMethods = new Set([...Object.keys(a), ...Object.keys(b)]);
    for (const m of [...allMethods].sort()) {
      if (!a[m]) {
        out.push(`ADDED-OP: ${m.toUpperCase()} ${p}`);
        continue;
      }
      if (!b[m]) {
        out.push(`REMOVED-OP: ${m.toUpperCase()} ${p}`);
        continue;
      }
      // Compare operations
      const aOp = a[m];
      const bOp = b[m];
      const aParams = new Map(aOp.parameters.map((x) => [`${x.in}:${x.name}`, x] as const));
      const bParams = new Map(bOp.parameters.map((x) => [`${x.in}:${x.name}`, x] as const));
      for (const key of new Set([...aParams.keys(), ...bParams.keys()])) {
        const av = aParams.get(key);
        const bv = bParams.get(key);
        if (!av) {
          out.push(`PARAM-ADDED: ${m.toUpperCase()} ${p} (${key})`);
          continue;
        }
        if (!bv) {
          out.push(`PARAM-REMOVED: ${m.toUpperCase()} ${p} (${key})`);
          continue;
        }
        if (av.type !== bv.type) {
          out.push(
            `PARAM-TYPE-CHANGED: ${m.toUpperCase()} ${p} (${key}): ${av.type} → ${bv.type}`,
          );
        }
        if (!av.required && bv.required) {
          out.push(`PARAM-REQUIRED: ${m.toUpperCase()} ${p} (${key}) became required`);
        }
      }
      const aReqBody = aOp.requestBody;
      const bReqBody = bOp.requestBody;
      if (Boolean(aReqBody) !== Boolean(bReqBody)) {
        out.push(
          `REQUESTBODY-PRESENCE: ${m.toUpperCase()} ${p}: ${
            aReqBody ? 'was-present' : 'was-absent'
          } → ${bReqBody ? 'present' : 'absent'}`,
        );
      } else if (aReqBody && bReqBody && aReqBody.required !== bReqBody.required) {
        out.push(
          `REQUESTBODY-REQUIRED: ${m.toUpperCase()} ${p}: ${aReqBody.required} → ${bReqBody.required}`,
        );
      }
      const aResp = new Set(Object.keys(aOp.responses));
      const bResp = new Set(Object.keys(bOp.responses));
      for (const code of new Set([...aResp, ...bResp])) {
        if (!aResp.has(code)) out.push(`RESPONSE-ADDED: ${m.toUpperCase()} ${p} → ${code}`);
        else if (!bResp.has(code)) out.push(`RESPONSE-REMOVED: ${m.toUpperCase()} ${p} → ${code}`);
      }
    }
  }

  const allComponents = new Set([...Object.keys(prev.components), ...Object.keys(next.components)]);
  for (const c of [...allComponents].sort()) {
    const a = prev.components[c];
    const b = next.components[c];
    if (!a) {
      out.push(`ADDED-COMPONENT: ${c}`);
      continue;
    }
    if (!b) {
      out.push(`REMOVED-COMPONENT: ${c}`);
      continue;
    }
    const aProps = new Map(a.properties.map((p) => [p.name, p] as const));
    const bProps = new Map(b.properties.map((p) => [p.name, p] as const));
    for (const key of new Set([...aProps.keys(), ...bProps.keys()])) {
      const av = aProps.get(key);
      const bv = bProps.get(key);
      if (!av) {
        out.push(`PROPERTY-ADDED: ${c}.${key}`);
        continue;
      }
      if (!bv) {
        out.push(`REMOVED-PROPERTY: ${c}.${key}`);
        continue;
      }
      if (av.type !== bv.type) {
        out.push(`PROPERTY-TYPE-CHANGED: ${c}.${key}: ${av.type} → ${bv.type}`);
      }
      if (!av.required && bv.required) {
        out.push(`PROPERTY-NEWLY-REQUIRED: ${c}.${key} became required`);
      }
    }
  }

  return out;
}

/**
 * Categorise a diff list into breaking / non-breaking buckets so the
 * spec can pretty-print a focused PR comment without re-parsing the
 * change strings.
 */
export function classifyDiff(diff: string[]): { breaking: string[]; nonBreaking: string[] } {
  const breakingPrefixes = new Set([
    'REMOVED-PATH',
    'REMOVED-OP',
    'PARAM-REMOVED',
    'PARAM-TYPE-CHANGED',
    'PARAM-REQUIRED',
    'REQUESTBODY-PRESENCE',
    'REQUESTBODY-REQUIRED',
    'REMOVED-COMPONENT',
    'REMOVED-PROPERTY',
    'PROPERTY-TYPE-CHANGED',
    'PROPERTY-NEWLY-REQUIRED',
    'RESPONSE-REMOVED',
    'OPENAPI-VERSION',
  ]);
  const breaking: string[] = [];
  const nonBreaking: string[] = [];
  for (const entry of diff) {
    const prefix = entry.split(':')[0]?.split(' ')[0] ?? '';
    if (breakingPrefixes.has(prefix)) breaking.push(entry);
    else nonBreaking.push(entry);
  }
  return { breaking, nonBreaking };
}

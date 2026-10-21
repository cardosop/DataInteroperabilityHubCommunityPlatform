/**
 * odpsDocumentBuilder — pure functions for building, parsing, and merging
 * Bitol ODPS v1.0.0 data-product documents.
 *
 * Two invariants govern round-tripping:
 *  1. `buildODPSDocument(formData)` produces the canonical Bitol v1.0.0 shape
 *     from a form-driven snapshot.
 *  2. `parseODPSDocument(raw)` splits a document into the form-managed slice
 *     plus `unknownFields` — everything outside the form's vocabulary.
 *  3. `mergeODPSDocument(formData, unknownFields)` recombines the two so
 *     editing in the form never drops unknown content.
 */

import * as yaml from 'js-yaml';
import type {
  ODPSFormData,
  ODPSTeamMember,
  ODPSPort,
  ODPSInputSchema,
  ODPSQualityRule,
  ODPSSLAProperty,
} from '../../../shared/types/odps';

export const BITOL_V1_SCHEMA_URL =
  'https://bitol-io.github.io/open-data-product-standard/v1.0.0/schema.json';

export type OutputFormat = 'JSON' | 'YAML';

export interface ValidationError {
  field: string;
  message: string;
}

export interface ParseResult {
  formData: ODPSFormData;
  unknownFields: Record<string, unknown>;
}

type JsonObject = Record<string, unknown>;

/**
 * Top-level Bitol keys that the form owns. Anything else at root is kept in
 * `unknownFields` verbatim.
 */
const KNOWN_ROOT_KEYS = new Set([
  'schema',
  'apiVersion',
  'kind',
  'version',
  'status',
  'domain',
  'tenant',
  'visibility',
  'category',
  'type',
  'tags',
  'categories',
  'product',
]);

/**
 * Keys the form owns inside `product.*`. Everything else under `product` is
 * preserved in `unknownFields["product.<key>"]`.
 */
const KNOWN_PRODUCT_KEYS = new Set([
  'details',
  'team',
  'outputPorts',
  'inputPorts',
  'inputSchemas',
  'slaProperties',
  'qualityRules',
  'price',
  'license',
  'marketplace',
]);

const isPlainObject = (v: unknown): v is JsonObject =>
  typeof v === 'object' && v !== null && !Array.isArray(v);

export function buildODPSDocument(
  form: ODPSFormData,
  format: OutputFormat = 'JSON',
): string {
  return serialise(composeDocument(form, {}), format);
}

export function mergeODPSDocument(
  form: ODPSFormData,
  unknownFields: Record<string, unknown>,
  format: OutputFormat = 'JSON',
): string {
  return serialise(composeDocument(form, unknownFields), format);
}

export function parseODPSDocument(raw: string): ParseResult {
  const trimmed = raw.trim();
  if (!trimmed) {
    throw new Error('Empty ODPS document');
  }
  let parsed: unknown;
  try {
    parsed = JSON.parse(trimmed);
  } catch {
    parsed = yaml.load(trimmed);
  }
  if (!isPlainObject(parsed)) {
    throw new Error('ODPS document root must be an object');
  }
  return decomposeDocument(parsed);
}

export function validateODPSFormData(form: ODPSFormData): ValidationError[] {
  const errors: ValidationError[] = [];

  if (!form.schema || !form.schema.trim()) {
    errors.push({ field: 'schema', message: 'schema URL is required' });
  } else if (!isAbsoluteHttpUrl(form.schema.trim())) {
    errors.push({ field: 'schema', message: 'schema must be an absolute http(s) URL' });
  }

  if (!form.language.trim()) {
    errors.push({ field: 'language', message: 'language code is required' });
  }

  if (!form.productID.trim()) {
    errors.push({ field: 'productID', message: 'productID is required' });
  }

  if (!form.productName.trim()) {
    errors.push({
      field: 'productName',
      message: 'product.details name is required',
    });
  }

  form.team.forEach((m, i) => {
    if (!m.name.trim()) {
      errors.push({ field: `team[${i}].name`, message: 'member name is required' });
    }
    if (!m.email.trim()) {
      errors.push({ field: `team[${i}].email`, message: 'member email is required' });
    }
  });

  form.outputPorts.forEach((p, i) => {
    if (!p.name.trim()) {
      errors.push({
        field: `outputPorts[${i}].name`,
        message: 'output port name is required',
      });
    }
  });

  form.inputPorts.forEach((p, i) => {
    if (!p.name.trim()) {
      errors.push({
        field: `inputPorts[${i}].name`,
        message: 'input port name is required',
      });
    }
  });

  return errors;
}

function isAbsoluteHttpUrl(candidate: string): boolean {
  try {
    const parsed = new URL(candidate);
    return parsed.protocol === 'http:' || parsed.protocol === 'https:';
  } catch {
    return false;
  }
}

function serialise(doc: JsonObject, format: OutputFormat): string {
  if (format === 'YAML') {
    return yaml.dump(doc, { noRefs: true, lineWidth: 120 });
  }
  return JSON.stringify(doc, null, 2);
}

function composeDocument(
  form: ODPSFormData,
  unknownFields: Record<string, unknown>,
): JsonObject {
  // Separate unknown fields into root-level vs product-level keys.
  const rootExtras: JsonObject = {};
  const productExtras: JsonObject = {};
  for (const [k, v] of Object.entries(unknownFields)) {
    if (k.startsWith('product.')) {
      productExtras[k.slice('product.'.length)] = v;
    } else {
      rootExtras[k] = v;
    }
  }

  const language = form.language || 'en';

  // Per Bitol ODPS v1.0.0, product.details carries language-specific descriptive
  // content only (productID, name, description). Organisational metadata like
  // domain/tenant/visibility/status/version lives at the root — emitting it in
  // both places would produce a bloated, contradictory document.
  const detailsForLanguage: JsonObject = pruneUndefined({
    productID: form.productID,
    name: form.productName,
    description: form.productDescription || undefined,
  });

  const product: JsonObject = {
    details: { [language]: detailsForLanguage },
  };

  if (form.team.length) {
    product.team = { members: form.team.map(serializeTeamMember) };
  }
  if (form.outputPorts.length) {
    product.outputPorts = form.outputPorts.map(serializePort);
  }
  if (form.inputPorts.length) {
    product.inputPorts = form.inputPorts.map(serializePort);
  }
  if (form.inputSchemas.length) {
    product.inputSchemas = form.inputSchemas.map(serializeInputSchema);
  }
  if (form.slaProperties.length) {
    product.slaProperties = form.slaProperties.map(serializeSLA);
  }
  if (form.qualityRules.length) {
    product.qualityRules = form.qualityRules.map(serializeQuality);
  }
  if (form.marketplaceListed) {
    if (form.price !== undefined && form.currency) {
      product.price = { amount: form.price, currency: form.currency };
    }
    if (form.licenseType) {
      product.license = form.licenseType;
    }
    if (form.marketplaceDescription) {
      product.marketplace = { description: form.marketplaceDescription, listed: true };
    } else {
      product.marketplace = { listed: true };
    }
  }

  // Preserve unknown product-level keys under product.*
  Object.assign(product, productExtras);

  const linking: JsonObject = {};
  if (form.linkedAssetId) linking.assetId = form.linkedAssetId;
  if (form.linkedContractId) linking.contractId = form.linkedContractId;
  if (Object.keys(linking).length) {
    // Bitol has no native "linking" block; stash it under x-meshant to keep it
    // round-trippable without polluting the canonical namespace.
    const xMeshant = (product['x-meshant'] as JsonObject | undefined) ?? {};
    xMeshant.linking = linking;
    product['x-meshant'] = xMeshant;
  }

  const root: JsonObject = pruneUndefined({
    schema: form.schema || BITOL_V1_SCHEMA_URL,
    apiVersion: form.apiVersion || 'v1.0.0',
    kind: form.kind || 'DataProduct',
    version: form.productVersion || undefined,
    status: form.productStatus || undefined,
    domain: form.productDomain || undefined,
    tenant: form.productTenant || undefined,
    visibility: form.productVisibility || undefined,
    category: form.productCategory,
    type: form.productType,
    tags: form.tags.length ? form.tags : undefined,
    categories: form.categories.length ? form.categories : undefined,
    product,
  });

  // Put unknown root-level extras back.
  Object.assign(root, rootExtras);

  return root;
}

function decomposeDocument(doc: JsonObject): ParseResult {
  const unknownFields: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(doc)) {
    if (!KNOWN_ROOT_KEYS.has(k)) unknownFields[k] = v;
  }

  const product = isPlainObject(doc.product) ? doc.product : {};
  for (const [k, v] of Object.entries(product)) {
    if (!KNOWN_PRODUCT_KEYS.has(k) && k !== 'x-meshant') {
      unknownFields[`product.${k}`] = v;
    }
  }

  const details = isPlainObject(product.details) ? product.details : {};
  const language =
    Object.keys(details).find((k) => isPlainObject(details[k])) || 'en';
  const d = isPlainObject(details[language]) ? (details[language] as JsonObject) : {};

  const xMeshant = isPlainObject(product['x-meshant'])
    ? (product['x-meshant'] as JsonObject)
    : {};
  const linking = isPlainObject(xMeshant.linking)
    ? (xMeshant.linking as JsonObject)
    : {};

  const price = isPlainObject(product.price) ? (product.price as JsonObject) : undefined;
  const marketplace = isPlainObject(product.marketplace)
    ? (product.marketplace as JsonObject)
    : undefined;

  const team = isPlainObject(product.team) ? (product.team as JsonObject) : {};
  const teamMembers = Array.isArray(team.members) ? team.members : [];

  const formData: ODPSFormData = {
    schema: asString(doc.schema) || BITOL_V1_SCHEMA_URL,
    apiVersion: asString(doc.apiVersion) || 'v1.0.0',
    kind: asString(doc.kind) || 'DataProduct',

    language,
    productID: asString(d.productID),
    productName: asString(d.name),
    productVersion: asString(doc.version),
    productStatus: asString(doc.status),
    productDescription: asString(d.description),
    productDomain: asString(doc.domain) || asString(d.domain),
    productTenant: asString(doc.tenant) || asString(d.tenant),
    productVisibility: asString(doc.visibility) || asString(d.visibility),
    productCategory: optionalString(doc.category ?? d.category),
    productType: optionalString(doc.type ?? d.type),

    team: teamMembers.filter(isPlainObject).map((m) => ({
      name: asString(m.name),
      email: asString(m.email),
      role: optionalString(m.role),
      id: optionalString(m.id),
    })) as ODPSTeamMember[],

    outputPorts: asArray(product.outputPorts).filter(isPlainObject).map(parsePort),
    inputPorts: asArray(product.inputPorts).filter(isPlainObject).map(parsePort),

    inputSchemas: asArray(product.inputSchemas).filter(isPlainObject).map(parseInputSchema),

    slaProperties: asArray(product.slaProperties).filter(isPlainObject).map((s) => ({
      property: asString(s.property),
      value: asString(s.value),
      unit: optionalString(s.unit),
    })) as ODPSSLAProperty[],

    qualityRules: asArray(product.qualityRules).filter(isPlainObject).map((q) => ({
      name: asString(q.name),
      type: optionalString(q.type),
      expression: optionalString(q.expression),
    })) as ODPSQualityRule[],

    tags: asArray(doc.tags).filter((t): t is string => typeof t === 'string'),
    categories: asArray(doc.categories).filter((t): t is string => typeof t === 'string'),

    price: price && typeof price.amount === 'number' ? price.amount : undefined,
    currency: price ? optionalString(price.currency) : undefined,
    licenseType: optionalString(product.license),
    marketplaceListed: marketplace?.listed === true || !!price,
    marketplaceDescription: marketplace ? optionalString(marketplace.description) : undefined,

    linkedAssetId: optionalString(linking.assetId) ?? null,
    linkedContractId: optionalString(linking.contractId) ?? null,
  };

  return { formData, unknownFields };
}

function serializeTeamMember(m: ODPSTeamMember): JsonObject {
  return pruneUndefined({
    name: m.name,
    email: m.email,
    role: m.role || undefined,
    id: m.id || undefined,
  });
}

function serializePort(p: ODPSPort): JsonObject {
  return pruneUndefined({
    name: p.name,
    description: p.description || undefined,
    contractId: p.contractId || undefined,
    tags: p.tags && p.tags.length ? p.tags : undefined,
    type: p.type || undefined,
  });
}

function parsePort(raw: JsonObject): ODPSPort {
  return {
    name: asString(raw.name),
    description: optionalString(raw.description),
    contractId: optionalString(raw.contractId),
    type: optionalString(raw.type),
    tags: asArray(raw.tags).filter((t): t is string => typeof t === 'string'),
  };
}

function serializeInputSchema(s: ODPSInputSchema): JsonObject {
  return pruneUndefined({
    name: s.name,
    fields: s.fields.map((f) =>
      pruneUndefined({
        name: f.name,
        type: f.type,
        description: f.description || undefined,
        required: f.required || undefined,
      }),
    ),
  });
}

function parseInputSchema(raw: JsonObject): ODPSInputSchema {
  return {
    name: asString(raw.name),
    fields: asArray(raw.fields).filter(isPlainObject).map((f) => ({
      name: asString(f.name),
      type: asString(f.type),
      description: optionalString(f.description),
      required: f.required === true,
    })),
  };
}

function serializeSLA(s: ODPSSLAProperty): JsonObject {
  return pruneUndefined({
    property: s.property,
    value: s.value,
    unit: s.unit || undefined,
  });
}

function serializeQuality(q: ODPSQualityRule): JsonObject {
  return pruneUndefined({
    name: q.name,
    type: q.type || undefined,
    expression: q.expression || undefined,
  });
}

function asString(v: unknown): string {
  return typeof v === 'string' ? v : '';
}

function optionalString(v: unknown): string | undefined {
  return typeof v === 'string' && v.length > 0 ? v : undefined;
}

function asArray(v: unknown): unknown[] {
  return Array.isArray(v) ? v : [];
}

function pruneUndefined(obj: JsonObject): JsonObject {
  const result: JsonObject = {};
  for (const [k, v] of Object.entries(obj)) {
    if (v !== undefined) result[k] = v;
  }
  return result;
}

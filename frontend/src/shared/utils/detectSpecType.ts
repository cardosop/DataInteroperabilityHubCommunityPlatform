/**
 * Contract spec type auto-detection.
 *
 * Detects whether a YAML/JSON contract document is ODPS, ODCS, HubContract,
 * or unknown. Detection order matches the backend logic in:
 *   - hub/apps/contracts/spec_detection.py
 *   - hub/apps/contracts/odps_version_detection.py
 *
 * SECURITY: Uses js-yaml v4+ DEFAULT_SCHEMA which rejects dangerous tags
 * like !!js/function, preventing arbitrary code execution from user-pasted YAML.
 */

import * as yaml from 'js-yaml';

export interface DetectedSpec {
  type: 'ODPS' | 'ODCS' | 'HUB' | 'UNKNOWN';
  version?: string;
}

/**
 * Detect the contract specification type from raw YAML or JSON content.
 *
 * @param content - Raw string content (JSON or YAML)
 * @returns Detected spec type and optional version
 */
export function detectSpecType(content: string): DetectedSpec {
  if (!content || typeof content !== 'string' || !content.trim()) {
    return { type: 'UNKNOWN' };
  }

  let parsed: unknown;
  try {
    // Try JSON first (faster, unambiguous)
    if (content.trimStart().startsWith('{')) {
      parsed = JSON.parse(content);
    } else {
      // SECURITY: yaml.load with DEFAULT_SCHEMA rejects !!js/function etc.
      parsed = yaml.load(content, { schema: yaml.DEFAULT_SCHEMA });
    }
  } catch {
    return { type: 'UNKNOWN' };
  }

  // Must be a non-null object (not array, string, number, null)
  if (parsed === null || typeof parsed !== 'object' || Array.isArray(parsed)) {
    return { type: 'UNKNOWN' };
  }

  const doc = parsed as Record<string, unknown>;

  // 1. Bitol ODPS — schema URL contains bitol-io.github.io (most specific, check first)
  if (typeof doc.schema === 'string' && doc.schema.includes('bitol-io.github.io')) {
    const match = doc.schema.match(/v([\d.]+)/);
    return { type: 'ODPS', version: match ? `bitol-${match[1]}` : 'bitol' };
  }

  // 2. Pre-Bitol ODPS — product.details + schema URL from opendataproducts.org
  const product = doc.product as Record<string, unknown> | undefined;
  if (
    product &&
    typeof product === 'object' &&
    'details' in product &&
    typeof doc.schema === 'string' &&
    (doc.schema.includes('opendataproducts.org') ||
      doc.schema.includes('schemas.opendataproducts.io'))
  ) {
    const match = doc.schema.match(/v([\d.]+)/);
    const version =
      match?.[1] ?? (typeof doc.version === 'string' ? doc.version : undefined);
    return { type: 'ODPS', version };
  }

  // 3. ODCS — apiVersion + kind === 'DataContract'
  if (doc.apiVersion && doc.kind === 'DataContract') {
    const apiVersion = String(doc.apiVersion);
    // Extract version from patterns like "odcs/v3", "odcs.io/v3.0.2"
    // Match the last /vX.Y.Z or /vX segment (after the last slash)
    const slashMatch = apiVersion.match(/\/v?([\d]+(?:\.[\d]+)*)\s*$/);
    const version = slashMatch ? `v${slashMatch[1]}` : apiVersion;
    return { type: 'ODCS', version };
  }

  // 4. DataContract.com / Bitol data contract spec
  if (doc.dataContractSpecification) {
    return { type: 'ODCS', version: String(doc.dataContractSpecification) };
  }

  // 5. HubContract — internal Meshant format
  if (doc.hub_contract || doc.meshant) {
    return { type: 'HUB' };
  }

  return { type: 'UNKNOWN' };
}

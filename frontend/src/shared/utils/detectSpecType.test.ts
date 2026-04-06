/**
 * Tests for detectSpecType — contract format auto-detection.
 *
 * TDD: These tests are written BEFORE the implementation.
 * Detection logic verified against backend:
 *   - hub/apps/contracts/spec_detection.py
 *   - hub/apps/contracts/odps_version_detection.py
 * Fixtures sourced from tests/fixtures/odps/ and examples/contracts/.
 */

import { describe, expect, it } from 'vitest';
import { detectSpecType } from './detectSpecType';

// ---------------------------------------------------------------------------
// ODPS — Pre-Bitol (schema URL + product.details)
// ---------------------------------------------------------------------------

describe('detectSpecType — ODPS pre-Bitol', () => {
  it('detects ODPS v4.1 JSON', () => {
    const content = JSON.stringify({
      schema: 'https://opendataproducts.org/schema/v4.1',
      version: '4.1',
      product: {
        details: {
          en: { productID: 'test', name: 'Test Product' },
        },
      },
    });
    const result = detectSpecType(content);
    expect(result.type).toBe('ODPS');
    expect(result.version).toBe('4.1');
  });

  it('detects ODPS v4.0 JSON', () => {
    const content = JSON.stringify({
      schema: 'https://opendataproducts.org/schema/v4.0',
      version: '4.0',
      product: { details: { en: { productID: 'p', name: 'P' } } },
    });
    const result = detectSpecType(content);
    expect(result.type).toBe('ODPS');
    expect(result.version).toBe('4.0');
  });

  it('detects ODPS v4.2 JSON', () => {
    const content = JSON.stringify({
      schema: 'https://opendataproducts.org/schema/v4.2',
      version: '4.2',
      product: { details: { en: { productID: 'p', name: 'P' } } },
    });
    const result = detectSpecType(content);
    expect(result.type).toBe('ODPS');
    expect(result.version).toBe('4.2');
  });

  it('detects ODPS v3.x JSON', () => {
    const content = JSON.stringify({
      schema: 'https://opendataproducts.org/schema/v3.0',
      version: '3.0',
      product: { details: { en: { productID: 'p', name: 'P' } } },
    });
    const result = detectSpecType(content);
    expect(result.type).toBe('ODPS');
    expect(result.version).toBe('3.0');
  });

  it('detects ODPS v2.x JSON', () => {
    const content = JSON.stringify({
      schema: 'https://opendataproducts.org/schema/v2.0',
      version: '2.0',
      product: { details: { en: { productID: 'p', name: 'P' } } },
    });
    const result = detectSpecType(content);
    expect(result.type).toBe('ODPS');
    expect(result.version).toBe('2.0');
  });

  it('detects ODPS v1.9 JSON', () => {
    const content = JSON.stringify({
      schema: 'https://opendataproducts.org/schema/v1.9',
      version: '1.9',
      product: {
        details: {
          en: {
            productID: 'sample-product-v1.9',
            name: 'Sample Data Product v1.9',
          },
        },
        contract: {
          contractURL: 'https://example.com/contracts/sample-product-v1.9',
        },
      },
    });
    const result = detectSpecType(content);
    expect(result.type).toBe('ODPS');
    expect(result.version).toBe('1.9');
  });

  it('detects ODPS from schemas.opendataproducts.io URL', () => {
    const content = JSON.stringify({
      schema: 'https://schemas.opendataproducts.io/spec/v4.1',
      version: '4.1',
      product: { details: { en: { productID: 'p', name: 'P' } } },
    });
    const result = detectSpecType(content);
    expect(result.type).toBe('ODPS');
    expect(result.version).toBe('4.1');
  });

  it('falls back to version field when schema URL has no version', () => {
    const content = JSON.stringify({
      schema: 'https://opendataproducts.org/schema/',
      version: '4.1',
      product: { details: { en: { productID: 'p', name: 'P' } } },
    });
    const result = detectSpecType(content);
    expect(result.type).toBe('ODPS');
    expect(result.version).toBe('4.1');
  });
});

// ---------------------------------------------------------------------------
// ODPS — Bitol (bitol-io.github.io schema URL)
// ---------------------------------------------------------------------------

describe('detectSpecType — ODPS Bitol', () => {
  it('detects Bitol ODPS v1.0.0 from YAML', () => {
    const content = [
      'schema: https://bitol-io.github.io/open-data-product-standard/v1.0.0/schema.json',
      'kind: DataProduct',
      'apiVersion: v1.0.0',
      'product:',
      '  details:',
      '    en:',
      '      productID: fixture-bitol-v100',
      '      name: Bitol ODPS v1.0.0 Minimal Fixture',
    ].join('\n');
    const result = detectSpecType(content);
    expect(result.type).toBe('ODPS');
    expect(result.version).toBe('bitol-1.0.0');
  });

  it('detects Bitol ODPS v0.9.0', () => {
    const content = JSON.stringify({
      schema:
        'https://bitol-io.github.io/open-data-product-standard/v0.9.0/schema.json',
      kind: 'DataProduct',
      apiVersion: 'v0.9.0',
      product: { details: { en: { productID: 'p', name: 'P' } } },
    });
    const result = detectSpecType(content);
    expect(result.type).toBe('ODPS');
    expect(result.version).toBe('bitol-0.9.0');
  });

  it('Bitol detection takes priority over ODCS kind check', () => {
    // Bitol ODPS has kind: DataProduct (not DataContract), but both have apiVersion.
    // The schema URL must be the primary discriminator.
    const content = JSON.stringify({
      schema:
        'https://bitol-io.github.io/open-data-product-standard/v1.0.0/schema.json',
      kind: 'DataProduct',
      apiVersion: 'v1.0.0',
      product: { details: { en: { productID: 'p', name: 'P' } } },
    });
    const result = detectSpecType(content);
    expect(result.type).toBe('ODPS');
    // Must NOT be detected as ODCS even though it has apiVersion + kind
  });
});

// ---------------------------------------------------------------------------
// ODCS (apiVersion + kind: "DataContract")
// ---------------------------------------------------------------------------

describe('detectSpecType — ODCS', () => {
  it('detects ODCS v3 minimal JSON', () => {
    const content = JSON.stringify({
      apiVersion: 'odcs/v3',
      kind: 'DataContract',
      id: 'minimal-contract',
      name: 'Minimal Contract Example',
      version: '1.0.0',
      schema: {
        fields: [
          { name: 'id', type: 'string' },
          { name: 'name', type: 'string' },
        ],
      },
    });
    const result = detectSpecType(content);
    expect(result.type).toBe('ODCS');
    expect(result.version).toBe('v3');
  });

  it('detects ODCS v3.0.2 from YAML', () => {
    const content = [
      'apiVersion: odcs.io/v3.0.2',
      'kind: DataContract',
      'id: fixture-v302-reference',
      'name: ODCS v3.0.2 Reference Fixture',
      'version: 1.0.0',
      'schema:',
      '  - name: customers',
      '    fields:',
      '      - name: id',
      '        type: string',
    ].join('\n');
    const result = detectSpecType(content);
    expect(result.type).toBe('ODCS');
    expect(result.version).toContain('3.0.2');
  });

  it('detects ODCS v3.1.0 from YAML', () => {
    const content = [
      'apiVersion: odcs.io/v3.1.0',
      'kind: DataContract',
      'id: fixture-v310-minimal',
      'name: ODCS v3.1.0 Minimal Fixture',
    ].join('\n');
    const result = detectSpecType(content);
    expect(result.type).toBe('ODCS');
    expect(result.version).toContain('3.1.0');
  });

  it('detects ODCS v2.2.2', () => {
    const content = JSON.stringify({
      apiVersion: 'odcs/v2.2.2',
      kind: 'DataContract',
      id: 'test',
      schema: { fields: [] },
    });
    const result = detectSpecType(content);
    expect(result.type).toBe('ODCS');
    expect(result.version).toContain('2.2.2');
  });
});

// ---------------------------------------------------------------------------
// DataContract.com (Bitol data contract spec — dataContractSpecification key)
// ---------------------------------------------------------------------------

describe('detectSpecType — DataContract.com (Bitol)', () => {
  it('detects DataContract.com v1.0.0', () => {
    const content = JSON.stringify({
      dataContractSpecification: '1.0.0',
      id: 'test-dc',
      info: { title: 'Test', version: '1.0.0' },
    });
    const result = detectSpecType(content);
    expect(result.type).toBe('ODCS');
    expect(result.version).toBe('1.0.0');
  });

  it('detects DataContract.com v0.9.0', () => {
    const content = JSON.stringify({
      dataContractSpecification: '0.9.0',
      id: 'test-dc',
    });
    const result = detectSpecType(content);
    expect(result.type).toBe('ODCS');
    expect(result.version).toBe('0.9.0');
  });
});

// ---------------------------------------------------------------------------
// HubContract (internal Meshant format)
// ---------------------------------------------------------------------------

describe('detectSpecType — HubContract', () => {
  it('detects hub_contract key', () => {
    const content = JSON.stringify({
      hub_contract: { version: '1.0.0', info: { name: 'Test' } },
    });
    const result = detectSpecType(content);
    expect(result.type).toBe('HUB');
  });

  it('detects meshant key', () => {
    const content = JSON.stringify({
      meshant: { version: '1.0.0' },
    });
    const result = detectSpecType(content);
    expect(result.type).toBe('HUB');
  });
});

// ---------------------------------------------------------------------------
// UNKNOWN — fallback cases
// ---------------------------------------------------------------------------

describe('detectSpecType — UNKNOWN / fallback', () => {
  it('returns UNKNOWN for empty string', () => {
    expect(detectSpecType('').type).toBe('UNKNOWN');
  });

  it('returns UNKNOWN for invalid JSON', () => {
    expect(detectSpecType('{bad json!!!').type).toBe('UNKNOWN');
  });

  it('returns UNKNOWN for invalid YAML', () => {
    expect(detectSpecType(':::not yaml:::').type).toBe('UNKNOWN');
  });

  it('returns UNKNOWN for plain text', () => {
    expect(detectSpecType('Hello, this is just a text file.').type).toBe('UNKNOWN');
  });

  it('returns UNKNOWN for null/undefined-ish values parsed from JSON', () => {
    expect(detectSpecType('null').type).toBe('UNKNOWN');
    expect(detectSpecType('"just a string"').type).toBe('UNKNOWN');
    expect(detectSpecType('42').type).toBe('UNKNOWN');
  });

  it('returns UNKNOWN for JSON with no recognizable keys', () => {
    const content = JSON.stringify({ foo: 'bar', baz: 123 });
    expect(detectSpecType(content).type).toBe('UNKNOWN');
  });

  it('returns UNKNOWN for YAML with no recognizable keys', () => {
    const content = 'foo: bar\nbaz: 123\n';
    expect(detectSpecType(content).type).toBe('UNKNOWN');
  });
});

// ---------------------------------------------------------------------------
// SECURITY — malicious YAML must not execute code
// ---------------------------------------------------------------------------

describe('detectSpecType — security', () => {
  it('does NOT execute !!js/function payloads (returns UNKNOWN)', () => {
    // js-yaml v4+ safe schema rejects !!js/function by default.
    // If this test ever passes with type !== 'UNKNOWN', we have a security issue.
    const malicious = '!!js/function "function() { return process.exit(1); }"';
    const result = detectSpecType(malicious);
    expect(result.type).toBe('UNKNOWN');
  });

  it('does NOT execute !!python/object payloads', () => {
    const malicious = '!!python/object/apply:os.system ["echo pwned"]';
    const result = detectSpecType(malicious);
    expect(result.type).toBe('UNKNOWN');
  });

  it('handles extremely large input without crashing', () => {
    // 1MB of repeated YAML — should not OOM or hang
    const large = 'key: value\n'.repeat(100_000);
    const result = detectSpecType(large);
    expect(result.type).toBe('UNKNOWN');
  });
});

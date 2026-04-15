/**
 * Tests for odpsDocumentBuilder — Bitol ODPS v1.0.0 document build/parse/merge.
 *
 * Covers:
 *  - buildODPSDocument: produces a valid Bitol v1.0.0 JSON/YAML document with
 *    the correct schema URL, apiVersion, kind and language-keyed product.details.
 *  - parseODPSDocument: round-trips a built document, recovering all form data
 *    and preserving any unknown fields that the form does not manage.
 *  - mergeODPSDocument: merging form data with a previously captured set of
 *    unknown fields yields a document that keeps the foreign fields intact.
 *  - Required-field validation: schema URL, productID, and product.details.
 */

import { describe, it, expect } from 'vitest';
import {
  buildODPSDocument,
  parseODPSDocument,
  mergeODPSDocument,
  BITOL_V1_SCHEMA_URL,
  validateODPSFormData,
} from './odpsDocumentBuilder';
import type { ODPSFormData } from '../../../shared/types/odps';

const minimalFormData = (): ODPSFormData => ({
  schema: BITOL_V1_SCHEMA_URL,
  apiVersion: 'v1.0.0',
  kind: 'DataProduct',
  language: 'en',
  productID: 'dp-test-001',
  productName: 'Test Product',
  productVersion: '1.0.0',
  productStatus: 'active',
  productDescription: 'A product used for unit testing.',
  productDomain: 'marketing',
  productTenant: 'tenant-a',
  productVisibility: 'internal',
  productCategory: undefined,
  productType: undefined,
  team: [],
  outputPorts: [],
  inputPorts: [],
  inputSchemas: [],
  slaProperties: [],
  qualityRules: [],
  tags: [],
  categories: [],
  price: undefined,
  currency: undefined,
  licenseType: undefined,
  marketplaceListed: false,
  marketplaceDescription: undefined,
  linkedAssetId: null,
  linkedContractId: null,
});

describe('buildODPSDocument', () => {
  it('builds a valid Bitol v1.0.0 JSON document with schema URL, apiVersion and kind', () => {
    const raw = buildODPSDocument(minimalFormData(), 'JSON');
    const parsed = JSON.parse(raw);
    expect(parsed.schema).toBe(BITOL_V1_SCHEMA_URL);
    expect(parsed.apiVersion).toBe('v1.0.0');
    expect(parsed.kind).toBe('DataProduct');
    expect(parsed.version).toBe('1.0.0');
    expect(parsed.status).toBe('active');
    expect(parsed.domain).toBe('marketing');
    expect(parsed.tenant).toBe('tenant-a');
  });

  it('places product details under product.details keyed by language', () => {
    const raw = buildODPSDocument(minimalFormData(), 'JSON');
    const parsed = JSON.parse(raw);
    expect(parsed.product.details).toBeDefined();
    expect(parsed.product.details.en).toBeDefined();
    expect(parsed.product.details.en.productID).toBe('dp-test-001');
    expect(parsed.product.details.en.name).toBe('Test Product');
    expect(parsed.product.details.en.description).toBe(
      'A product used for unit testing.',
    );
  });

  it('keeps organisational metadata at root — never duplicated inside product.details', () => {
    const raw = buildODPSDocument(minimalFormData(), 'JSON');
    const parsed = JSON.parse(raw);
    // These live at root only per Bitol v1.0.0.
    expect(parsed.domain).toBe('marketing');
    expect(parsed.tenant).toBe('tenant-a');
    expect(parsed.visibility).toBe('internal');
    expect(parsed.product.details.en.domain).toBeUndefined();
    expect(parsed.product.details.en.tenant).toBeUndefined();
    expect(parsed.product.details.en.visibility).toBeUndefined();
  });

  it('emits YAML when format is YAML', () => {
    const raw = buildODPSDocument(minimalFormData(), 'YAML');
    expect(raw).toMatch(/^schema:\s+/m);
    expect(raw).toMatch(/^kind:\s+DataProduct/m);
    expect(raw).toMatch(/productID:\s+dp-test-001/);
  });

  it('emits team as an array of members under product.team', () => {
    const data = minimalFormData();
    data.team = [
      { name: 'Alice', email: 'alice@example.com', role: 'owner' },
      { name: 'Bob', email: 'bob@example.com', role: 'maintainer' },
    ];
    const parsed = JSON.parse(buildODPSDocument(data, 'JSON'));
    expect(parsed.product.team.members).toHaveLength(2);
    expect(parsed.product.team.members[0].name).toBe('Alice');
  });

  it('emits output ports with contractId and tags', () => {
    const data = minimalFormData();
    data.outputPorts = [
      { name: 'api-out', contractId: 'c-uuid-001', tags: ['production'] },
    ];
    const parsed = JSON.parse(buildODPSDocument(data, 'JSON'));
    expect(parsed.product.outputPorts).toHaveLength(1);
    expect(parsed.product.outputPorts[0].name).toBe('api-out');
    expect(parsed.product.outputPorts[0].contractId).toBe('c-uuid-001');
    expect(parsed.product.outputPorts[0].tags).toEqual(['production']);
  });

  it('omits empty optional collections (no empty team/ports arrays)', () => {
    const parsed = JSON.parse(buildODPSDocument(minimalFormData(), 'JSON'));
    expect(parsed.product.team).toBeUndefined();
    expect(parsed.product.outputPorts).toBeUndefined();
    expect(parsed.product.inputPorts).toBeUndefined();
  });

  it('includes marketplace fields when marketplaceListed is true', () => {
    const data = minimalFormData();
    data.marketplaceListed = true;
    data.price = 99.99;
    data.currency = 'USD';
    data.licenseType = 'commercial';
    data.marketplaceDescription = 'Premium data product';
    const parsed = JSON.parse(buildODPSDocument(data, 'JSON'));
    expect(parsed.product.price).toEqual({ amount: 99.99, currency: 'USD' });
    expect(parsed.product.license).toBe('commercial');
  });
});

describe('parseODPSDocument', () => {
  it('round-trips built documents with all known fields preserved', () => {
    const original = minimalFormData();
    original.team = [{ name: 'Alice', email: 'alice@example.com', role: 'owner' }];
    original.outputPorts = [
      { name: 'api-out', contractId: 'c-uuid-001', tags: ['production'] },
    ];
    original.tags = ['finance', 'gold'];

    const raw = buildODPSDocument(original, 'JSON');
    const { formData, unknownFields } = parseODPSDocument(raw);

    expect(formData.productID).toBe(original.productID);
    expect(formData.productName).toBe(original.productName);
    expect(formData.productDescription).toBe(original.productDescription);
    expect(formData.team).toHaveLength(1);
    expect(formData.team[0].name).toBe('Alice');
    expect(formData.outputPorts).toHaveLength(1);
    expect(formData.outputPorts[0].contractId).toBe('c-uuid-001');
    expect(formData.tags).toEqual(['finance', 'gold']);
    expect(unknownFields).toEqual({});
  });

  it('round-trips organisational metadata (domain/tenant/visibility/status/version) at root', () => {
    const original = minimalFormData();
    const raw = buildODPSDocument(original, 'JSON');
    const { formData } = parseODPSDocument(raw);
    expect(formData.productDomain).toBe(original.productDomain);
    expect(formData.productTenant).toBe(original.productTenant);
    expect(formData.productVisibility).toBe(original.productVisibility);
    expect(formData.productStatus).toBe(original.productStatus);
    expect(formData.productVersion).toBe(original.productVersion);
  });

  it('still reads legacy documents where domain/tenant sit inside product.details', () => {
    // Some pre-existing Bitol documents nested organisational metadata under
    // details[language]. Parser must tolerate that shape and surface the
    // values on the form even if build() emits them at root.
    const legacy = {
      schema: BITOL_V1_SCHEMA_URL,
      apiVersion: 'v1.0.0',
      kind: 'DataProduct',
      product: {
        details: {
          en: {
            productID: 'dp-legacy',
            name: 'Legacy',
            domain: 'legacy-domain',
            tenant: 'legacy-tenant',
            visibility: 'private',
          },
        },
      },
    };
    const { formData } = parseODPSDocument(JSON.stringify(legacy));
    expect(formData.productDomain).toBe('legacy-domain');
    expect(formData.productTenant).toBe('legacy-tenant');
    expect(formData.productVisibility).toBe('private');
  });

  it('parses YAML documents', () => {
    const raw = buildODPSDocument(minimalFormData(), 'YAML');
    const { formData } = parseODPSDocument(raw);
    expect(formData.productID).toBe('dp-test-001');
    expect(formData.schema).toBe(BITOL_V1_SCHEMA_URL);
  });

  it('captures unknown top-level fields in unknownFields', () => {
    const doc = {
      schema: BITOL_V1_SCHEMA_URL,
      apiVersion: 'v1.0.0',
      kind: 'DataProduct',
      customRootField: { answer: 42 },
      product: {
        details: { en: { productID: 'dp-x', name: 'X' } },
        customProductField: 'vendor-specific',
      },
    };
    const { unknownFields } = parseODPSDocument(JSON.stringify(doc));
    expect(unknownFields.customRootField).toEqual({ answer: 42 });
    expect(unknownFields['product.customProductField']).toBe('vendor-specific');
  });

  it('throws when JSON/YAML is malformed', () => {
    expect(() => parseODPSDocument('{not valid json')).toThrow();
  });
});

describe('mergeODPSDocument', () => {
  it('preserves unknown fields when merging edited form data', () => {
    const doc = {
      schema: BITOL_V1_SCHEMA_URL,
      apiVersion: 'v1.0.0',
      kind: 'DataProduct',
      customRootField: { answer: 42 },
      product: {
        details: { en: { productID: 'dp-x', name: 'X' } },
        customProductField: 'vendor-specific',
      },
    };
    const { formData, unknownFields } = parseODPSDocument(JSON.stringify(doc));
    formData.productName = 'Renamed Product';
    const merged = mergeODPSDocument(formData, unknownFields, 'JSON');
    const parsed = JSON.parse(merged);
    expect(parsed.customRootField).toEqual({ answer: 42 });
    expect(parsed.product.customProductField).toBe('vendor-specific');
    expect(parsed.product.details.en.name).toBe('Renamed Product');
  });
});

describe('validateODPSFormData', () => {
  it('flags missing schema URL', () => {
    const data = minimalFormData();
    data.schema = '';
    const errors = validateODPSFormData(data);
    expect(errors.some((e) => e.field === 'schema')).toBe(true);
  });

  it('flags missing productID', () => {
    const data = minimalFormData();
    data.productID = '';
    const errors = validateODPSFormData(data);
    expect(errors.some((e) => e.field === 'productID')).toBe(true);
  });

  it('flags missing productName (product.details required content)', () => {
    const data = minimalFormData();
    data.productName = '';
    const errors = validateODPSFormData(data);
    expect(errors.some((e) => e.field === 'productName')).toBe(true);
  });

  it('returns empty array for a complete form', () => {
    expect(validateODPSFormData(minimalFormData())).toEqual([]);
  });

  it('rejects a schema URL that is not a valid URL', () => {
    const data = minimalFormData();
    data.schema = 'not a url';
    const errors = validateODPSFormData(data);
    expect(errors.some((e) => e.field === 'schema')).toBe(true);
  });
});

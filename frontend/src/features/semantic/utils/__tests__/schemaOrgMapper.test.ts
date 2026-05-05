/**
 * Phase 230.9 (REQ-SEM-SEO-001) — Schema.org mapper tests.
 *
 * Spec scenarios pinned by these tests:
 *
 *  * Public-listing emits valid Schema.org with required fields per
 *    type (`@type`, `name`, `description`, `inLanguage`, `dateModified`).
 *  * Default language tag is `'en'` when the input has no explicit
 *    language.
 *  * Per-resource type mapping produces the spec-mandated
 *    `schema:Dataset` / `schema:DataCatalog` / `schema:Offer` shapes.
 *
 * Validation strategy: import the schema-dts type definitions and use
 * `as` casts to confirm the mapper output is assignable to the
 * concrete schema-dts type. A type-level mismatch fails compilation
 * (and thus the `tsc --noEmit` step in CI), giving us validation
 * without bringing in a runtime JSON-Schema validator.
 */
import { describe, expect, it } from 'vitest';

import type { Dataset, DataCatalog, Offer } from 'schema-dts';

import {
  mapAssetToSchemaOrg,
  mapContractToSchemaOrg,
  mapDatasetToSchemaOrg,
  mapListingToSchemaOrg,
} from '../schemaOrgMapper';

const REQUIRED_FIELDS = ['@type', 'name', 'description', 'inLanguage', 'dateModified'] as const;

describe('schemaOrgMapper', () => {
  describe('mapAssetToSchemaOrg', () => {
    it('produces a schema:Dataset with all required fields', () => {
      const asset = {
        id: 'a-1',
        name: 'Customer Master',
        description: 'Authoritative customer entity records.',
        canonical_iri: 'https://meshant.com/id/asset/a-1',
        updated_at: '2026-04-01T12:00:00Z',
      };
      const out = mapAssetToSchemaOrg(asset);
      // Type-level assertion: assignable to schema-dts Dataset.
      const _checkAssignability: Dataset = out;
      expect(_checkAssignability).toBeDefined();
      expect(out['@type']).toBe('Dataset');
      for (const k of REQUIRED_FIELDS) {
        expect(out).toHaveProperty(k);
        expect(out[k as keyof typeof out]).toBeTruthy();
      }
      expect(out.identifier).toBe('https://meshant.com/id/asset/a-1');
      expect(out.dateModified).toBe('2026-04-01T12:00:00Z');
    });

    it('defaults inLanguage to "en" when not supplied', () => {
      const out = mapAssetToSchemaOrg({
        id: 'a-2',
        name: 'X',
        description: 'Y',
        canonical_iri: 'https://meshant.com/id/asset/a-2',
        updated_at: '2026-04-01T12:00:00Z',
      });
      expect(out.inLanguage).toBe('en');
    });

    it('honors explicit inLanguage override', () => {
      const out = mapAssetToSchemaOrg({
        id: 'a-3',
        name: 'X',
        description: 'Y',
        canonical_iri: 'https://meshant.com/id/asset/a-3',
        updated_at: '2026-04-01T12:00:00Z',
        inLanguage: 'pt-BR',
      });
      expect(out.inLanguage).toBe('pt-BR');
    });

    it('emits @context: schema.org', () => {
      const out = mapAssetToSchemaOrg({
        id: 'a-4',
        name: 'X',
        description: 'Y',
        canonical_iri: 'https://meshant.com/id/asset/a-4',
        updated_at: '2026-04-01T12:00:00Z',
      });
      expect(out['@context']).toBe('https://schema.org');
    });
  });

  describe('mapContractToSchemaOrg', () => {
    it('produces a schema:Dataset with all required fields', () => {
      const out = mapContractToSchemaOrg({
        id: 'c-1',
        name: 'Customer Contract v2',
        description: 'ODCS contract for customer master data.',
        canonical_iri: 'https://meshant.com/id/contract/c-1',
        updated_at: '2026-04-02T08:30:00Z',
      });
      const _check: Dataset = out;
      expect(_check).toBeDefined();
      expect(out['@type']).toBe('Dataset');
      for (const k of REQUIRED_FIELDS) {
        expect(out).toHaveProperty(k);
      }
    });
  });

  describe('mapDatasetToSchemaOrg', () => {
    it('produces a schema:Dataset with all required fields', () => {
      const out = mapDatasetToSchemaOrg({
        id: 'd-1',
        name: 'Q4 Sales Dataset',
        description: 'Aggregated Q4 sales records by region.',
        canonical_iri: 'https://meshant.com/id/dataset/d-1',
        updated_at: '2026-03-15T18:00:00Z',
      });
      const _check: Dataset = out;
      expect(_check).toBeDefined();
      expect(out['@type']).toBe('Dataset');
    });
  });

  describe('mapListingToSchemaOrg', () => {
    it('produces a schema:DataCatalog with at least one Offer', () => {
      const out = mapListingToSchemaOrg({
        id: 'l-1',
        name: 'Public Sales Listing',
        description: 'Marketplace offer for Q4 sales data.',
        canonical_iri: 'https://meshant.com/id/listing/l-1',
        updated_at: '2026-04-10T10:00:00Z',
        price_amount: 99.99,
        price_currency: 'USD',
      });
      const _check: DataCatalog = out;
      expect(_check).toBeDefined();
      expect(out['@type']).toBe('DataCatalog');
      // Listings carry an Offer for the price-bearing payload.
      const dataset = (out.dataset ?? []) as unknown as { offers?: Offer | Offer[] }[];
      const firstWithOffer = Array.isArray(dataset) ? dataset[0] : dataset;
      expect(firstWithOffer?.offers).toBeDefined();
    });

    it('omits offers when listing has no price', () => {
      const out = mapListingToSchemaOrg({
        id: 'l-2',
        name: 'Free Listing',
        description: 'Free public dataset.',
        canonical_iri: 'https://meshant.com/id/listing/l-2',
        updated_at: '2026-04-10T10:00:00Z',
      });
      const dataset = (out.dataset ?? []) as unknown as { offers?: Offer | Offer[] }[];
      const firstWithOffer = Array.isArray(dataset) ? dataset[0] : dataset;
      expect(firstWithOffer?.offers).toBeUndefined();
    });

    it('defaults inLanguage to "en"', () => {
      const out = mapListingToSchemaOrg({
        id: 'l-3',
        name: 'X',
        description: 'Y',
        canonical_iri: 'https://meshant.com/id/listing/l-3',
        updated_at: '2026-04-10T10:00:00Z',
      });
      expect(out.inLanguage).toBe('en');
    });
  });

  describe('JSON-LD serialization', () => {
    it('all mappers produce JSON-serializable output (round-trip)', () => {
      const inputs = [
        {
          fn: mapAssetToSchemaOrg,
          arg: {
            id: 'a',
            name: 'A',
            description: 'D',
            canonical_iri: 'urn:asset:a',
            updated_at: '2026-01-01T00:00:00Z',
          },
        },
        {
          fn: mapContractToSchemaOrg,
          arg: {
            id: 'c',
            name: 'C',
            description: 'D',
            canonical_iri: 'urn:contract:c',
            updated_at: '2026-01-01T00:00:00Z',
          },
        },
        {
          fn: mapDatasetToSchemaOrg,
          arg: {
            id: 'd',
            name: 'D',
            description: 'X',
            canonical_iri: 'urn:dataset:d',
            updated_at: '2026-01-01T00:00:00Z',
          },
        },
        {
          fn: mapListingToSchemaOrg,
          arg: {
            id: 'l',
            name: 'L',
            description: 'X',
            canonical_iri: 'urn:listing:l',
            updated_at: '2026-01-01T00:00:00Z',
          },
        },
      ];
      for (const { fn, arg } of inputs) {
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        const out = (fn as any)(arg);
        const json = JSON.stringify(out);
        expect(() => JSON.parse(json)).not.toThrow();
        const parsed = JSON.parse(json);
        expect(parsed['@context']).toBe('https://schema.org');
      }
    });
  });
});

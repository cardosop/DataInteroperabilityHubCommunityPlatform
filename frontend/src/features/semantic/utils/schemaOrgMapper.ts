/**
 * Phase 230.9 (REQ-SEM-SEO-001) — Schema.org JSON-LD mappers.
 *
 * Each mapper takes a Meshant resource shape and produces a
 * Schema.org-typed object suitable for embedding in
 * `<script type="application/ld+json">`.
 *
 * Type validation is structural — output is annotated with the
 * `schema-dts` types so the TypeScript compiler enforces required
 * fields at build time. Schema.org's "required" set per type is
 * intentionally narrower than the spec's `REQUIRED_FIELDS` (we
 * always emit `inLanguage` + `dateModified` even when Schema.org
 * marks them optional, because Google Rich Results scores higher
 * with them present).
 *
 * Default `inLanguage` is `'en'` per spec scenario "Default language
 * tag" — a tenant that hasn't opted in to a non-default language
 * gets `'en'` rather than a bare missing field.
 */
import type { Dataset, DataCatalog, Offer, WithContext } from 'schema-dts';

const SCHEMA_ORG_CONTEXT = 'https://schema.org' as const;
const DEFAULT_LANGUAGE = 'en' as const;

interface BaseResource {
  id: string;
  name: string;
  description: string;
  canonical_iri: string;
  updated_at: string;
  /** Optional override; when omitted defaults to ``'en'``. */
  inLanguage?: string;
  /** Optional published-at — Schema.org `datePublished`. */
  created_at?: string;
  /** Optional keyword list — Schema.org `keywords` (comma-joined). */
  keywords?: string[];
}

export type AssetInput = BaseResource;
export type ContractInput = BaseResource;
export type DatasetInput = BaseResource;

export interface ListingInput extends BaseResource {
  /** Optional price (omit Offer when both fields absent). */
  price_amount?: number;
  price_currency?: string;
}

function resolveLanguage(language: string | undefined): string {
  return language && language.trim() ? language : DEFAULT_LANGUAGE;
}

function buildKeywords(keywords: readonly string[] | undefined): string | undefined {
  if (!keywords || keywords.length === 0) return undefined;
  return keywords.join(', ');
}

/**
 * Map a Meshant Asset to a Schema.org Dataset.
 *
 * Schema.org type chosen: ``Dataset`` (Schema.org's
 * "data asset" surface; same as Contract/Dataset for indexing
 * symmetry — Google understands all three the same way).
 */
export function mapAssetToSchemaOrg(asset: AssetInput): WithContext<Dataset> {
  return {
    '@context': SCHEMA_ORG_CONTEXT,
    '@type': 'Dataset',
    identifier: asset.canonical_iri,
    name: asset.name,
    description: asset.description,
    inLanguage: resolveLanguage(asset.inLanguage),
    dateModified: asset.updated_at,
    ...(asset.created_at ? { datePublished: asset.created_at } : {}),
    ...(buildKeywords(asset.keywords) ? { keywords: buildKeywords(asset.keywords) } : {}),
  };
}

/**
 * Map a Meshant Contract to a Schema.org Dataset.
 *
 * Contracts describe data shape + SLAs but Schema.org has no first-
 * class "DataContract" type. ``Dataset`` with the contract IRI as
 * `identifier` is the closest match and indexes the contract
 * page for SERP discovery.
 */
export function mapContractToSchemaOrg(contract: ContractInput): WithContext<Dataset> {
  return {
    '@context': SCHEMA_ORG_CONTEXT,
    '@type': 'Dataset',
    identifier: contract.canonical_iri,
    name: contract.name,
    description: contract.description,
    inLanguage: resolveLanguage(contract.inLanguage),
    dateModified: contract.updated_at,
    ...(contract.created_at ? { datePublished: contract.created_at } : {}),
    ...(buildKeywords(contract.keywords)
      ? { keywords: buildKeywords(contract.keywords) }
      : {}),
  };
}

/**
 * Map a Meshant Dataset to a Schema.org Dataset.
 */
export function mapDatasetToSchemaOrg(dataset: DatasetInput): WithContext<Dataset> {
  return {
    '@context': SCHEMA_ORG_CONTEXT,
    '@type': 'Dataset',
    identifier: dataset.canonical_iri,
    name: dataset.name,
    description: dataset.description,
    inLanguage: resolveLanguage(dataset.inLanguage),
    dateModified: dataset.updated_at,
    ...(dataset.created_at ? { datePublished: dataset.created_at } : {}),
    ...(buildKeywords(dataset.keywords)
      ? { keywords: buildKeywords(dataset.keywords) }
      : {}),
  };
}

/**
 * Map a marketplace Listing to a Schema.org DataCatalog (with an
 * embedded Offer when the listing carries a price).
 *
 * DataCatalog is the right shape for a "listing" — it represents a
 * collection of one or more datasets with a commercial offer.
 * Embedding the Offer (rather than referencing it) lets Google's
 * Rich Results show the price + currency directly in SERP cards.
 */
export function mapListingToSchemaOrg(listing: ListingInput): WithContext<DataCatalog> {
  const innerDataset: Dataset & { offers?: Offer } = {
    '@type': 'Dataset',
    identifier: listing.canonical_iri,
    name: listing.name,
    description: listing.description,
    inLanguage: resolveLanguage(listing.inLanguage),
    dateModified: listing.updated_at,
  };

  if (
    typeof listing.price_amount === 'number' &&
    typeof listing.price_currency === 'string' &&
    listing.price_currency.length > 0
  ) {
    innerDataset.offers = {
      '@type': 'Offer',
      price: String(listing.price_amount),
      priceCurrency: listing.price_currency,
      availability: 'https://schema.org/InStock',
    };
  }

  return {
    '@context': SCHEMA_ORG_CONTEXT,
    '@type': 'DataCatalog',
    identifier: listing.canonical_iri,
    name: listing.name,
    description: listing.description,
    inLanguage: resolveLanguage(listing.inLanguage),
    dateModified: listing.updated_at,
    ...(listing.created_at ? { datePublished: listing.created_at } : {}),
    ...(buildKeywords(listing.keywords)
      ? { keywords: buildKeywords(listing.keywords) }
      : {}),
    dataset: [innerDataset],
  };
}

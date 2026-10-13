/**
 * Pure SEO mapper for the public pricing surface (285.13.11.3).
 *
 * Lives outside PricingPage.tsx for two reasons: react-refresh forbids
 * non-component exports from component files, and the JSON-LD
 * computation must be unit-pinned without a DOM —
 * react-helmet-async 3 under React 19 + jsdom never lands `<script>`
 * children in document.head (the SchemaOrgJsonLd.test.tsx precedent),
 * so the CONTENT pin lives here while the real-browser script emission
 * is E2E-pinned (frontend/e2e/journeys/seo/schemaorg-public.spec.ts).
 */
import type { PublicPricingResponse } from '../../shared/types/billing';

export function buildStructuredData(
  data: PublicPricingResponse | null,
): Record<string, unknown> | null {
  if (!data?.base_plans?.length) return null;
  const starter = data.base_plans.find(p => p.plan.order >= 1) || data.base_plans[0];
  const paidPrices = data.base_plans
    .filter(p => p.plan.price_amount_cents > 0)
    .map(p => p.plan.price_amount_cents);
  const allPrices = data.base_plans.map(p => p.plan.price_amount_cents);
  return {
    '@context': 'https://schema.org',
    '@type': 'SoftwareApplication',
    name: 'Meshant',
    applicationCategory: 'DataInteroperabilityPlatform',
    operatingSystem: 'Web',
    offers: {
      '@type': 'AggregateOffer',
      priceCurrency: starter.plan.price_currency,
      lowPrice: paidPrices.length
        ? (Math.min(...paidPrices) / 100).toString()
        : '0',
      highPrice: allPrices.length
        ? (Math.max(...allPrices) / 100).toString()
        : '0',
    },
  };
}

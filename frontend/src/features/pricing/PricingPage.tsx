/**
 * 285.13.11.2 — Public Pricing Page.
 *
 * States: loading, empty, error, logged-in, logged-out.
 * Behaviors: annual/monthly toggle, mobile responsive.
 * SEO: structured data, meta tags (285.13.11.3).
 * a11y: keyboard-nav cards, screen-reader prices (285.13.11.8).
 */
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Helmet } from 'react-helmet-async';
import { useAuthStore } from '../auth/store/authStore';
import { PricingCard } from './PricingCard';
import { PricingComparison } from './PricingComparison';
import { fetchPublicPricing } from './pricingService';
import type { PublicPricingResponse } from '../../shared/types/billing';

type PageState = 'loading' | 'loaded' | 'error' | 'empty';

export const PricingPage: React.FC = () => {
  const [state, setState] = useState<PageState>('loading');
  const [data, setData] = useState<PublicPricingResponse | null>(null);
  const [errorMessage, setErrorMessage] = useState('');
  const [isAnnual, setIsAnnual] = useState(false);
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        setState('loading');
        const result = await fetchPublicPricing();
        if (cancelled) return;
        const empty = (!result.base_plans || result.base_plans.length === 0)
          && (!result.ml_plans || result.ml_plans.length === 0);
        setData(result);
        setState(empty ? 'empty' : 'loaded');
      } catch (err) {
        if (cancelled) return;
        setErrorMessage(err instanceof Error ? err.message : 'Failed to load pricing');
        setState('error');
      }
    }
    load();
    return () => { cancelled = true; };
  }, []);

  const handleSelect = useCallback((slug: string) => {
    window.location.href = `/register?plan=${slug}`;
  }, []);

  const allPlans = useMemo(() => {
    if (!data) return [];
    return [...(data.base_plans || []), ...(data.ml_plans || [])];
  }, [data]);

  const structuredData = useMemo(() => {
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
  }, [data]);

  return (
    <main className="pricing-page" id="pricing-page">
      <Helmet>
        <title>Pricing — Meshant</title>
        <meta name="description" content="Meshant pricing plans — from free to enterprise. Compare features and find the right plan for your data interoperability needs." />
        <link rel="canonical" href="https://meshant.com/pricing" />
        {structuredData && (
          <script type="application/ld+json">
            {JSON.stringify(structuredData)}
          </script>
        )}
      </Helmet>

      <header className="pricing-page__header">
        <h1>Plans & Pricing</h1>
        <p>Choose the plan that fits your data interoperability needs.</p>
        <div className="pricing-page__toggle" role="radiogroup" aria-label="Billing period">
          <button
            role="radio"
            aria-checked={!isAnnual}
            className={!isAnnual ? 'active' : ''}
            onClick={() => setIsAnnual(false)}
          >
            Monthly
          </button>
          <button
            role="radio"
            aria-checked={isAnnual}
            className={isAnnual ? 'active' : ''}
            onClick={() => setIsAnnual(true)}
          >
            Annual <small>(save 15%)</small>
          </button>
        </div>
      </header>

      {state === 'loading' && (
        <div className="pricing-page__state" role="status" aria-live="polite">
          Loading plans…
        </div>
      )}

      {state === 'error' && (
        <div className="pricing-page__state pricing-page__state--error" role="alert">
          <p>{errorMessage}</p>
          <button onClick={() => window.location.reload()}>Retry</button>
        </div>
      )}

      {state === 'empty' && (
        <div className="pricing-page__state" role="status">
          No plans available at this time. Please check back later.
        </div>
      )}

      {state === 'loaded' && data && (
        <>
          {/* BASE plans */}
          {data.base_plans.length > 0 && (
            <section className="pricing-page__section" aria-labelledby="base-plans-heading">
              <h2 id="base-plans-heading">Platform Plans</h2>
              <div className="pricing-cards">
                {data.base_plans.map((pw) => (
                  <PricingCard
                    key={pw.plan.slug}
                    plan={pw.plan}
                    tierProfile={pw.tier_profile}
                    isAnnual={isAnnual}
                    isMostPopular={pw.tier_profile?.is_recommended ?? false}
                    isLoggedIn={isAuthenticated}
                    onSelect={handleSelect}
                  />
                ))}
              </div>
            </section>
          )}

          {/* ML add-on plans */}
          {data.ml_plans.length > 0 && (
            <section className="pricing-page__section" aria-labelledby="ml-plans-heading">
              <h2 id="ml-plans-heading">ML / AI Add-ons</h2>
              <p className="pricing-page__note">
                Requires an active BASE plan at Starter tier or above.
              </p>
              <div className="pricing-cards">
                {data.ml_plans.map((pw) => (
                  <PricingCard
                    key={pw.plan.slug}
                    plan={pw.plan}
                    tierProfile={pw.tier_profile}
                    isAnnual={isAnnual}
                    isMostPopular={false}
                    isLoggedIn={isAuthenticated}
                    onSelect={handleSelect}
                  />
                ))}
              </div>
            </section>
          )}

          {/* Feature comparison */}
          <section className="pricing-page__section" aria-labelledby="comparison-heading">
            <h2 id="comparison-heading">Feature Comparison</h2>
            <PricingComparison
              plans={allPlans.map((pw) => pw.plan)}
              tierProfiles={new Map(
                allPlans.map((pw) => [pw.plan.slug, pw.tier_profile]),
              )}
            />
          </section>
        </>
      )}
    </main>
  );
};

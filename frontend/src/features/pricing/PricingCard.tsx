/**
 * 285.13.11.2 — PricingCard component.
 *
 * Displays a single plan card with price, features, tier profile,
 * and "Most Popular" badge. Handles annual/monthly price toggle.
 */
import React from 'react';
import type { PlanPricing, TierProfile } from '../../shared/types/billing';

export interface PricingCardProps {
  plan: PlanPricing;
  tierProfile: TierProfile | null;
  isAnnual: boolean;
  isMostPopular: boolean;
  isLoggedIn: boolean;
  onSelect?: (slug: string) => void;
}

function formatPrice(cents: number, currency = 'USD', locale = 'en-US'): string {
  const usd = cents / 100;
  return new Intl.NumberFormat(locale, {
    style: 'currency',
    currency,
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(usd);
}

function formatPriceSR(cents: number, currency = 'USD', locale = 'en-US'): string {
  const usd = cents / 100;
  return new Intl.NumberFormat(locale, {
    style: 'currency',
    currency,
    currencyDisplay: 'name',
  }).format(usd);
}

function computeAnnual(cents: number): number {
  return Math.round(cents * 12 * 0.85);
}

export const PricingCard: React.FC<PricingCardProps> = ({
  plan,
  tierProfile,
  isAnnual,
  isMostPopular,
  isLoggedIn,
  onSelect,
}) => {
  const price = isAnnual ? computeAnnual(plan.price_amount_cents) : plan.price_amount_cents;
  const period = isAnnual ? '/yr' : '/mo';
  const srPrice = formatPriceSR(price, plan.price_currency);

  return (
    <article
      className={`pricing-card ${isMostPopular ? 'pricing-card--popular' : ''}`}
      role="region"
      aria-label={`${plan.name} plan — ${srPrice} per ${isAnnual ? 'year' : 'month'}`}
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === 'Enter' && onSelect) onSelect(plan.slug);
      }}
    >
      {isMostPopular && (
        <span className="pricing-card__badge" aria-label="Most popular plan">
          Most Popular
        </span>
      )}

      <h3 className="pricing-card__tier">{plan.tier}</h3>
      {tierProfile?.headline && (
        <p className="pricing-card__headline">{tierProfile.headline}</p>
      )}

      <div className="pricing-card__price" aria-hidden="true">
        <span className="pricing-card__price-value">{formatPrice(price)}</span>
        <span className="pricing-card__price-period">{period}</span>
      </div>
      <span className="sr-only">{srPrice} per {isAnnual ? 'year' : 'month'}</span>

      <ul className="pricing-card__features" role="list">
        {plan.limits_json && Object.entries(plan.limits_json).map(([key, limit]) => (
          <li key={key} className="pricing-card__feature">
            {limit === null ? `Unlimited ${key.replace('max_', '')}` : `${limit?.toLocaleString()} ${key.replace('max_', '')}`}
          </li>
        ))}
      </ul>

      {tierProfile?.features_highlight && (
        <p className="pricing-card__highlights">{tierProfile.features_highlight}</p>
      )}

      {isLoggedIn && tierProfile?.self_serve && onSelect && (
        <button
          className="pricing-card__cta"
          onClick={() => onSelect(plan.slug)}
          aria-label={`Select ${plan.name} plan`}
        >
          {plan.price_amount_cents === 0 ? 'Current Plan' : 'Upgrade'}
        </button>
      )}
    </article>
  );
};

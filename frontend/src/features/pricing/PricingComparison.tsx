/**
 * 285.13.11.2 — Feature comparison table for pricing page.
 *
 * Renders a responsive matrix of features × plans using TierProfile
 * checkmark data. Keyboard-navigable with role="grid".
 */
import React from 'react';
import type { PlanPricing, TierProfile } from '../../shared/types/billing';

export interface PricingComparisonProps {
  plans: PlanPricing[];
  tierProfiles: Map<string, TierProfile | null>;
}

export const PricingComparison: React.FC<PricingComparisonProps> = ({
  plans,
  tierProfiles,
}) => {
  // Collect all unique feature keys across plans
  const allFeatures = new Set<string>();
  for (const tp of tierProfiles.values()) {
    if (tp?.feature_checkmarks) {
      for (const key of Object.keys(tp.feature_checkmarks)) {
        allFeatures.add(key);
      }
    }
  }
  const features = Array.from(allFeatures);

  if (features.length === 0) return null;

  return (
    <div className="pricing-comparison" role="grid" aria-label="Feature comparison">
      <div className="pricing-comparison__header" role="row">
        <div className="pricing-comparison__label" role="columnheader" />
        {plans.map((p) => (
          <div key={p.slug} className="pricing-comparison__plan" role="columnheader">
            {p.name}
          </div>
        ))}
      </div>
      {features.map((feature) => (
        <div key={feature} className="pricing-comparison__row" role="row">
          <div className="pricing-comparison__label" role="rowheader">
            {feature.replace(/_/g, ' ')}
          </div>
          {plans.map((p) => {
            const tp = tierProfiles.get(p.slug);
            const hasFeature = tp?.feature_checkmarks?.[feature] ?? false;
            return (
              <div
                key={`${p.slug}-${feature}`}
                className="pricing-comparison__cell"
                role="cell"
                aria-label={`${p.name}: ${hasFeature ? 'included' : 'not included'}`}
              >
                {hasFeature ? (
                  <span aria-hidden="true" className="pricing-comparison__check">✓</span>
                ) : (
                  <span aria-hidden="true" className="pricing-comparison__cross">—</span>
                )}
              </div>
            );
          })}
        </div>
      ))}
    </div>
  );
};

/**
 * 285.13.11.4 — Plan Settings Page (dual-panel BASE + ML).
 *
 * States: loading, upgrade-in-progress, payment-failed, downgrade-blocked, success.
 */
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { apiClient } from '../../shared/api/client';
import { usePlanUsage } from './usePlanUsage';
import { usePlanUpgrade } from './usePlanUpgrade';
import { PlanUpgradeDialog } from './PlanUpgradeDialog';
import { PlanDowngradeWarning } from './PlanDowngradeWarning';
import type { PlanPricing, PlanWithProfile, UsageLimit } from '../../shared/types/billing';

const BASE = '/api/v1';

export const PlanSettingsPage: React.FC = () => {
  const [currentPlan, setCurrentPlan] = useState<PlanPricing | null>(null);
  const [availableUpgrades, setAvailableUpgrades] = useState<PlanWithProfile[]>([]);
  const [mlAddons, setMlAddons] = useState<PlanWithProfile[]>([]);
  const [loadingPlans, setLoadingPlans] = useState(true);
  const [dialogTarget, setDialogTarget] = useState<PlanPricing | null>(null);
  const [showDowngrade, setShowDowngrade] = useState<PlanPricing | null>(null);

  const { usage, loading: usageLoading } = usePlanUsage();
  const { loading: changingPlan, error, success, upgrade, downgrade, reset } = usePlanUpgrade();

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const [planResp, upgradeResp, mlResp] = await Promise.all([
          apiClient.getClient().get<{ plan: PlanPricing; tier_profile: unknown }>(`${BASE}/tenants/me/plan/`),
          apiClient.getClient().get<PlanWithProfile[]>(`${BASE}/tenants/me/plan/available-upgrades/`),
          apiClient.getClient().get<PlanWithProfile[]>(`${BASE}/tenants/me/plan/available-ml-addons/`).catch(() => ({ data: [] as PlanWithProfile[] })),
        ]);
        if (cancelled) return;
        setCurrentPlan(planResp.data.plan);
        setAvailableUpgrades(upgradeResp.data || []);
        setMlAddons(mlResp.data || []);
      } catch {
        // current plan endpoint returns error when no plan is assigned
      } finally {
        if (!cancelled) setLoadingPlans(false);
      }
    }
    load();
    return () => { cancelled = true; };
  }, []);

  // Compute exceeded limits for the current downgrade target (not dialogTarget).
  const exceededLimits = useMemo(() => {
    if (!usage || !showDowngrade) return [];
    const targetLimits = showDowngrade.limits_json || {};
    return usage.limits
      .filter((l: UsageLimit) => {
        const limit = targetLimits[l.limit_key]
          ?? targetLimits[`max_${l.limit_key}`];
        return limit !== null && limit !== undefined && l.usage > Number(limit);
      })
      .map((l: UsageLimit) => l.limit_key);
  }, [usage, showDowngrade]);

  const handleUpgradeConfirm = useCallback(async () => {
    if (!dialogTarget) return;
    await upgrade(dialogTarget.slug);
  }, [dialogTarget, upgrade]);

  const handleDowngradeConfirm = useCallback(async () => {
    if (!showDowngrade) return;
    await downgrade(showDowngrade.slug);
  }, [showDowngrade, downgrade]);

  if (loadingPlans || usageLoading) {
    return <div className="plan-settings" role="status">Loading plan details…</div>;
  }

  return (
    <div className="plan-settings">
      <h1>Plan Settings</h1>

      {success && (
        <div className="banner banner--success" role="status">
          Plan changed successfully.
        </div>
      )}
      {error && (
        <div className="banner banner--error" role="alert">
          {error}
          {error.includes('circuit breaker') && (
            <p className="banner__hint">
              The payment service is temporarily unavailable. Your request is safe
              to retry in a few minutes.
            </p>
          )}
        </div>
      )}

      {/* BASE plan panel */}
      <section className="plan-settings__panel" aria-labelledby="base-plan-heading">
        <h2 id="base-plan-heading">Current BASE Plan</h2>
        {currentPlan ? (
          <>
            <p><strong>{currentPlan.name}</strong> ({currentPlan.tier})</p>
            <p>${(currentPlan.price_amount_cents / 100).toFixed(2)}/{currentPlan.billing_interval}</p>
            {usage && (
              <div
                className="usage-bar"
                role="progressbar"
                aria-valuenow={usage.overall_status === 'exceeded' ? 100
                  : usage.overall_status === 'critical' ? 95
                  : usage.overall_status === 'warning' ? 85 : 50}
                aria-valuemin={0}
                aria-valuemax={100}
                aria-label={`Usage status: ${usage.overall_status}`}
              >
                <div className={`usage-bar__fill usage-bar__fill--${usage.overall_status}`} />
              </div>
            )}
          </>
        ) : (
          <p>No active BASE subscription.</p>
        )}

        {availableUpgrades.length > 0 && (
          <div className="plan-settings__upgrades">
            <h3>Available Upgrades</h3>
            {availableUpgrades.map((pw) => (
              <button
                key={pw.plan.slug}
                className="btn--primary"
                onClick={() => { reset(); setDialogTarget(pw.plan); }}
              >
                Upgrade to {pw.plan.name}
              </button>
            ))}
          </div>
        )}
      </section>

      {/* ML add-ons panel */}
      <section className="plan-settings__panel" aria-labelledby="ml-plan-heading">
        <h2 id="ml-plan-heading">ML / AI Add-ons</h2>
        {mlAddons.length > 0 ? (
          mlAddons.map((pw) => (
            <button
              key={pw.plan.slug}
              className="btn--primary"
              onClick={() => { reset(); setDialogTarget(pw.plan); }}
            >
              Add {pw.plan.name} — ${(pw.plan.price_amount_cents / 100).toFixed(2)}/mo
            </button>
          ))
        ) : (
          <p>
            No ML add-ons available. Requires a BASE subscription at Starter tier
            (order &ge; 1) or above.
          </p>
        )}
      </section>

      {dialogTarget && currentPlan && (
        <PlanUpgradeDialog
          open
          currentPlan={currentPlan}
          targetPlan={dialogTarget}
          loading={changingPlan}
          error={error}
          onConfirm={handleUpgradeConfirm}
          onCancel={() => { setDialogTarget(null); reset(); }}
        />
      )}

      {showDowngrade && currentPlan && (
        <PlanDowngradeWarning
          currentPlan={currentPlan}
          targetPlan={showDowngrade}
          exceededLimits={exceededLimits}
          onConfirm={handleDowngradeConfirm}
          onCancel={() => { setShowDowngrade(null); reset(); }}
        />
      )}
    </div>
  );
};

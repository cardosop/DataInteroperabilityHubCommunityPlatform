/**
 * Query Cost Meter — Phase 275.D
 * Visual indicator of warehouse query cost consumption per tenant.
 */
import React from 'react';

interface Props { costUnits: number; unitLabel: string; budget: number }

export function QueryCostMeter({ costUnits, unitLabel, budget }: Props): React.ReactElement {
  const pct = budget > 0 ? Math.min(100, (costUnits / budget) * 100) : 0;
  const warn = pct > 80;
  const critical = pct > 95;

  return (
    <div className={`cost-meter ${critical ? 'critical' : warn ? 'warn' : ''}`}>
      <div className="bar"><div className="fill" style={{ width: `${pct}%` }} /></div>
      <span className="label">
        {costUnits.toFixed(2)} / {budget} {unitLabel} ({pct.toFixed(0)}%)
      </span>
    </div>
  );
}

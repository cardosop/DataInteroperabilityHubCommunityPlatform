/**
 * Pure helpers for compliance trend chart (Phase 231.7).
 * Split from the component module for react-refresh/only-export-components.
 */

import type { ComplianceRun } from '../../../shared/types/compliance';

import { complianceRiskOrdinal } from '../utils/riskLevelOrdinal';

export const COMPLIANCE_TREND_MAX_RUNS = 50;

/** Prepare chronological points (oldest → newest) for the line chart. */
export function buildComplianceTrendPoints(runs: ComplianceRun[]): Array<{
  id: string;
  completedAt: string;
  ordinal: number;
  riskLabel: string;
}> {
  const withTimes = runs
    .filter((r) => r.completed_at)
    .map((r) => ({
      id: r.id,
      completedAt: r.completed_at as string,
      ordinal: complianceRiskOrdinal(r.risk_level),
      riskLabel: r.risk_level ?? 'UNKNOWN',
    }))
    .sort((a, b) => new Date(a.completedAt).getTime() - new Date(b.completedAt).getTime());
  return withTimes;
}

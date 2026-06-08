/**
 * Ordinal scale for compliance risk (Phase 231.7 trend chart).
 * Aligns with hub.apps.compliance.models.RiskLevel.risk_ordinal for standard levels.
 */

import type { RiskLevel } from '../../../shared/types/compliance';

const ORDINAL: Record<string, number> = {
  NONE: 0,
  LOW: 1,
  MEDIUM: 2,
  HIGH: 3,
  CRITICAL: 4,
  UNKNOWN: 2,
};

/**
 * Map API risk_level string to Y-axis value in [0, 4]. Malformed / missing → UNKNOWN slot (2).
 */
export function complianceRiskOrdinal(level: RiskLevel | string | null | undefined): number {
  if (level == null || level === '') {
    return ORDINAL.UNKNOWN;
  }
  const key = String(level).trim().toUpperCase();
  return key in ORDINAL ? ORDINAL[key]! : ORDINAL.UNKNOWN;
}

export const COMPLIANCE_RISK_ORDINAL_MAX = 4;

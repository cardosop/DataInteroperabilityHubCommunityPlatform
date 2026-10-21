/**
 * Phase 231.7 — trend chart uses synthetic runs (in-memory); no HTTP mocks.
 */
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import type { ComplianceRun } from '../../../../shared/types/compliance';
import { ComplianceTrendChart } from '../ComplianceTrendChart';
import { buildComplianceTrendPoints } from '../../utils/complianceTrendChartModel';

function syntheticRuns(): ComplianceRun[] {
  const base = '2026-03-01T12:00:00Z';
  const levels = ['NONE', 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL'] as const;
  return levels.map((risk_level, i) => ({
    id: `00000000-0000-0000-0000-00000000000${i}`,
    tenant: 'tenant-1',
    job: `job-${i}`,
    status: 'SUCCEEDED',
    risk_level,
    completed_at: new Date(new Date(base).getTime() + i * 3600_000).toISOString(),
    created_at: base,
    updated_at: base,
  }));
}

describe('ComplianceTrendChart', () => {
  it('buildComplianceTrendPoints sorts by completed_at ascending', () => {
    const runs = syntheticRuns().reverse();
    const pts = buildComplianceTrendPoints(runs);
    expect(pts).toHaveLength(5);
    for (let i = 1; i < pts.length; i++) {
      expect(new Date(pts[i].completedAt).getTime()).toBeGreaterThanOrEqual(
        new Date(pts[i - 1].completedAt).getTime(),
      );
    }
    expect(pts.map((p) => p.ordinal)).toEqual([0, 1, 2, 3, 4]);
  });

  it('renders empty state when no completed_at runs', () => {
    render(<ComplianceTrendChart runs={[]} />);
    expect(screen.getByTestId('compliance-trend-chart-empty')).toBeInTheDocument();
    expect(screen.getByRole('status')).toHaveTextContent(/no succeeded compliance runs/i);
  });

  it('renders line chart img role for synthetic succeeded runs', () => {
    render(<ComplianceTrendChart runs={syntheticRuns()} />);
    expect(screen.getByTestId('compliance-trend-chart')).toBeInTheDocument();
    expect(screen.getByRole('img', { name: /line chart of risk level/i })).toBeInTheDocument();
  });
});

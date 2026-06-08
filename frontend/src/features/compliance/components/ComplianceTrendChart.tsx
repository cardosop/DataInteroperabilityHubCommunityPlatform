/**
 * Phase 231.7 — per-asset compliance risk trend (last N succeeded runs).
 * SVG line chart; no extra charting dependencies.
 */

import type { ComplianceRun } from '../../../shared/types/compliance';
import { COMPLIANCE_RISK_ORDINAL_MAX } from '../utils/riskLevelOrdinal';
import { buildComplianceTrendPoints } from '../utils/complianceTrendChartModel';
import styles from './ComplianceTrendChart.module.css';

export interface ComplianceTrendChartProps {
  /** Succeeded runs; caller should cap at 50 and pass API order any — points are sorted by ``completed_at``. */
  runs: ComplianceRun[];
}

function formatShortDate(iso: string): string {
  try {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return iso.slice(0, 10);
    return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
  } catch {
    return iso.slice(0, 10);
  }
}

export function ComplianceTrendChart({ runs }: ComplianceTrendChartProps) {
  const points = buildComplianceTrendPoints(runs);
  const label =
    points.length === 0
      ? 'No succeeded compliance runs yet for this asset.'
      : `Line chart of risk level over ${points.length} succeeded run${points.length === 1 ? '' : 's'}, oldest to newest.`;

  if (points.length === 0) {
    return (
      <div className={styles.wrap} data-testid="compliance-trend-chart-empty">
        <h2 className={styles.title}>Compliance trend</h2>
        <p className={styles.empty} role="status">
          No succeeded compliance runs yet.
        </p>
      </div>
    );
  }

  const w = 400;
  const h = 160;
  const padL = 8;
  const padR = 8;
  const padT = 12;
  const padB = 8;
  const innerW = w - padL - padR;
  const innerH = h - padT - padB;
  const n = points.length;
  const minY = 0;
  const maxY = COMPLIANCE_RISK_ORDINAL_MAX;

  const coords = points.map((pt, i) => {
    const x = n === 1 ? padL + innerW / 2 : padL + (innerW * i) / (n - 1);
    const yn = (pt.ordinal - minY) / (maxY - minY || 1);
    const y = padT + innerH - yn * innerH;
    return { x, y, ...pt };
  });

  const d = coords.map((c, i) => `${i === 0 ? 'M' : 'L'} ${c.x.toFixed(1)} ${c.y.toFixed(1)}`).join(' ');

  const yPositions = [4, 3, 2, 1, 0].map((ord) => {
    const yn = (ord - minY) / (maxY - minY || 1);
    const y = padT + innerH - yn * innerH;
    return { ord, y };
  });

  return (
    <div className={styles.wrap} data-testid="compliance-trend-chart">
      <h2 className={styles.title}>Compliance trend</h2>
      <p className={styles.meta}>
        Last {points.length} succeeded runs (risk: None=0 … Critical=4)
      </p>
      <svg
        className={styles.chartSvg}
        viewBox={`0 0 ${w} ${h}`}
        role="img"
        aria-label={label}
      >
        <title>{label}</title>
        {/* horizontal grid */}
        {yPositions.map(({ ord, y }) => (
          <line
            key={`grid-${ord}`}
            x1={padL}
            x2={w - padR}
            y1={y}
            y2={y}
            stroke="var(--color-border-subtle, #e2e8f0)"
            strokeWidth={0.5}
          />
        ))}
        <path
          d={d}
          fill="none"
          stroke="var(--color-accent-primary, #2563eb)"
          strokeWidth={2}
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        {coords.map((c) => (
          <circle
            key={c.id}
            cx={c.x}
            cy={c.y}
            r={4}
            fill="var(--color-accent-primary, #2563eb)"
            aria-label={`${c.riskLabel} at ${formatShortDate(c.completedAt)}`}
          />
        ))}
      </svg>
      <div className={styles.axisLabels} aria-hidden="true">
        <span>{formatShortDate(points[0].completedAt)}</span>
        <span>{formatShortDate(points[points.length - 1].completedAt)}</span>
      </div>
    </div>
  );
}

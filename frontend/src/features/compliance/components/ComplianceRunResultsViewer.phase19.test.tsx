/**
 * Thin integration smoke: Phase 231.5 blocks mount with coherent /results-shaped props.
 */

import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import type { ComplianceRunResults } from '../../../shared/types/compliance';
import { ComplianceRunResultsViewer } from './ComplianceRunResultsViewer';

function minimalResults(overrides: Partial<ComplianceRunResults> = {}): ComplianceRunResults {
  return {
    compliance_run_id: '00000000-0000-0000-0000-000000000001',
    overall_status: 'PASS',
    risk_level: 'LOW',
    allowed_to_store: true,
    compliance_score: 100,
    score_breakdown: {
      total_columns: 1,
      columns_with_pii: 0,
      columns_without_pii: 1,
      pii_detection_rate: 0,
      base_score: 100,
      pii_penalty: 0,
      final_score: 100,
    },
    violations: [],
    violation_details: [],
    remediation_suggestions: [],
    risk_assessment: {
      overall_risk_level: 'LOW',
      risk_score: 0,
      allowed_to_store: true,
      total_violations: 0,
      high_severity_violations: 0,
      medium_severity_violations: 0,
      low_severity_violations: 0,
      regulations_checked: [],
      recommendations: [],
    },
    violation_timeline: [],
    regulations: [],
    column_findings: [],
    ...overrides,
  };
}

describe('ComplianceRunResultsViewer — Phase 19', () => {
  it('renders regulatory posture and cross-border triggered state when applicable', () => {
    render(
      <ComplianceRunResultsViewer
        results={minimalResults({
          cross_border_alert: { applicable: true, regulations: ['GDPR'], requires_safeguards: true },
          localisation_alert: { applicable: false },
          regulation_summaries: [{ regulation: 'GDPR', status: 'WARN', violations: 1 }],
          legal_basis_violations: [
            { regulation: 'HIPAA', basis: 'CONTRACT', violation: 'review_retention' },
          ],
        })}
      />
    );
    expect(screen.getByRole('heading', { name: /Regulatory posture \(v2\)/i })).toBeInTheDocument();
    const cross = screen.getByTestId('cross-border-alert-card');
    expect(cross).toHaveClass('phase19-alert-triggered');
    expect(screen.getByTestId('regulation-summary-table')).toBeInTheDocument();
    expect(screen.getByTestId('legal-basis-violations-list')).toBeInTheDocument();
  });

  it('defaults null alerts to clear-state cards via viewer fallbacks', () => {
    render(<ComplianceRunResultsViewer results={minimalResults()} />);
    expect(screen.getByTestId('cross-border-alert-card')).toHaveClass('phase19-alert-clear');
  });
});

/**
 * Compliance Run Results Viewer
 * Displays detailed compliance results with filtering and severity grouping
 */

import { useState, useMemo } from 'react';
import type { ComplianceRunResults } from '../../../shared/types/compliance';
import './ComplianceRunResultsViewer.css';

interface ComplianceRunResultsViewerProps {
  results: ComplianceRunResults;
}

export function ComplianceRunResultsViewer({ results }: ComplianceRunResultsViewerProps) {
  const [severityFilter, setSeverityFilter] = useState<'ALL' | 'HIGH' | 'MEDIUM' | 'LOW'>('ALL');
  const [regulationFilter, setRegulationFilter] = useState<string>('ALL');

  // Get unique regulations
  const regulations = useMemo(() => {
    const regs = new Set<string>();
    results.violations.forEach((violation) => {
      const detail = results.violation_details.find(
        (vd) => vd.column === violation.column && vd.pii_type === violation.pii_type
      );
      if (detail?.regulations_affected) {
        detail.regulations_affected.forEach((r) => regs.add(r));
      }
    });
    return Array.from(regs).sort();
  }, [results.violations, results.violation_details]);

  // Filter violations
  const filteredViolations = useMemo(() => {
    return results.violations.filter((violation) => {
      if (severityFilter !== 'ALL' && violation.severity !== severityFilter) return false;
      if (regulationFilter !== 'ALL') {
        const detail = results.violation_details.find(
          (vd) => vd.column === violation.column && vd.pii_type === violation.pii_type
        );
        if (!detail?.regulations_affected?.includes(regulationFilter)) return false;
      }
      return true;
    });
  }, [results.violations, results.violation_details, severityFilter, regulationFilter]);

  // Group violations by severity
  const violationsBySeverity = useMemo(() => {
    const grouped: Record<string, typeof filteredViolations> = {
      HIGH: [],
      MEDIUM: [],
      LOW: [],
    };
    filteredViolations.forEach((violation) => {
      grouped[violation.severity].push(violation);
    });
    return grouped;
  }, [filteredViolations]);

  return (
    <div className="compliance-results-viewer">
      {/* Summary Section */}
      <div className="compliance-results-summary">
        <div className="summary-card">
          <div className="summary-label">Overall Status</div>
          <div
            className={`summary-value overall-status-${results.overall_status?.toLowerCase() || 'unknown'}`}
          >
            {results.overall_status || 'UNKNOWN'}
          </div>
        </div>
        <div className="summary-card">
          <div className="summary-label">Risk Level</div>
          <div className={`summary-value risk-level-${results.risk_level?.toLowerCase() || 'unknown'}`}>
            {results.risk_level || 'UNKNOWN'}
          </div>
        </div>
        <div className="summary-card">
          <div className="summary-label">Allowed to Store</div>
          <div className={`summary-value ${results.allowed_to_store ? 'allowed' : 'blocked'}`}>
            {results.allowed_to_store ? 'Yes' : 'No'}
          </div>
        </div>
        <div className="summary-card">
          <div className="summary-label">Compliance Score</div>
          <div className="summary-value compliance-score">
            {results.compliance_score !== null && results.compliance_score !== undefined
              ? Math.round(results.compliance_score)
              : 0}
            %
          </div>
        </div>
        <div className="summary-card">
          <div className="summary-label">Total Violations</div>
          <div className="summary-value">{results.risk_assessment.total_violations}</div>
        </div>
        <div className="summary-card">
          <div className="summary-label">High Severity</div>
          <div className="summary-value high-severity">{results.risk_assessment.high_severity_violations}</div>
        </div>
      </div>

      {/* Fail-Closed Warning */}
      {!results.allowed_to_store && (
        <div className="fail-closed-warning">
          <h3>⚠️ Fail-Closed: Storage Blocked</h3>
          <p>
            This data cannot be stored due to compliance violations. Please review the violations
            below and remediate issues before retrying the compliance check.
          </p>
          <div className="fail-closed-actions">
            <strong>Next Steps:</strong>
            <ul>
              <li>Review all violations, especially high-severity ones</li>
              <li>Follow remediation suggestions for each violation</li>
              <li>Fix data issues (masking, redaction, removal of PII)</li>
              <li>Retry the compliance check after remediation</li>
            </ul>
          </div>
        </div>
      )}

      {/* Filters */}
      <div className="compliance-results-filters">
        <div className="filter-group">
          <label>Severity</label>
          <select value={severityFilter} onChange={(e) => setSeverityFilter(e.target.value as 'ALL' | 'HIGH' | 'MEDIUM' | 'LOW')}>
            <option value="ALL">All Severities</option>
            <option value="HIGH">High</option>
            <option value="MEDIUM">Medium</option>
            <option value="LOW">Low</option>
          </select>
        </div>
        <div className="filter-group">
          <label>Regulation</label>
          <select value={regulationFilter} onChange={(e) => setRegulationFilter(e.target.value)}>
            <option value="ALL">All Regulations</option>
            {regulations.map((reg) => (
              <option key={reg} value={reg}>
                {reg}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Score Breakdown */}
      <div className="compliance-results-score-breakdown">
        <h3>Score Breakdown</h3>
        <div className="score-breakdown-details">
          <div className="breakdown-item">
            <span className="breakdown-label">Total Columns:</span>
            <span className="breakdown-value">{results.score_breakdown.total_columns}</span>
          </div>
          <div className="breakdown-item">
            <span className="breakdown-label">Columns with PII:</span>
            <span className="breakdown-value warning">{results.score_breakdown.columns_with_pii}</span>
          </div>
          <div className="breakdown-item">
            <span className="breakdown-label">Columns without PII:</span>
            <span className="breakdown-value passed">{results.score_breakdown.columns_without_pii}</span>
          </div>
          <div className="breakdown-item">
            <span className="breakdown-label">PII Detection Rate:</span>
            <span className="breakdown-value">
              {Math.round(results.score_breakdown.pii_detection_rate * 100)}%
            </span>
          </div>
          <div className="breakdown-item">
            <span className="breakdown-label">PII Penalty:</span>
            <span className="breakdown-value failed">-{Math.round(results.score_breakdown.pii_penalty)}</span>
          </div>
          <div className="breakdown-item">
            <span className="breakdown-label">Final Score:</span>
            <span className="breakdown-value final-score">{Math.round(results.score_breakdown.final_score)}%</span>
          </div>
        </div>
      </div>

      {/* Risk Assessment */}
      <div className="compliance-results-risk-assessment">
        <h3>Risk Assessment</h3>
        <div className="risk-assessment-details">
          <div className="risk-item">
            <span className="risk-label">Overall Risk Level:</span>
            <span className={`risk-value risk-level-${results.risk_assessment.overall_risk_level.toLowerCase()}`}>
              {results.risk_assessment.overall_risk_level}
            </span>
          </div>
          <div className="risk-item">
            <span className="risk-label">Risk Score:</span>
            <span className="risk-value">{Math.round(results.risk_assessment.risk_score)}%</span>
          </div>
          <div className="risk-item">
            <span className="risk-label">Regulations Checked:</span>
            <span className="risk-value">{results.risk_assessment.regulations_checked.join(', ')}</span>
          </div>
          {results.risk_assessment.recommendations.length > 0 && (
            <div className="risk-recommendations">
              <strong>Recommendations:</strong>
              <ul>
                {results.risk_assessment.recommendations.map((rec, idx) => (
                  <li key={idx}>{rec}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </div>

      {/* Violations Grouped by Severity */}
      <div className="compliance-results-violations">
        <h3>Violations ({filteredViolations.length} violations)</h3>

        {violationsBySeverity.HIGH.length > 0 && (
          <div className="severity-group severity-high">
            <h4>
              High Severity ({violationsBySeverity.HIGH.length})
            </h4>
            <div className="violations-list">
              {violationsBySeverity.HIGH.map((violation, idx) => {
                const detail = results.violation_details.find(
                  (vd) => vd.column === violation.column && vd.pii_type === violation.pii_type
                );
                return (
                  <div key={idx} className="violation-item violation-high">
                    <div className="violation-header">
                      <span className="violation-column">{violation.column}</span>
                      <span className="violation-pii-type">{violation.pii_type}</span>
                      <span className="violation-risk-score">Risk: {Math.round(violation.risk_score * 100)}%</span>
                    </div>
                    <div className="violation-details">
                      {detail?.regulations_affected && detail.regulations_affected.length > 0 && (
                        <div className="violation-regulations">
                          <strong>Regulations Affected:</strong> {detail.regulations_affected.join(', ')}
                        </div>
                      )}
                      {detail?.detection_confidence !== undefined && (
                        <div className="violation-confidence">
                          <strong>Confidence:</strong> {Math.round(detail.detection_confidence * 100)}%
                        </div>
                      )}
                      {detail?.sample_values && detail.sample_values.length > 0 && (
                        <div className="violation-samples">
                          <strong>Sample Values:</strong>
                          <code>{detail.sample_values.join(', ')}</code>
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {violationsBySeverity.MEDIUM.length > 0 && (
          <div className="severity-group severity-medium">
            <h4>
              Medium Severity ({violationsBySeverity.MEDIUM.length})
            </h4>
            <div className="violations-list">
              {violationsBySeverity.MEDIUM.map((violation, idx) => {
                const detail = results.violation_details.find(
                  (vd) => vd.column === violation.column && vd.pii_type === violation.pii_type
                );
                return (
                  <div key={idx} className="violation-item violation-medium">
                    <div className="violation-header">
                      <span className="violation-column">{violation.column}</span>
                      <span className="violation-pii-type">{violation.pii_type}</span>
                      <span className="violation-risk-score">Risk: {Math.round(violation.risk_score * 100)}%</span>
                    </div>
                    <div className="violation-details">
                      {detail?.regulations_affected && detail.regulations_affected.length > 0 && (
                        <div className="violation-regulations">
                          <strong>Regulations Affected:</strong> {detail.regulations_affected.join(', ')}
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {violationsBySeverity.LOW.length > 0 && (
          <div className="severity-group severity-low">
            <h4>
              Low Severity ({violationsBySeverity.LOW.length})
            </h4>
            <div className="violations-list">
              {violationsBySeverity.LOW.map((violation, idx) => (
                <div key={idx} className="violation-item violation-low">
                  <div className="violation-header">
                    <span className="violation-column">{violation.column}</span>
                    <span className="violation-pii-type">{violation.pii_type}</span>
                    <span className="violation-risk-score">Risk: {Math.round(violation.risk_score * 100)}%</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {filteredViolations.length === 0 && (
          <div className="no-violations-message">No violations match the selected filters.</div>
        )}
      </div>

      {/* Remediation Suggestions */}
      {results.remediation_suggestions && results.remediation_suggestions.length > 0 && (
        <div className="compliance-results-remediation">
          <h3>Remediation Suggestions</h3>
          <ul>
            {results.remediation_suggestions.map((suggestion, idx) => (
              <li key={idx} className="remediation-item">
                <div className="remediation-priority priority-{suggestion.priority.toLowerCase()}">
                  {suggestion.priority}
                </div>
                <div className="remediation-content">
                  <div className="remediation-column">
                    <strong>Column:</strong> {suggestion.column}
                  </div>
                  <div className="remediation-pii-type">
                    <strong>PII Type:</strong> {suggestion.pii_type}
                  </div>
                  <div className="remediation-suggestion">{suggestion.suggestion}</div>
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

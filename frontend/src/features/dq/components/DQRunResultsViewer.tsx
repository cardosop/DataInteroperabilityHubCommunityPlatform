/**
 * DQ Run Results Viewer
 * Displays detailed DQ results with filtering and severity grouping
 */

import { useState, useMemo } from 'react';
import type { DQRunResults } from '../../../shared/types/dq';
import './DQRunResultsViewer.css';

interface DQRunResultsViewerProps {
  results: DQRunResults;
}

export function DQRunResultsViewer({ results }: DQRunResultsViewerProps) {
  const [severityFilter, setSeverityFilter] = useState<'ALL' | 'HIGH' | 'MEDIUM' | 'LOW'>('ALL');
  const [categoryFilter, setCategoryFilter] = useState<string>('ALL');
  const [statusFilter, setStatusFilter] = useState<'ALL' | 'PASS' | 'FAIL' | 'WARN'>('ALL');

  // Get unique categories
  const categories = useMemo(() => {
    const cats = new Set<string>();
    results.check_details.forEach((check) => {
      if (check.type) cats.add(check.type);
    });
    return Array.from(cats).sort();
  }, [results.check_details]);

  // Filter check details
  const filteredChecks = useMemo(() => {
    return results.check_details.filter((check) => {
      if (severityFilter !== 'ALL' && check.severity !== severityFilter) return false;
      if (categoryFilter !== 'ALL' && check.type !== categoryFilter) return false;
      if (statusFilter !== 'ALL' && check.status !== statusFilter) return false;
      return true;
    });
  }, [results.check_details, severityFilter, categoryFilter, statusFilter]);

  // Group checks by severity
  const checksBySeverity = useMemo(() => {
    const grouped: Record<string, typeof filteredChecks> = {
      HIGH: [],
      MEDIUM: [],
      LOW: [],
    };
    filteredChecks.forEach((check) => {
      grouped[check.severity].push(check);
    });
    return grouped;
  }, [filteredChecks]);

  return (
    <div className="dq-results-viewer">
      {/* Summary Section */}
      <div className="dq-results-summary">
        <div className="summary-card">
          <div className="summary-label">Overall Status</div>
          <div
            className={`summary-value overall-status-${results.overall_status?.toLowerCase() || 'unknown'}`}
          >
            {results.overall_status || 'UNKNOWN'}
          </div>
        </div>
        <div className="summary-card">
          <div className="summary-label">Quality Score</div>
          <div className="summary-value quality-score">
            {results.quality_score !== null && results.quality_score !== undefined
              ? Math.round(results.quality_score * 100)
              : 0}
            %
          </div>
        </div>
        <div className="summary-card">
          <div className="summary-label">Total Checks</div>
          <div className="summary-value">{results.score_breakdown.total_checks}</div>
        </div>
        <div className="summary-card">
          <div className="summary-label">Passed</div>
          <div className="summary-value passed">{results.score_breakdown.passed_checks}</div>
        </div>
        <div className="summary-card">
          <div className="summary-label">Failed</div>
          <div className="summary-value failed">{results.score_breakdown.failed_checks}</div>
        </div>
        <div className="summary-card">
          <div className="summary-label">Warnings</div>
          <div className="summary-value warning">{results.score_breakdown.warning_checks}</div>
        </div>
      </div>

      {/* Filters */}
      <div className="dq-results-filters">
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
          <label>Category</label>
          <select value={categoryFilter} onChange={(e) => setCategoryFilter(e.target.value)}>
            <option value="ALL">All Categories</option>
            {categories.map((cat) => (
              <option key={cat} value={cat}>
                {cat}
              </option>
            ))}
          </select>
        </div>
        <div className="filter-group">
          <label>Status</label>
          <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value as 'ALL' | 'PASS' | 'FAIL' | 'WARN')}>
            <option value="ALL">All Statuses</option>
            <option value="PASS">Pass</option>
            <option value="FAIL">Fail</option>
            <option value="WARN">Warn</option>
          </select>
        </div>
      </div>

      {/* Score Breakdown by Category */}
      {Object.keys(results.score_breakdown.by_category).length > 0 && (
        <div className="dq-results-category-breakdown">
          <h3>Score Breakdown by Category</h3>
          <div className="category-breakdown-grid">
            {Object.entries(results.score_breakdown.by_category).map(([category, stats]) => (
              <div key={category} className="category-card">
                <div className="category-name">{category}</div>
                <div className="category-stats">
                  <span className="stat-item">
                    Total: <strong>{stats.total}</strong>
                  </span>
                  <span className="stat-item passed">
                    Passed: <strong>{stats.passed}</strong>
                  </span>
                  <span className="stat-item failed">
                    Failed: <strong>{stats.failed}</strong>
                  </span>
                  {stats.warnings > 0 && (
                    <span className="stat-item warning">
                      Warnings: <strong>{stats.warnings}</strong>
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Checks Grouped by Severity */}
      <div className="dq-results-checks">
        <h3>Check Details ({filteredChecks.length} checks)</h3>

        {checksBySeverity.HIGH.length > 0 && (
          <div className="severity-group severity-high">
            <h4>
              High Severity ({checksBySeverity.HIGH.length})
            </h4>
            <div className="checks-list">
              {checksBySeverity.HIGH.map((check, idx) => (
                <div key={idx} className="check-item check-failed">
                  <div className="check-header">
                    <span className="check-name">{check.name}</span>
                    <span className={`check-status status-${check.status.toLowerCase()}`}>
                      {check.status}
                    </span>
                  </div>
                  <div className="check-details">
                    <div className="check-type">Type: {check.type}</div>
                    {check.message && <div className="check-message">{check.message}</div>}
                    {check.expected_value !== undefined && (
                      <div className="check-expected">
                        Expected: <code>{JSON.stringify(check.expected_value)}</code>
                      </div>
                    )}
                    {check.observed_value !== undefined && (
                      <div className="check-observed">
                        Observed: <code>{JSON.stringify(check.observed_value)}</code>
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {checksBySeverity.MEDIUM.length > 0 && (
          <div className="severity-group severity-medium">
            <h4>
              Medium Severity ({checksBySeverity.MEDIUM.length})
            </h4>
            <div className="checks-list">
              {checksBySeverity.MEDIUM.map((check, idx) => (
                <div key={idx} className="check-item check-warning">
                  <div className="check-header">
                    <span className="check-name">{check.name}</span>
                    <span className={`check-status status-${check.status.toLowerCase()}`}>
                      {check.status}
                    </span>
                  </div>
                  <div className="check-details">
                    <div className="check-type">Type: {check.type}</div>
                    {check.message && <div className="check-message">{check.message}</div>}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {checksBySeverity.LOW.length > 0 && (
          <div className="severity-group severity-low">
            <h4>
              Low Severity ({checksBySeverity.LOW.length})
            </h4>
            <div className="checks-list">
              {checksBySeverity.LOW.map((check, idx) => (
                <div key={idx} className="check-item check-pass">
                  <div className="check-header">
                    <span className="check-name">{check.name}</span>
                    <span className={`check-status status-${check.status.toLowerCase()}`}>
                      {check.status}
                    </span>
                  </div>
                  <div className="check-details">
                    <div className="check-type">Type: {check.type}</div>
                    {check.message && <div className="check-message">{check.message}</div>}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {filteredChecks.length === 0 && (
          <div className="no-checks-message">No checks match the selected filters.</div>
        )}
      </div>

      {/* Recommendations */}
      {results.recommendations && results.recommendations.length > 0 && (
        <div className="dq-results-recommendations">
          <h3>Recommendations</h3>
          <ul>
            {results.recommendations.map((rec, idx) => (
              <li key={idx} className="recommendation-item">
                <div className="recommendation-priority priority-{rec.priority.toLowerCase()}">
                  {rec.priority}
                </div>
                <div className="recommendation-content">
                  <div className="recommendation-check">{rec.check_name}</div>
                  <div className="recommendation-issue">{rec.issue}</div>
                  <div className="recommendation-suggestion">{rec.suggestion}</div>
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

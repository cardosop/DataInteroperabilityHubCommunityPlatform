/**
 * Query Execution UI Component
 * SQL editor + results + export + history with cancel/progress support
 */

import { useState, useEffect } from 'react';
import { useExecuteQuery, useQueryExecutions, useQueryExecution, useQueryExecutionProgress, useQueryExecutionResult, useCancelQueryExecution } from '../hooks/useVirtualization';
import { QueryExecutionMode } from '../../../shared/types/virtualization';
import './QueryExecutionUI.css';

interface QueryExecutionUIProps {
  datasetId: string;
}

export function QueryExecutionUI({ datasetId }: QueryExecutionUIProps) {
  const [query, setQuery] = useState('');
  const [parameters, setParameters] = useState('{}');
  const [executionId, setExecutionId] = useState<string | null>(null);
  const [resultPage, setResultPage] = useState(1);
  const [resultPageSize] = useState(100);
  const [showHistory, setShowHistory] = useState(false);

  const executeMutation = useExecuteQuery();
  const { data: executions } = useQueryExecutions({ virtual_dataset: datasetId, page_size: 10 });
  const { data: currentExecution } = useQueryExecution(executionId ?? undefined);
  const { data: progress } = useQueryExecutionProgress(
    executionId ?? undefined,
    currentExecution?.status === 'RUNNING' || currentExecution?.status === 'PENDING'
  );
  const { data: result } = useQueryExecutionResult(
    executionId ?? undefined,
    resultPage,
    resultPageSize,
    'json'
  );
  const cancelMutation = useCancelQueryExecution();

  const handleExecute = async () => {
    if (!query.trim()) {
      alert('Please enter a query');
      return;
    }

    try {
      let params = {};
      try {
        params = JSON.parse(parameters || '{}');
      } catch (e) {
        alert('Invalid JSON in parameters');
        return;
      }

      const execution = await executeMutation.mutateAsync({
        datasetId,
        data: {
          parameters: params,
          execution_mode: QueryExecutionMode.SYNC,
        },
      });

      setExecutionId(execution.id);
      setResultPage(1);
    } catch (err) {
      // Error handled by mutation
    }
  };

  const handleCancel = async () => {
    if (!executionId) return;
    try {
      await cancelMutation.mutateAsync(executionId);
      setExecutionId(null);
    } catch (err) {
      // Error handled by mutation
    }
  };

  const handleExport = async (format: 'json' | 'csv' | 'parquet') => {
    if (!executionId || !result) return;

    try {
      // In a real implementation, this would download the file
      const blob = new Blob([JSON.stringify(result.data, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `query-result-${executionId}.${format}`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err) {
      alert('Failed to export result');
    }
  };

  useEffect(() => {
    if (currentExecution?.status === 'COMPLETED' && !result) {
      // Auto-fetch result when execution completes
    }
  }, [currentExecution?.status, result]);

  const isRunning = currentExecution?.status === 'RUNNING' || currentExecution?.status === 'PENDING';

  return (
    <div className="query-execution-ui">
      <div className="query-editor-section">
        <div className="section-header">
          <h3>Query Editor</h3>
          <div className="editor-actions">
            <button
              onClick={handleExecute}
              className="btn-primary"
              type="button"
              disabled={executeMutation.isPending || isRunning}
            >
              {executeMutation.isPending ? 'Executing...' : 'Execute Query'}
            </button>
            {isRunning && (
              <button
                onClick={handleCancel}
                className="btn-danger"
                type="button"
                disabled={cancelMutation.isPending}
              >
                {cancelMutation.isPending ? 'Cancelling...' : 'Cancel'}
              </button>
            )}
            <button
              onClick={() => setShowHistory(!showHistory)}
              className="btn-secondary"
              type="button"
            >
              {showHistory ? 'Hide' : 'Show'} History
            </button>
          </div>
        </div>

        <textarea
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Enter your query here..."
          className="query-editor"
          rows={10}
        />

        <div className="parameters-section">
          <label htmlFor="parameters">Parameters (JSON):</label>
          <textarea
            id="parameters"
            value={parameters}
            onChange={(e) => setParameters(e.target.value)}
            placeholder='{"param1": "value1"}'
            className="parameters-editor"
            rows={3}
          />
        </div>
      </div>

      {isRunning && progress && (
        <div className="progress-section">
          <h3>Execution Progress</h3>
          <div className="progress-bar-container">
            <div
              className="progress-bar"
              style={{ width: `${progress.progress_percentage || 0}%` }}
            />
          </div>
          <p>Status: {progress.status}</p>
          {progress.duration_seconds && (
            <p>Duration: {progress.duration_seconds.toFixed(2)}s</p>
          )}
        </div>
      )}

      {currentExecution?.status === 'COMPLETED' && result && (
        <div className="results-section">
          <div className="section-header">
            <h3>Results</h3>
            <div className="result-actions">
              <button onClick={() => handleExport('json')} className="btn-secondary" type="button">
                Export JSON
              </button>
              <button onClick={() => handleExport('csv')} className="btn-secondary" type="button">
                Export CSV
              </button>
              <span className="result-count">
                {result.returned_count} of {result.total_count} rows
              </span>
            </div>
          </div>

          <div className="results-table-container">
            <table className="results-table">
              <thead>
                {Array.isArray(result.data) && result.data.length > 0 && (
                  <tr>
                    {Object.keys(result.data[0]).map((key) => (
                      <th key={key}>{key}</th>
                    ))}
                  </tr>
                )}
              </thead>
              <tbody>
                {Array.isArray(result.data) ? (
                  result.data.map((row: any, index: number) => (
                    <tr key={index}>
                      {Object.values(row).map((value: any, colIndex: number) => (
                        <td key={colIndex}>{String(value ?? '')}</td>
                      ))}
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={100}>{JSON.stringify(result.data, null, 2)}</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>

          {result.pagination && (
            <div className="results-pagination">
              <button
                onClick={() => setResultPage((p) => Math.max(1, p - 1))}
                className="btn-secondary"
                disabled={!result.pagination.has_previous}
                type="button"
              >
                Previous
              </button>
              <span>
                Page {result.pagination.page} of {result.pagination.total_pages}
              </span>
              <button
                onClick={() => setResultPage((p) => p + 1)}
                className="btn-secondary"
                disabled={!result.pagination.has_next}
                type="button"
              >
                Next
              </button>
            </div>
          )}
        </div>
      )}

      {executeMutation.isError && (
        <div className="error-section">
          <h3>Execution Failed</h3>
          <p>
            {(executeMutation.error as Error)?.message || 'Failed to start execution'}
          </p>
        </div>
      )}

      {currentExecution?.status === 'FAILED' && (
        <div className="error-section">
          <h3>Execution Failed</h3>
          <p>{currentExecution.execution_log || 'Unknown error occurred'}</p>
        </div>
      )}

      {showHistory && executions && (
        <div className="history-section">
          <h3>Execution History</h3>
          <div className="history-list">
            {executions.results.map((exec) => (
              <div
                key={exec.id}
                className={`history-item ${exec.id === executionId ? 'selected' : ''}`}
                onClick={() => {
                  setExecutionId(exec.id);
                  setResultPage(1);
                }}
              >
                <div className="history-item-header">
                  <span className="history-status">{exec.status}</span>
                  <span className="history-date">{new Date(exec.created_at).toLocaleString()}</span>
                </div>
                {exec.started_at && exec.completed_at && (
                  <div className="history-duration">
                    Duration: {(
                      (new Date(exec.completed_at).getTime() - new Date(exec.started_at).getTime()) / 1000
                    ).toFixed(2)}s
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

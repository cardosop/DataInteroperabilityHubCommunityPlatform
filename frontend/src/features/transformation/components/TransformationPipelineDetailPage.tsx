/**
 * Transformation Pipeline Detail Page
 * Shows full pipeline info, steps, action buttons, and recent executions
 */

import { useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { DetailPageSkeleton } from '../../../shared/components/skeletons/DetailPageSkeleton';
import { UuidWithCopy } from '../../../shared/components/UuidWithCopy';
import { Breadcrumbs } from '../../../shared/components/Breadcrumbs';
import { Button } from '../../../shared/components/Button';
import { ConfirmDialog } from '../../../shared/components/ConfirmDialog';
import {
  useTransformationPipeline,
  useUpdateTransformationPipeline,
  useDeleteTransformationPipeline,
  useExecuteTransformationPipeline,
  useTransformationExecutions,
} from '../hooks/useTransformationPipelines';
import { PipelineStatus } from '../../../shared/types/transformation';
import './TransformationPipelineDetailPage.css';

function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return '\u2014';
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return '\u2014';
  }
}

export function TransformationPipelineDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { data, isLoading, error } = useTransformationPipeline(id ?? null);
  const updateMutation = useUpdateTransformationPipeline();
  const deleteMutation = useDeleteTransformationPipeline();
  const executeMutation = useExecuteTransformationPipeline();

  // Fetch recent executions scoped to this pipeline
  const { data: executionsData } = useTransformationExecutions(
    id ? { page_size: 10 } : {},
  );

  const [confirmDeleteOpen, setConfirmDeleteOpen] = useState(false);
  const [executeAssetId, setExecuteAssetId] = useState('');
  const [showExecuteForm, setShowExecuteForm] = useState(false);

  if (isLoading) {
    return <DetailPageSkeleton />;
  }

  if (error) {
    return (
      <div className="transformation-detail-page">
        <ErrorDisplay error={error} title="Pipeline not found" />
      </div>
    );
  }

  if (!data) {
    return (
      <div className="transformation-detail-page">
        <ErrorDisplay
          error={new Error('Pipeline not found')}
          title="Pipeline not found"
        />
      </div>
    );
  }

  const steps = data.pipeline_definition?.steps ?? [];

  const handleActivate = () => {
    if (!id) return;
    updateMutation.mutate({ id, data: { status: PipelineStatus.ACTIVE } });
  };

  const handleDelete = () => {
    if (!id) return;
    deleteMutation.mutate(id, {
      onSuccess: () => navigate('/transformation'),
    });
  };

  const handleExecute = (e: React.FormEvent) => {
    e.preventDefault();
    if (!id || !executeAssetId.trim()) return;
    executeMutation.mutate(
      { id, data: { asset_id: executeAssetId.trim() } },
      {
        onSuccess: (execution) => {
          setShowExecuteForm(false);
          setExecuteAssetId('');
          navigate(`/transformation/executions/${execution.id}`);
        },
      },
    );
  };

  // Filter executions for this pipeline
  const pipelineExecutions = (executionsData?.results ?? []).filter(
    (ex) => ex.pipeline === id,
  );

  return (
    <div className="transformation-detail-page">
      <div className="transformation-detail-content">
        <Breadcrumbs
          items={[
            { label: 'Home', href: '/' },
            { label: 'Transformations', href: '/transformation' },
            { label: data.name || 'Pipeline' },
          ]}
        />

        <div className="transformation-detail-header">
          <h1>{data.name}</h1>
          <div className="transformation-detail-actions">
            {data.status === PipelineStatus.DRAFT && (
              <Button
                variant="secondary"
                onClick={handleActivate}
                disabled={updateMutation.isPending}
              >
                {updateMutation.isPending ? 'Activating...' : 'Activate'}
              </Button>
            )}
            <Button
              variant="primary"
              onClick={() => setShowExecuteForm(!showExecuteForm)}
            >
              Execute
            </Button>
            <Button
              variant="danger"
              onClick={() => setConfirmDeleteOpen(true)}
              disabled={deleteMutation.isPending}
            >
              Delete
            </Button>
          </div>
        </div>

        {data.description && (
          <p className="transformation-detail-description">{data.description}</p>
        )}

        <div className="transformation-detail-metadata">
          <span
            className={`status-badge status-${(data.status || 'draft').toLowerCase()}`}
            aria-label={`Status: ${data.status}`}
          >
            {data.status}
          </span>
          <div className="pipeline-uuid" data-testid="transformation-pipeline-uuid">
            <UuidWithCopy value={data.id} label="Pipeline ID" />
          </div>
        </div>

        <div className="transformation-detail-info-grid">
          <div className="info-item">
            <span className="info-label">Version</span>
            <span className="info-value"><code>{data.version || '1.0.0'}</code></span>
          </div>
          <div className="info-item">
            <span className="info-label">Steps</span>
            <span className="info-value">{steps.length}</span>
          </div>
          <div className="info-item">
            <span className="info-label">Created</span>
            <span className="info-value">{formatDateTime(data.created_at)}</span>
          </div>
          <div className="info-item">
            <span className="info-label">Updated</span>
            <span className="info-value">{formatDateTime(data.updated_at)}</span>
          </div>
        </div>

        {/* Execute form */}
        {showExecuteForm && (
          <div className="transformation-execute-form-card">
            <h3>Execute Pipeline</h3>
            <form onSubmit={handleExecute} className="transformation-execute-form">
              <div className="form-field">
                <label htmlFor="execute-asset-id">Asset ID *</label>
                <input
                  id="execute-asset-id"
                  type="text"
                  value={executeAssetId}
                  onChange={(e) => setExecuteAssetId(e.target.value)}
                  placeholder="Enter asset UUID"
                  required
                />
              </div>
              <div className="form-actions">
                <button type="button" onClick={() => setShowExecuteForm(false)}>
                  Cancel
                </button>
                <Button
                  type="submit"
                  variant="primary"
                  disabled={executeMutation.isPending || !executeAssetId.trim()}
                >
                  {executeMutation.isPending ? 'Starting...' : 'Start Execution'}
                </Button>
              </div>
            </form>
          </div>
        )}

        {/* Pipeline Steps */}
        <section className="transformation-steps-section">
          <h2>Pipeline Steps ({steps.length})</h2>
          {steps.length === 0 ? (
            <p className="transformation-steps-empty">No steps defined in this pipeline.</p>
          ) : (
            <div className="transformation-steps-list">
              {steps.map((step, index) => (
                <div key={index} className="transformation-step-card">
                  <div className="step-card-header">
                    <span className="step-number">Step {index + 1}</span>
                    <span className="step-type-badge">{step.type}</span>
                  </div>
                  <div className="step-card-body">
                    <strong>{step.name}</strong>
                    {step.config && Object.keys(step.config).length > 0 && (
                      <pre className="step-config-preview">
                        {JSON.stringify(step.config, null, 2).slice(0, 200)}
                        {JSON.stringify(step.config, null, 2).length > 200 ? '...' : ''}
                      </pre>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>

        {/* Recent Executions */}
        <section className="transformation-executions-section">
          <h2>Recent Executions</h2>
          {pipelineExecutions.length === 0 ? (
            <p className="transformation-executions-empty">No executions yet.</p>
          ) : (
            <div className="transformation-executions-table">
              <table role="table" aria-label="Pipeline executions">
                <thead>
                  <tr>
                    <th scope="col">ID</th>
                    <th scope="col">Status</th>
                    <th scope="col">Mode</th>
                    <th scope="col">Started</th>
                    <th scope="col">Completed</th>
                  </tr>
                </thead>
                <tbody>
                  {pipelineExecutions.map((exec) => (
                    <tr
                      key={exec.id}
                      role="button"
                      tabIndex={0}
                      className="execution-row"
                      onClick={() => navigate(`/transformation/executions/${exec.id}`)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' || e.key === ' ') {
                          e.preventDefault();
                          navigate(`/transformation/executions/${exec.id}`);
                        }
                      }}
                      aria-label={`Execution ${exec.id.slice(0, 8)}`}
                    >
                      <td><code>{exec.id.slice(0, 8)}...</code></td>
                      <td>
                        <span className={`status-badge status-${exec.status.toLowerCase()}`}>
                          {exec.status}
                        </span>
                      </td>
                      <td>{exec.execution_mode}</td>
                      <td>{formatDateTime(exec.started_at)}</td>
                      <td>{formatDateTime(exec.completed_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </div>

      <ConfirmDialog
        isOpen={confirmDeleteOpen}
        onClose={() => setConfirmDeleteOpen(false)}
        onConfirm={handleDelete}
        title="Delete Pipeline"
        message={`Are you sure you want to delete "${data.name}"? This action cannot be undone.`}
        confirmLabel="Delete"
        cancelLabel="Cancel"
        variant="warning"
      />
    </div>
  );
}

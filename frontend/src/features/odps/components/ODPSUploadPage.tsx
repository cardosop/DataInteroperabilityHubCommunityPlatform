/**
 * ODPS Upload Page
 * Upload ODPS JSON/YAML and show workflow progress
 */

import { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useCreateODPSProduct, useODPSWorkflowStatus } from '../hooks/useODPS';
import { LoadingSpinner } from '../../../shared/components/LoadingSpinner';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { Breadcrumbs } from '../../../shared/components/Breadcrumbs';
import { AssetPicker } from '../../../shared/components/pickers';
import { ContractFormat } from '../../../shared/types/contracts';
import { UuidWithCopy } from '../../../shared/components/UuidWithCopy';
import { useToast } from '../../../shared/components/Toast';
import './ODPSUploadPage.css';
import { Button } from '../../../shared/components/Button';

export function ODPSUploadPage() {
  const navigate = useNavigate();
  const toast = useToast();
  const [odpsContent, setOdpsContent] = useState('');
  const [format, setFormat] = useState<ContractFormat>(ContractFormat.JSON);
  const [resolveExternalRefs, setResolveExternalRefs] = useState(true);
  const [assetId, setAssetId] = useState<string | null>(null);
  const [workflowInstanceId, setWorkflowInstanceId] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const createMutation = useCreateODPSProduct();

  // Poll workflow status if workflow instance ID is set
  const { data: workflowStatus, error: workflowError } = useODPSWorkflowStatus(workflowInstanceId, {
    enabled: !!workflowInstanceId,
    refetchInterval: 2000,
  });

  // Navigate to ODPS detail page when workflow completes
  useEffect(() => {
    if (workflowStatus?.status === 'COMPLETED' && workflowStatus.odps_contract?.id) {
      const contractId = workflowStatus.odps_contract.id;
      const t = setTimeout(() => {
        navigate(`/odps/${contractId}`);
      }, 2000);
      return () => clearTimeout(t);
    }
  }, [workflowStatus?.status, workflowStatus?.odps_contract?.id, workflowStatus?.odps_contract, navigate]);

  const handleFileSelect = async (file: File) => {
    try {
      const text = await file.text();
      setOdpsContent(text);
      
      // Auto-detect format from file extension
      const extension = file.name.split('.').pop()?.toLowerCase();
      if (extension === 'yaml' || extension === 'yml') {
        setFormat(ContractFormat.YAML);
      } else if (extension === 'json') {
        setFormat(ContractFormat.JSON);
      }
    } catch (error) {
      console.error('Failed to read file:', error);
    }
  };

  const handleFileInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      handleFileSelect(file);
    }
  };

  const handleSubmit = async () => {
    if (!odpsContent.trim()) {
      toast.error('Please provide ODPS content');
      return;
    }

    try {
      const response = await createMutation.mutateAsync({
        original_raw: odpsContent,
        original_format: format,
        resolve_external_refs: resolveExternalRefs,
        asset_id: assetId ?? undefined,
      });

      setWorkflowInstanceId(response.workflow_instance_id);
    } catch {
      // Error is surfaced via createMutation.error and displayed in the UI
    }
  };

  const handleReset = () => {
    setOdpsContent('');
    setAssetId(null);
    setWorkflowInstanceId(null);
    createMutation.reset();
  };

  const isWorkflowRunning = workflowStatus?.status === 'RUNNING' || workflowStatus?.status === 'PENDING';
  const isWorkflowCompleted = workflowStatus?.status === 'COMPLETED';
  const isWorkflowFailed = workflowStatus?.status === 'FAILED';

  return (
    <div className="odps-upload-page">
      <Breadcrumbs
        items={[
          { label: 'Home', href: '/' },
          { label: 'ODPS', href: '/odps' },
          { label: 'Upload' },
        ]}
      />
      <div className="odps-upload-header">
        <Button onClick={() => navigate('/odps')} variant="ghost">
          ← Back to ODPS
        </Button>
        <h1>Create ODPS Product</h1>
      </div>

      <div className="odps-upload-content">
        {!workflowInstanceId ? (
          <div className="odps-upload-form">
            <div className="form-section">
              <label htmlFor="odps-file">Upload ODPS File (JSON or YAML)</label>
              <input
                ref={fileInputRef}
                id="odps-file"
                type="file"
                accept=".json,.yaml,.yml"
                onChange={handleFileInputChange}
                className="file-input"
              />
              <Button
 onClick={() => fileInputRef.current?.click()}
 variant="secondary">
                Select File
              </Button>
            </div>

            <div className="form-section">
              <label htmlFor="odps-format">Format</label>
              <select
                id="odps-format"
                value={format}
                onChange={(e) => setFormat(e.target.value as ContractFormat)}
              >
                <option value="JSON">JSON</option>
                <option value="YAML">YAML</option>
              </select>
            </div>

            <div className="form-section">
              <label htmlFor="odps-content">ODPS Content</label>
              <textarea
                id="odps-content"
                value={odpsContent}
                onChange={(e) => setOdpsContent(e.target.value)}
                placeholder="Paste ODPS content here or upload a file..."
                rows={20}
                className="odps-content-editor"
                spellCheck={false}
              />
            </div>

            <div className="form-section">
              <label>
                <input
                  type="checkbox"
                  checked={resolveExternalRefs}
                  onChange={(e) => setResolveExternalRefs(e.target.checked)}
                />
                Resolve external $ref references
              </label>
            </div>

            <div className="form-section">
              <label htmlFor="asset-picker">Asset to link (optional)</label>
              <AssetPicker
                value={assetId}
                onChange={setAssetId}
                placeholder="Search and select an asset to link..."
                data-testid="odps-upload-asset-picker"
              />
            </div>

            <div className="form-actions">
              <Button
 onClick={handleSubmit}
 disabled={createMutation.isPending || !odpsContent.trim()}
 variant="primary">
                {createMutation.isPending ? 'Creating...' : 'Create ODPS Product'}
              </Button>
              <Button onClick={handleReset} variant="secondary">
                Reset
              </Button>
            </div>

            {createMutation.isError && (
              <ErrorDisplay
                error={createMutation.error}
                title="Failed to create ODPS product"
                onRetry={() => createMutation.reset()}
              />
            )}
          </div>
        ) : (
          <div className="odps-workflow-progress">
            <h2>Workflow Progress</h2>
            {isWorkflowRunning && (
              <div className="workflow-running">
                <LoadingSpinner />
                <p>Processing ODPS product creation...</p>
                {workflowStatus?.progress_percentage !== undefined && (
                  <div className="progress-bar-container">
                    <div className="progress-bar">
                      <div
                        className="progress-bar-fill"
                        style={{ width: `${workflowStatus.progress_percentage}%` }}
                      />
                    </div>
                    <span className="progress-text">{workflowStatus.progress_percentage}%</span>
                  </div>
                )}
                {workflowStatus?.current_step_name && (
                  <p className="current-step">Current step: {workflowStatus.current_step_name}</p>
                )}
              </div>
            )}

            {isWorkflowCompleted && (
              <div className="workflow-completed">
                <div className="success-icon">✓</div>
                <h3>ODPS Product Created Successfully!</h3>
                {workflowStatus.odps_contract && (
                  <div className="created-contracts">
                    <div className="created-contract-id">
                      <UuidWithCopy value={workflowStatus.odps_contract.id} label="ODPS Contract" />
                      <button
                        onClick={() => navigate(`/odps/${workflowStatus.odps_contract!.id}`)}
                        className="btn-link"
                        type="button"
                      >
                        View
                      </button>
                    </div>
                    {workflowStatus.odcs_contract && (
                      <div className="created-contract-id">
                        <UuidWithCopy value={workflowStatus.odcs_contract.id} label="ODCS Contract" />
                        <button
                          onClick={() => navigate(`/contracts/${workflowStatus.odcs_contract!.id}`)}
                          className="btn-link"
                          type="button"
                        >
                          View
                        </button>
                      </div>
                    )}
                  </div>
                )}
                <p>Redirecting to ODPS detail page...</p>
              </div>
            )}

            {isWorkflowFailed && (
              <div className="workflow-failed">
                <div className="error-icon">✗</div>
                <h3>Workflow Failed</h3>
                <p>{workflowStatus?.message || 'An error occurred during workflow execution'}</p>
                <Button onClick={handleReset} variant="primary">
                  Try Again
                </Button>
              </div>
            )}

            {workflowError && (
              <ErrorDisplay
                error={workflowError}
                title="Failed to get workflow status"
                onRetry={() => window.location.reload()}
              />
            )}
          </div>
        )}
      </div>
    </div>
  );
}

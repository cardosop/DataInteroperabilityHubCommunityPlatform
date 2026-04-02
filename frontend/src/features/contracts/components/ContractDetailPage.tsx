/**
 * Contract Detail Page
 * Display contract details with operations and lineage (real API; no stub data).
 */

import { useParams, useNavigate } from 'react-router-dom';
import { useState } from 'react';
import { useContract, useValidateContract, useLintContract, useConvertContract, useExportContract, useDownloadContract } from '../hooks/useContracts';
import { ContractLineageVisualization } from '../../lineage/components/ContractLineageVisualization';
import { DetailPageSkeleton } from '../../../shared/components/skeletons/DetailPageSkeleton';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import {
  ContractFormat,
  type ContractValidationResult,
  type ContractLintResult,
  type ContractConvertResult,
  getContractLinkedAssetId,
} from '../../../shared/types/contracts';
import { UuidWithCopy } from '../../../shared/components/UuidWithCopy';
import { Breadcrumbs } from '../../../shared/components/Breadcrumbs';
import './ContractDetailPage.css';
import { Button } from '../../../shared/components/Button';

type ContractDetailTab = 'details' | 'lineage';

export function ContractDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState<ContractDetailTab>('details');
  const { data: contract, isLoading, error, refetch } = useContract(id || null);
  const validateMutation = useValidateContract();
  const lintMutation = useLintContract();
  const convertMutation = useConvertContract();
  const exportMutation = useExportContract();
  const downloadMutation = useDownloadContract();
  const [validationResult, setValidationResult] = useState<ContractValidationResult | null>(null);
  const [lintResult, setLintResult] = useState<ContractLintResult | null>(null);
  const [convertResult, setConvertResult] = useState<ContractConvertResult | null>(null);

  const handleValidate = async () => {
    if (!id) return;
    try {
      const result = await validateMutation.mutateAsync(id);
      setValidationResult(result);
    } catch {
      // Error handled by mutation
    }
  };

  const handleLint = async () => {
    if (!id) return;
    try {
      const result = await lintMutation.mutateAsync(id);
      setLintResult(result);
    } catch {
      // Error handled by mutation
    }
  };

  const handleConvert = async (targetFormat: ContractFormat) => {
    if (!id) return;
    try {
      const result = await convertMutation.mutateAsync({ id, data: { target_format: targetFormat } });
      setConvertResult(result);
    } catch {
      // Error handled by mutation
    }
  };

  const handleExport = async (format?: string) => {
    if (!id) return;
    try {
      const blob = await exportMutation.mutateAsync({ id, format });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `contract-${id}.${format || (contract?.original_format ?? 'json').toLowerCase()}`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
    } catch {
      // Error handled by mutation
    }
  };

  const handleDownload = async (format?: string) => {
    if (!id) return;
    try {
      const blob = await downloadMutation.mutateAsync({ id, format });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `contract-${id}.${format || (contract?.original_format ?? 'json').toLowerCase()}`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
    } catch {
      // Error handled by mutation
    }
  };

  if (isLoading) return <DetailPageSkeleton />;
  if (error || !contract) {
    return <ErrorDisplay error={error || new Error('Contract not found')} title="Failed to load contract" onRetry={() => refetch()} />;
  }

  const linkedAssetId = getContractLinkedAssetId(contract);

  return (
    <div className="contract-detail-page">
      <div className="contract-detail-header">
        <Button onClick={() => navigate('/contracts')} variant="ghost">
          ← Back to Contracts
        </Button>
        <div className="contract-detail-actions">
          {contract.original_spec_type === 'ODCS' && (
            <Button onClick={() => navigate(`/contracts/${id}/link-odps`)} variant="secondary">
              Link ODPS
            </Button>
          )}
          <Button onClick={() => navigate(`/contracts/${id}/edit`)} variant="secondary">Edit</Button>
        </div>
      </div>

      <div className="contract-detail-tabs" role="tablist" aria-label="Contract sections">
        <button
          type="button"
          role="tab"
          aria-selected={activeTab === 'details'}
          className={`contract-detail-tab ${activeTab === 'details' ? 'active' : ''}`}
          onClick={() => setActiveTab('details')}
        >
          Details
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={activeTab === 'lineage'}
          className={`contract-detail-tab ${activeTab === 'lineage' ? 'active' : ''}`}
          onClick={() => setActiveTab('lineage')}
        >
          Lineage
        </button>
      </div>

      <div className="contract-detail-content">
        <Breadcrumbs
          items={[
            { label: 'Home', href: '/' },
            { label: 'Contracts', href: '/contracts' },
            { label: contract.name || 'Contract' },
          ]}
        />
        <div className="contract-detail-main">
          {activeTab === 'lineage' && id ? (
            <ContractLineageVisualization contractId={id} maxDepth={10} />
          ) : (
            <>
          <h1>{contract.name || 'Unnamed Contract'}</h1>
          {id && (
            <div className="contract-uuid" data-testid="contract-uuid">
              <UuidWithCopy value={id} label="Contract ID" />
            </div>
          )}
          {contract.description && <p className="contract-description">{contract.description}</p>}

          <div className="contract-detail-metadata">
            <div className="metadata-item">
              <label>Format</label>
              <span>{contract.original_format ?? '—'}</span>
            </div>
            <div className="metadata-item">
              <label>Normalization Status</label>
              <span className={`status-badge status-${(contract.normalization_status ?? '').toLowerCase().replace('_', '-')}`}>
                {contract.normalization_status ?? '—'}
              </span>
            </div>
            <div className="metadata-item">
              <label>Validation Status</label>
              <span className={`validation-badge validation-${(contract.validation_status ?? '').toLowerCase()}`}>
                {contract.validation_status ?? '—'}
              </span>
            </div>
            <div className="metadata-item">
              <label>Created</label>
              <span>{new Date(contract.created_at).toLocaleString()}</span>
            </div>
            <div className="metadata-item">
              <label>Updated</label>
              <span>{new Date(contract.updated_at).toLocaleString()}</span>
            </div>
          </div>

          <div className="contract-operations">
            <h2>Operations</h2>
            <div className="operations-grid">
              <Button
 onClick={handleValidate}
 loading={validateMutation.isPending}
 variant="primary">
                Validate
              </Button>
              <Button
 onClick={handleLint}
 loading={lintMutation.isPending}
 variant="primary">
                Lint
              </Button>
              <Button
 onClick={() => handleConvert((contract.original_format ?? ContractFormat.JSON) === ContractFormat.JSON ? ContractFormat.YAML : ContractFormat.JSON)}
 loading={convertMutation.isPending}
 variant="primary">
                {convertMutation.isPending ? 'Converting...' : `Convert to ${(contract.original_format ?? ContractFormat.JSON) === ContractFormat.JSON ? 'YAML' : 'JSON'}`}
              </Button>
              <Button
 onClick={() => handleExport()}
 loading={exportMutation.isPending}
 variant="primary">
                Export
              </Button>
              <Button
 onClick={() => handleDownload()}
 loading={downloadMutation.isPending}
 variant="primary">
                Download
              </Button>
            </div>

            {validationResult && (
              <div className={`operation-result ${validationResult.valid ? 'success' : 'error'}`}>
                <h3>Validation Result</h3>
                {validationResult.valid ? (
                  <p>✓ Contract is valid</p>
                ) : (
                  <>
                    <p>✗ Contract has errors:</p>
                    <ul>
                      {validationResult.errors?.map((err: { message: string }, idx: number) => (
                        <li key={idx}>{err.message}</li>
                      ))}
                    </ul>
                  </>
                )}
              </div>
            )}

            {lintResult && (
              <div className={`operation-result ${lintResult.valid ? 'success' : 'warning'}`}>
                <h3>Lint Result</h3>
                {lintResult.valid ? (
                  <p>✓ No linting issues</p>
                ) : (
                  <>
                    <p>⚠ Linting issues found:</p>
                    <ul>
                      {lintResult.issues?.map((issue: { message: string; severity: string }, idx: number) => (
                        <li key={idx} className={`issue-${issue.severity}`}>{issue.message}</li>
                      ))}
                    </ul>
                  </>
                )}
              </div>
            )}

            {convertResult && (
              <div className="operation-result success">
                <h3>Convert Result</h3>
                <pre className="converted-content">{convertResult.converted_raw}</pre>
                <Button
 onClick={() => {
 const blob = new Blob([convertResult.converted_raw], { type: 'text/plain' });
 const url = window.URL.createObjectURL(blob);
 const a = document.createElement('a');
 a.href = url;
 a.download = `contract-converted.${(convertResult.format ?? 'json').toLowerCase()}`;
 document.body.appendChild(a);
 a.click();
 document.body.removeChild(a);
 window.URL.revokeObjectURL(url);
 }}
 variant="secondary">
                  Download Converted
                </Button>
              </div>
            )}
          </div>

          {/* Linked Asset section */}
          {linkedAssetId && (
            <div className="contract-linked-asset" data-testid="contract-linked-asset">
              <h2>Linked Asset</h2>
              <div className="linked-asset-row">
                <UuidWithCopy value={linkedAssetId} label="Asset ID" />
                <button
                  type="button"
                  className="btn-link"
                  onClick={() => navigate(`/assets/${linkedAssetId}`)}
                  data-testid="contract-linked-asset-view"
                >
                  View Asset
                </button>
              </div>
            </div>
          )}

          <div className="contract-raw">
            <h2>Raw Contract</h2>
            <pre className="contract-content">{contract.original_raw}</pre>
          </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

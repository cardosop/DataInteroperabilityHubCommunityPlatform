/**
 * Asset Detail Page
 * Displays asset details with linked contracts and datasets
 */

import { useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { LoadingSpinner } from '../../../shared/components/LoadingSpinner';
import type { File } from '../../../shared/types/files';
import { useComplianceRuns, useCreateComplianceRun } from '../../compliance/hooks/useCompliance';
import { useCreateDataset } from '../../datasets/hooks/useDatasets';
import { useCreateDQRun, useDQRuns } from '../../dq/hooks/useDQ';
import { FileUpload } from '../../files/components/FileUpload';
import {
  useActivateAsset,
  useAsset,
  useAssetHealthScore,
  useAssetRecommendations,
  useAttachContract,
  useAttachDataset,
  useRecalculateHealthScore,
} from '../hooks/useAssets';
import './AssetDetailPage.css';

export function AssetDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { data: asset, isLoading, error, refetch } = useAsset(id || null);
  const activateMutation = useActivateAsset();
  const attachContractMutation = useAttachContract();
  const attachDatasetMutation = useAttachDataset();
  const createDatasetMutation = useCreateDataset();
  const [showFileUpload, setShowFileUpload] = useState(false);
  const [contractId, setContractId] = useState('');
  const [datasetId, setDatasetId] = useState('');

  // DQ and Compliance runs for this asset (only fetch if asset is loaded)
  const { data: dqRuns } = useDQRuns(
    asset?.dataset_id ? { dataset_id: asset.dataset_id, page_size: 5 } : {}
  );
  const { data: complianceRuns } = useComplianceRuns(id ? { asset: id, page_size: 5 } : {});
  const createDQRunMutation = useCreateDQRun();
  const createComplianceRunMutation = useCreateComplianceRun();
  const {
    data: healthScore,
    isLoading: healthScoreLoading,
    refetch: refetchHealthScore,
  } = useAssetHealthScore(id || null, { breakdown: true });
  const recalculateHealthScoreMutation = useRecalculateHealthScore();
  const { data: recommendations } = useAssetRecommendations(id ? { asset_id: id, limit: 5 } : {});

  const handleActivate = async () => {
    if (!id || !asset) return;
    try {
      await activateMutation.mutateAsync({ id, version: asset.version });
      refetch();
    } catch (err) {
      // Error handled by mutation
    }
  };

  const handleFileUploaded = async (file: File) => {
    if (!id) return;
    try {
      // Create dataset from uploaded file
      const dataset = await createDatasetMutation.mutateAsync({
        file_id: file.id,
        asset_id: id,
      });
      // Attach dataset to asset
      await attachDatasetMutation.mutateAsync({ id, data: { dataset_id: dataset.id } });
      setShowFileUpload(false);
      refetch();
    } catch (err) {
      // Error handled by mutation
    }
  };

  const handleAttachContract = async () => {
    if (!id || !contractId.trim()) return;
    try {
      await attachContractMutation.mutateAsync({ id, data: { contract_id: contractId.trim() } });
      setContractId('');
      refetch();
    } catch (err) {
      // Error handled by mutation
    }
  };

  const handleAttachDataset = async () => {
    if (!id || !datasetId.trim()) return;
    try {
      await attachDatasetMutation.mutateAsync({ id, data: { dataset_id: datasetId.trim() } });
      setDatasetId('');
      refetch();
    } catch (err) {
      // Error handled by mutation
    }
  };

  const handleRunDQ = async () => {
    if (!id) return;
    try {
      await createDQRunMutation.mutateAsync({
        asset_id: id,
        dataset_id: asset?.dataset_id,
      });
      // Refetch will happen automatically via query invalidation
    } catch (err) {
      // Error handled by mutation
    }
  };

  const handleRunCompliance = async () => {
    if (!id) return;
    try {
      await createComplianceRunMutation.mutateAsync({
        asset_id: id,
        dataset_id: asset?.dataset_id,
        scan_mode: 'internal',
      });
      // Refetch will happen automatically via query invalidation
    } catch (err) {
      // Error handled by mutation
    }
  };

  if (isLoading) {
    return <LoadingSpinner message="Loading asset..." />;
  }

  if (error || !asset) {
    return (
      <ErrorDisplay
        error={error || new Error('Asset not found')}
        title="Failed to load asset"
        onRetry={() => refetch()}
      />
    );
  }

  const canActivate = asset.status === 'DRAFT';

  return (
    <div className="asset-detail-page">
      <div className="asset-detail-header">
        <button onClick={() => navigate('/assets')} className="btn-back" type="button">
          ← Back to Assets
        </button>
        <div className="asset-detail-actions">
          {canActivate && (
            <button
              onClick={handleActivate}
              disabled={activateMutation.isPending}
              className="btn-primary"
              type="button"
            >
              {activateMutation.isPending ? 'Activating...' : 'Activate Asset'}
            </button>
          )}
        </div>
      </div>

      <div className="asset-detail-content">
        <div className="asset-detail-main">
          <h1>{asset.name}</h1>
          <p className="asset-key">
            Key: <code>{asset.key}</code>
          </p>
          {asset.description && <p className="asset-description">{asset.description}</p>}

          <div className="asset-detail-metadata">
            <div className="metadata-item">
              <label>Status</label>
              <span className={`status-badge status-${asset.status.toLowerCase()}`}>
                {asset.status}
              </span>
            </div>
            <div className="metadata-item">
              <label>Visibility</label>
              <span className={`visibility-badge visibility-${asset.visibility.toLowerCase()}`}>
                {asset.visibility}
              </span>
            </div>
            {asset.domain && (
              <div className="metadata-item">
                <label>Domain</label>
                <span>{asset.domain}</span>
              </div>
            )}
            <div className="metadata-item">
              <label>DQ Status</label>
              <span className={`dq-badge dq-${asset.dq_status.toLowerCase()}`}>
                {asset.dq_status}
              </span>
            </div>
            <div className="metadata-item">
              <label>Compliance Status</label>
              <span
                className={`compliance-badge compliance-${asset.compliance_status.toLowerCase().replace('_', '-')}`}
              >
                {asset.compliance_status}
              </span>
            </div>
            <div className="metadata-item">
              <label>Created</label>
              <span>{new Date(asset.created_at).toLocaleString()}</span>
            </div>
            <div className="metadata-item">
              <label>Updated</label>
              <span>{new Date(asset.updated_at).toLocaleString()}</span>
            </div>
          </div>

          {/* Health score section */}
          <div className="asset-health-score-section" data-testid="asset-health-score-section">
            <h2>Health score</h2>
            {healthScoreLoading ? (
              <p className="asset-health-score-loading">Loading...</p>
            ) : (
              <>
                <div className="asset-health-score-value">
                  {healthScore?.health_score != null ? (
                    <span className="asset-health-score-number">
                      {healthScore.health_score.toFixed(1)}
                    </span>
                  ) : (
                    <span className="asset-health-score-na">N/A</span>
                  )}
                </div>
                {healthScore?.breakdown && (
                  <div className="asset-health-score-breakdown">
                    {healthScore.breakdown.components?.dq && (
                      <div className="breakdown-item">
                        DQ: {healthScore.breakdown.components.dq.score} (×
                        {healthScore.breakdown.components.dq.weight})
                      </div>
                    )}
                    {healthScore.breakdown.components?.compliance && (
                      <div className="breakdown-item">
                        Compliance: {healthScore.breakdown.components.compliance.score}
                      </div>
                    )}
                    {healthScore.breakdown.components?.freshness && (
                      <div className="breakdown-item">
                        Freshness: {healthScore.breakdown.components.freshness.score}
                      </div>
                    )}
                    {healthScore.breakdown.components?.usage && (
                      <div className="breakdown-item">
                        Usage: {healthScore.breakdown.components.usage.score}
                      </div>
                    )}
                  </div>
                )}
                <button
                  type="button"
                  className="btn-secondary btn-small"
                  onClick={async () => {
                    if (!id) return;
                    try {
                      await recalculateHealthScoreMutation.mutateAsync({ id, breakdown: true });
                      refetchHealthScore();
                    } catch {
                      // Error handled by mutation
                    }
                  }}
                  disabled={recalculateHealthScoreMutation.isPending}
                >
                  {recalculateHealthScoreMutation.isPending ? 'Recalculating…' : 'Recalculate'}
                </button>
              </>
            )}
          </div>

          {/* Recommended / Similar assets */}
          {recommendations && recommendations.length > 0 && (
            <div className="asset-recommendations-section">
              <h2>Recommended for you</h2>
              <ul className="asset-recommendations-list">
                {recommendations.map((rec) => (
                  <li key={rec.asset_id}>
                    <a href={`/assets/${rec.asset_id}`}>{rec.asset_name || rec.asset_key}</a>
                    <span className="recommendation-score">{(rec.score * 100).toFixed(0)}%</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>

        <div className="asset-detail-linked">
          <div className="linked-section">
            <h2>Linked Contract</h2>
            {asset.contract_id ? (
              <div className="linked-item">
                <a href={`/contracts/${asset.contract_id}`}>View Contract</a>
              </div>
            ) : (
              <>
                <p className="no-linked">No contract linked</p>
                <div className="attach-controls">
                  <input
                    type="text"
                    value={contractId}
                    onChange={(e) => setContractId(e.target.value)}
                    placeholder="Contract ID"
                    className="attach-input"
                  />
                  <button
                    onClick={handleAttachContract}
                    disabled={!contractId.trim() || attachContractMutation.isPending}
                    className="btn-secondary btn-small"
                    type="button"
                  >
                    {attachContractMutation.isPending ? 'Attaching...' : 'Attach'}
                  </button>
                </div>
              </>
            )}
          </div>

          <div className="linked-section">
            <h2>Linked Dataset</h2>
            {asset.dataset_id ? (
              <div className="linked-item">
                <a href={`/datasets/${asset.dataset_id}`}>View Dataset</a>
              </div>
            ) : (
              <>
                <p className="no-linked">No dataset linked</p>
                <div className="attach-controls">
                  <input
                    type="text"
                    value={datasetId}
                    onChange={(e) => setDatasetId(e.target.value)}
                    placeholder="Dataset ID"
                    className="attach-input"
                  />
                  <button
                    onClick={handleAttachDataset}
                    disabled={!datasetId.trim() || attachDatasetMutation.isPending}
                    className="btn-secondary btn-small"
                    type="button"
                  >
                    {attachDatasetMutation.isPending ? 'Attaching...' : 'Attach'}
                  </button>
                </div>
              </>
            )}
          </div>

          <div className="linked-section">
            <h2>Upload File</h2>
            {!showFileUpload ? (
              <button
                onClick={() => setShowFileUpload(true)}
                className="btn-secondary"
                type="button"
              >
                Upload File
              </button>
            ) : (
              <div className="file-upload-section">
                <FileUpload
                  onUploadComplete={handleFileUploaded}
                  assetId={id}
                  accept=".csv,.json,.parquet"
                />
                <button
                  onClick={() => setShowFileUpload(false)}
                  className="btn-secondary btn-small"
                  type="button"
                >
                  Cancel
                </button>
              </div>
            )}
          </div>

          {/* DQ and Compliance Runs Section */}
          <div className="asset-quality-gates-section">
            <h2>Quality Gates</h2>

            {/* DQ Runs */}
            <div className="quality-gate-subsection">
              <div className="quality-gate-header">
                <h3>Data Quality Runs</h3>
                {asset.dataset_id && (
                  <button
                    onClick={handleRunDQ}
                    disabled={createDQRunMutation.isPending}
                    className="btn-secondary btn-small"
                    type="button"
                  >
                    {createDQRunMutation.isPending ? 'Running...' : 'Run DQ Check'}
                  </button>
                )}
              </div>
              {!asset.dataset_id ? (
                <p className="quality-gate-message">Upload a dataset to run DQ checks</p>
              ) : dqRuns?.results && dqRuns.results.length > 0 ? (
                <div className="quality-gate-runs">
                  {dqRuns.results.slice(0, 3).map((run) => (
                    <div
                      key={run.id}
                      className="quality-gate-run-item"
                      onClick={() => navigate(`/dq/runs/${run.id}`)}
                    >
                      <div className="run-status">
                        <span className={`status-badge status-${run.status.toLowerCase()}`}>
                          {run.status}
                        </span>
                        {run.overall_status && (
                          <span
                            className={`overall-status-badge overall-status-${run.overall_status.toLowerCase()}`}
                          >
                            {run.overall_status}
                          </span>
                        )}
                      </div>
                      <div className="run-details">
                        {run.quality_score !== null && run.quality_score !== undefined && (
                          <span className="quality-score">
                            Score: {Math.round(run.quality_score * 100)}%
                          </span>
                        )}
                        <span className="run-date">
                          {new Date(run.created_at).toLocaleString()}
                        </span>
                      </div>
                    </div>
                  ))}
                  {dqRuns.results.length > 3 && (
                    <button onClick={() => navigate('/dq')} className="btn-link" type="button">
                      View all DQ runs →
                    </button>
                  )}
                </div>
              ) : (
                <p className="quality-gate-message">
                  No DQ runs yet. Click "Run DQ Check" to start.
                </p>
              )}
            </div>

            {/* Compliance Runs */}
            <div className="quality-gate-subsection">
              <div className="quality-gate-header">
                <h3>Compliance Runs</h3>
                {asset.dataset_id && (
                  <button
                    onClick={handleRunCompliance}
                    disabled={createComplianceRunMutation.isPending}
                    className="btn-secondary btn-small"
                    type="button"
                  >
                    {createComplianceRunMutation.isPending ? 'Running...' : 'Run Compliance Check'}
                  </button>
                )}
              </div>
              {!asset.dataset_id ? (
                <p className="quality-gate-message">Upload a dataset to run compliance checks</p>
              ) : complianceRuns?.results && complianceRuns.results.length > 0 ? (
                <div className="quality-gate-runs">
                  {complianceRuns.results.slice(0, 3).map((run) => {
                    const isBlocked = run.allowed_to_store === false;
                    return (
                      <div
                        key={run.id}
                        className={`quality-gate-run-item ${isBlocked ? 'run-blocked' : ''}`}
                        onClick={() => navigate(`/compliance/runs/${run.id}`)}
                      >
                        <div className="run-status">
                          <span className={`status-badge status-${run.status.toLowerCase()}`}>
                            {run.status}
                          </span>
                          {run.overall_status && (
                            <span
                              className={`overall-status-badge overall-status-${run.overall_status.toLowerCase()}`}
                            >
                              {run.overall_status}
                            </span>
                          )}
                          {run.risk_level && (
                            <span
                              className={`risk-level-badge risk-level-${run.risk_level.toLowerCase()}`}
                            >
                              {run.risk_level}
                            </span>
                          )}
                        </div>
                        <div className="run-details">
                          {isBlocked && (
                            <span className="blocked-indicator">⚠️ Storage Blocked</span>
                          )}
                          <span className="run-date">
                            {new Date(run.created_at).toLocaleString()}
                          </span>
                        </div>
                        {isBlocked && (
                          <div className="blocked-message">
                            Fail-closed: Review violations and remediate before retrying
                          </div>
                        )}
                      </div>
                    );
                  })}
                  {complianceRuns.results.length > 3 && (
                    <button
                      onClick={() => navigate('/compliance')}
                      className="btn-link"
                      type="button"
                    >
                      View all compliance runs →
                    </button>
                  )}
                </div>
              ) : (
                <p className="quality-gate-message">
                  No compliance runs yet. Click "Run Compliance Check" to start.
                </p>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

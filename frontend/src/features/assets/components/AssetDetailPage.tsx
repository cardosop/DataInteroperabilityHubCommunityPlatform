/**
 * Asset Detail Page
 * Displays asset details with linked contracts/datasets (plural tables),
 * onboarding checklist for DRAFT assets, activation blocker dialog,
 * and inline DQ/Compliance result summaries.
 */

import { useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useAuthStore } from '../../auth/store/authStore';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { DetailPageSkeleton } from '../../../shared/components/skeletons/DetailPageSkeleton';
import { UuidWithCopy } from '../../../shared/components/UuidWithCopy';
import { Banner } from '../../../shared/components/Banner';
import { Breadcrumbs } from '../../../shared/components/Breadcrumbs';
import { InfoHint } from '../../../shared/components/InfoHint';
import type { File } from '../../../shared/types/files';
import { useComplianceRuns, useCreateComplianceRun } from '../../compliance/hooks/useCompliance';
import { useContracts } from '../../contracts/hooks/useContracts';
import { useCreateDataset, useDatasets } from '../../datasets/hooks/useDatasets';
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
  useRetireAsset,
} from '../hooks/useAssets';
import { ContractAutoValidationBanner } from '../../contracts/components/ContractAutoValidationBanner';
import { ContractPicker, DatasetPicker } from '../../../shared/components/pickers';
import { useToast } from '../../../shared/components/Toast';
import { normalizeError } from '../../../shared/utils/errorUtils';
import { AssetSocialSection } from '../../social/components/AssetSocialSection';
import { ActivityTimeline } from '../../../shared/components/ActivityTimeline';
import { OnboardingChecklist } from './OnboardingChecklist';
import { ActivationBlockerDialog, extractBlockersFromError } from './ActivationBlockerDialog';
import './AssetDetailPage.css';
import { Button } from '../../../shared/components/Button';

export function AssetDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { data: asset, isLoading, error, refetch } = useAsset(id || null);
  const activeTenantId = useAuthStore((s) => s.active_tenant_id);
  const userTenantId = useAuthStore((s) => s.user?.tenant_id);
  const effectiveTenantId = activeTenantId ?? userTenantId;
  const activateMutation = useActivateAsset();
  const retireMutation = useRetireAsset();
  const attachContractMutation = useAttachContract();
  const attachDatasetMutation = useAttachDataset();
  const createDatasetMutation = useCreateDataset();
  const [showFileUpload, setShowFileUpload] = useState(false);
  const [contractId, setContractId] = useState<string | null>(null);
  const [datasetId, setDatasetId] = useState<string | null>(null);
  const [activationBlockers, setActivationBlockers] = useState<string[] | null>(null);
  // Phase 224.3.4 — Details / Activity tab selector (acceptance criteria:
  // "Asset detail → Activity tab → chronological timeline").
  const [activeTab, setActiveTab] = useState<'details' | 'activity'>('details');
  // Last contract attached in this session — drives the one-shot dry-run
  // validation banner below the contracts table.
  const [lastAttachedContractId, setLastAttachedContractId] = useState<
    string | null
  >(null);

  // Fetch all contracts linked to this asset (plural)
  const { data: contractsData } = useContracts(
    id ? { asset_id: id, page_size: 50 } : {},
    { enabled: !!id }
  );
  const linkedContracts = contractsData?.results ?? [];

  // Fetch all datasets linked to this asset (plural)
  const { data: datasetsData } = useDatasets(
    id ? { asset_id: id, page_size: 50 } : {},
    { enabled: !!id }
  );
  const linkedDatasets = datasetsData?.results ?? [];

  // DQ and Compliance runs for this asset
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
  const toast = useToast();

  // Latest DQ run summary
  const latestDQRun = dqRuns?.results?.[0] ?? null;
  // Latest compliance run summary
  const latestComplianceRun = complianceRuns?.results?.[0] ?? null;

  const handleActivate = async () => {
    if (!id || !asset) return;
    setActivationBlockers(null);
    try {
      await activateMutation.mutateAsync({ id, version: asset.version });
      toast.success('Asset activated successfully.');
      refetch();
    } catch (err) {
      const blockers = extractBlockersFromError(err);
      if (blockers) {
        setActivationBlockers(blockers);
      } else {
        toast.error(normalizeError(err).error.message || 'Failed to activate asset');
      }
    }
  };

  const handleRetire = async () => {
    if (!id || !asset) return;
    try {
      await retireMutation.mutateAsync({ id, version: asset.version });
      refetch();
      toast.success('Asset retired successfully.');
    } catch (err) {
      toast.error(normalizeError(err).error.message || 'Failed to retire asset');
    }
  };

  const handleFileUploaded = async (file: File) => {
    if (!id) return;
    try {
      const dataset = await createDatasetMutation.mutateAsync({
        file_id: file.id,
        asset_id: id,
      });
      await attachDatasetMutation.mutateAsync({ id, data: { dataset_id: dataset.id } });
      setShowFileUpload(false);
      toast.success('Dataset created and linked successfully.');
    } catch (err) {
      toast.error(normalizeError(err).error.message || 'Upload failed. See details below.');
    }
  };

  const handleAttachContract = async () => {
    if (!id || !contractId) return;
    try {
      await attachContractMutation.mutateAsync({ id, data: { contract_id: contractId } });
      // Trigger the one-shot dry-run validation banner for this contract.
      // The hook's ref-guard prevents re-validation on subsequent renders.
      setLastAttachedContractId(contractId);
      setContractId(null);
      refetch();
      toast.success('Contract attached successfully.');
    } catch (err) {
      toast.error(normalizeError(err).error.message || 'Failed to attach contract');
    }
  };

  const handleAttachDataset = async () => {
    if (!id || !datasetId) return;
    try {
      await attachDatasetMutation.mutateAsync({ id, data: { dataset_id: datasetId } });
      setDatasetId(null);
      refetch();
      toast.success('Dataset attached successfully.');
    } catch (err) {
      toast.error(normalizeError(err).error.message || 'Failed to attach dataset');
    }
  };

  const handleRunDQ = async () => {
    if (!id) return;
    try {
      await createDQRunMutation.mutateAsync({
        asset_id: id,
        dataset_id: asset?.dataset_id,
      });
      toast.success('DQ run started.');
    } catch (err) {
      toast.error(normalizeError(err).error.message || 'Failed to start DQ run');
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
      toast.success('Compliance run started.');
    } catch (err) {
      toast.error(normalizeError(err).error.message || 'Failed to start compliance run');
    }
  };

  if (isLoading) {
    return <DetailPageSkeleton />;
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

  // Tenant isolation
  if (
    effectiveTenantId &&
    asset.tenant &&
    asset.tenant !== effectiveTenantId &&
    asset.visibility !== 'PUBLIC'
  ) {
    return (
      <ErrorDisplay
        error={new Error('Asset not found')}
        title="Asset not found"
      />
    );
  }

  const canActivate = asset.status === 'DRAFT';
  const canRetire = asset.status === 'ACTIVE';
  const isDraft = asset.status === 'DRAFT';

  return (
    <div className="asset-detail-page">
      <div className="asset-detail-header">
        <Button onClick={() => navigate('/assets')} variant="ghost">
          &larr; Back to Assets
        </Button>
        <div className="asset-detail-actions">
          {canActivate && (
            <Button
              onClick={handleActivate}
              loading={activateMutation.isPending}
              variant="primary"
              data-testid="btn-activate-asset">
              Activate Asset
            </Button>
          )}
          {canRetire && (
            <Button
              onClick={handleRetire}
              loading={retireMutation.isPending}
              variant="secondary"
              data-testid="btn-retire-asset">
              Retire Asset
            </Button>
          )}
        </div>
      </div>

      {/* Activation Blocker Dialog */}
      {activationBlockers && id && (
        <ActivationBlockerDialog
          blockers={activationBlockers}
          assetId={id}
          onDismiss={() => setActivationBlockers(null)}
        />
      )}

      <div className="asset-detail-content">
        <Breadcrumbs
          items={[
            { label: 'Home', href: '/' },
            { label: 'Assets', href: '/assets' },
            { label: asset.name || 'Asset' },
          ]}
        />
        {isDraft && (
          <div className="asset-draft-banner" data-testid="asset-draft-banner">
            <Banner variant="info">
              This asset is in <strong>DRAFT</strong>. Complete the steps below to activate it.
            </Banner>
          </div>
        )}

        {/* Phase 224.3.4 — Details / Activity tabs. */}
        <div
          className="asset-detail-tabs"
          role="tablist"
          aria-label="Asset sections"
        >
          <button
            type="button"
            role="tab"
            aria-selected={activeTab === 'details'}
            className={`asset-detail-tab ${activeTab === 'details' ? 'active' : ''}`}
            onClick={() => setActiveTab('details')}
            data-testid="asset-tab-details"
          >
            Details
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={activeTab === 'activity'}
            className={`asset-detail-tab ${activeTab === 'activity' ? 'active' : ''}`}
            onClick={() => setActiveTab('activity')}
            data-testid="asset-tab-activity"
          >
            Activity
          </button>
        </div>

        {activeTab === 'activity' && id && (
          <div className="asset-detail-main" data-testid="asset-activity">
            <ActivityTimeline resourceType="ASSET" resourceId={id} />
          </div>
        )}

        <div
          className="asset-detail-main"
          hidden={activeTab !== 'details'}
          data-testid="asset-details-tabpanel"
        >
          <h1>{asset.name}</h1>
          <p className="asset-key">
            Key: <code>{asset.key}</code>
          </p>
          {id && (
            <div className="asset-uuid" data-testid="asset-uuid">
              <UuidWithCopy value={id} label="Asset ID" />
            </div>
          )}
          {asset.description && <p className="asset-description">{asset.description}</p>}

          <div className="asset-detail-metadata">
            <div className="metadata-item">
              <label>
                Status
                <InfoHint
                  label="About asset Activation lifecycle"
                  content="Assets move DRAFT → ACTIVE → RETIRED. Only ACTIVE assets are visible to consumers, eligible for marketplace listings, and participate in lineage. Activation requires passing the onboarding checklist (schema registered, contract bound, DQ baseline)."
                />
              </label>
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

          {/* Onboarding Checklist for DRAFT assets */}
          {isDraft && (
            <OnboardingChecklist
              contracts={linkedContracts}
              datasets={linkedDatasets}
              dqStatus={asset.dq_status}
              complianceStatus={asset.compliance_status}
              assetId={id}
              onRunDQ={handleRunDQ}
              onRunCompliance={handleRunCompliance}
              onActivate={handleActivate}
              isActivating={activateMutation.isPending}
            />
          )}

          {/* Inline DQ Result Summary */}
          <div className="asset-inline-summary" data-testid="asset-dq-summary">
            <div className="inline-summary-header">
              <h3>Latest DQ Result</h3>
              {latestDQRun && (
                <button
                  type="button"
                  className="btn-link"
                  onClick={() => navigate(`/dq/runs/${latestDQRun.id}`)}
                >
                  View Details &rarr;
                </button>
              )}
            </div>
            {latestDQRun ? (
              <div className="inline-summary-body">
                <span className={`status-badge status-${latestDQRun.status.toLowerCase()}`}>
                  {latestDQRun.status}
                </span>
                {latestDQRun.quality_score != null && (
                  <span className="inline-summary-score">
                    Score: {Math.round(latestDQRun.quality_score * 100)}%
                  </span>
                )}
                {latestDQRun.overall_status && (
                  <span
                    className={`overall-status-badge overall-status-${latestDQRun.overall_status.toLowerCase()}`}
                  >
                    {latestDQRun.overall_status}
                  </span>
                )}
              </div>
            ) : (
              <p className="inline-summary-empty">No DQ runs yet.</p>
            )}
          </div>

          {/* Inline Compliance Result Summary */}
          <div className="asset-inline-summary" data-testid="asset-compliance-summary">
            <div className="inline-summary-header">
              <h3>Latest Compliance Result</h3>
              {latestComplianceRun && (
                <button
                  type="button"
                  className="btn-link"
                  onClick={() => navigate(`/compliance/runs/${latestComplianceRun.id}`)}
                >
                  View Details &rarr;
                </button>
              )}
            </div>
            {latestComplianceRun ? (
              <div className="inline-summary-body">
                <span className={`status-badge status-${latestComplianceRun.status.toLowerCase()}`}>
                  {latestComplianceRun.status}
                </span>
                {latestComplianceRun.overall_status && (
                  <span
                    className={`overall-status-badge overall-status-${latestComplianceRun.overall_status.toLowerCase()}`}
                  >
                    {latestComplianceRun.overall_status}
                  </span>
                )}
                {latestComplianceRun.risk_level && (
                  <span
                    className={`risk-level-badge risk-level-${latestComplianceRun.risk_level.toLowerCase()}`}
                  >
                    {latestComplianceRun.risk_level}
                  </span>
                )}
                {latestComplianceRun.allowed_to_store === false && (
                  <span className="blocked-indicator">Storage Blocked</span>
                )}
              </div>
            ) : (
              <p className="inline-summary-empty">No compliance runs yet.</p>
            )}
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
                        DQ: {healthScore.breakdown.components.dq.score} (&times;
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
                <Button
                  variant="secondary" className="btn-small"
                  onClick={async () => {
                    if (!id) return;
                    try {
                      await recalculateHealthScoreMutation.mutateAsync({ id, breakdown: true });
                      refetchHealthScore();
                    } catch {
                      // Error handled by mutation
                    }
                  }}
                  loading={recalculateHealthScoreMutation.isPending}>
                  Recalculate
                </Button>
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

          {/* Social section: Ratings, Reviews, Comments (capability-gated) */}
          {id && <AssetSocialSection assetId={id} />}
        </div>

        <div className="asset-detail-linked">
          {/* Linked Contracts (plural table) */}
          <div className="linked-section" data-testid="asset-contracts-section">
            <h2>Linked Contracts ({linkedContracts.length})</h2>
            {linkedContracts.length > 0 ? (
              <table className="linked-table" data-testid="contracts-table">
                <thead>
                  <tr>
                    <th>Name</th>
                    <th>Format</th>
                    <th>Normalization</th>
                    <th>Validation</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {linkedContracts.map((c) => (
                    <tr key={c.id} data-testid={`contract-row-${c.id}`}>
                      <td>{c.name || 'Unnamed'}</td>
                      <td>{c.original_format ?? '\u2014'}</td>
                      <td>
                        <span className={`status-badge status-${(c.normalization_status ?? '').toLowerCase().replace('_', '-')}`}>
                          {c.normalization_status ?? '\u2014'}
                        </span>
                      </td>
                      <td>
                        <span className={`validation-badge validation-${(c.validation_status ?? '').toLowerCase()}`}>
                          {c.validation_status ?? '\u2014'}
                        </span>
                      </td>
                      <td>
                        <button
                          type="button"
                          className="btn-link"
                          onClick={() => navigate(`/contracts/${c.id}`)}
                        >
                          View
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <p className="no-linked">No contracts linked</p>
            )}
            {/* 222.5 — inline dry-run validation feedback for the contract
                that was just attached in this session. Suspends when null. */}
            {lastAttachedContractId && (
              <ContractAutoValidationBanner
                contract={
                  linkedContracts.find((c) => c.id === lastAttachedContractId) ?? null
                }
              />
            )}
            <div className="attach-controls">
              <ContractPicker
                value={contractId}
                onChange={setContractId}
                placeholder="Search and select a contract..."
                data-testid="asset-attach-contract-picker"
              />
              <Button
                onClick={handleAttachContract}
                disabled={!contractId || attachContractMutation.isPending}
                variant="secondary" className="btn-small">
                {attachContractMutation.isPending ? 'Attaching...' : 'Attach'}
              </Button>
            </div>
          </div>

          {/* Linked Datasets (plural table) */}
          <div className="linked-section" data-testid="asset-datasets-section">
            <h2>Linked Datasets ({linkedDatasets.length})</h2>
            <table className="linked-table" data-testid="datasets-table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Format</th>
                  <th>Rows</th>
                  <th>Size</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {linkedDatasets.length > 0 ? (
                  linkedDatasets.map((d) => (
                    <tr key={d.id} data-testid={`dataset-row-${d.id}`}>
                      <td>{d.name || 'Unnamed'}</td>
                      <td>{d.format}</td>
                      <td>{d.row_count ?? '\u2014'}</td>
                      <td>{d.size_bytes != null ? formatBytes(d.size_bytes) : '\u2014'}</td>
                      <td>
                        <button
                          type="button"
                          className="btn-link"
                          onClick={() => navigate(`/datasets/${d.id}`)}
                        >
                          View
                        </button>
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={5} className="no-linked-cell">
                      No datasets linked
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
            <div className="attach-controls">
              <DatasetPicker
                value={datasetId}
                onChange={setDatasetId}
                placeholder="Search and select a dataset..."
                data-testid="asset-attach-dataset-picker"
              />
              <Button
                onClick={handleAttachDataset}
                disabled={!datasetId || attachDatasetMutation.isPending}
                variant="secondary" className="btn-small">
                {attachDatasetMutation.isPending ? 'Attaching...' : 'Attach'}
              </Button>
            </div>
          </div>

          {/* Upload File */}
          <div className="linked-section" data-testid="asset-upload-section">
            <h2>Upload File</h2>
            {(createDatasetMutation.isError || attachDatasetMutation.isError) && (
              <ErrorDisplay
                error={createDatasetMutation.error || attachDatasetMutation.error}
                title="Upload failed"
                onRetry={() => {
                  createDatasetMutation.reset();
                  attachDatasetMutation.reset();
                }}
              />
            )}
            {!showFileUpload ? (
              <Button
                onClick={() => setShowFileUpload(true)}
                variant="secondary">
                Upload File
              </Button>
            ) : (
              <div className="file-upload-section">
                <FileUpload
                  onUploadComplete={handleFileUploaded}
                  assetId={id}
                  accept=".csv,.json,.parquet"
                />
                <Button
                  onClick={() => setShowFileUpload(false)}
                  variant="secondary" className="btn-small">
                  Cancel
                </Button>
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
                  <Button
                    onClick={handleRunDQ}
                    disabled={
                      createDQRunMutation.isPending ||
                      createDatasetMutation.isPending ||
                      attachDatasetMutation.isPending
                    }
                    variant="secondary" className="btn-small">
                    {createDQRunMutation.isPending ? 'Running...' : 'Run DQ Check'}
                  </Button>
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
                      View all DQ runs &rarr;
                    </button>
                  )}
                </div>
              ) : (
                <p className="quality-gate-message">
                  No DQ runs yet. Click &quot;Run DQ Check&quot; to start.
                </p>
              )}
            </div>

            {/* Compliance Runs */}
            <div className="quality-gate-subsection">
              <div className="quality-gate-header">
                <h3>Compliance Runs</h3>
                {asset.dataset_id && (
                  <Button
                    onClick={handleRunCompliance}
                    disabled={
                      createComplianceRunMutation.isPending ||
                      createDatasetMutation.isPending ||
                      attachDatasetMutation.isPending
                    }
                    variant="secondary" className="btn-small">
                    {createComplianceRunMutation.isPending ? 'Running...' : 'Run Compliance Check'}
                  </Button>
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
                            <span className="blocked-indicator">Storage Blocked</span>
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
                      View all compliance runs &rarr;
                    </button>
                  )}
                </div>
              ) : (
                <p className="quality-gate-message">
                  No compliance runs yet. Click &quot;Run Compliance Check&quot; to start.
                </p>
              )}
            </div>
          </div>

        </div>
      </div>
    </div>
  );
}

function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
}

/**
 * Contract Detail Page
 * Display contract details with operations and lineage (real API; no stub data).
 */

import { useParams, useNavigate } from 'react-router-dom';
import { useState } from 'react';
import { useContract, useUpdateContract, useValidateContract, useLintContract, useConvertContract, useExportContract, useDownloadContract, useContractLinks } from '../hooks/useContracts';
import { AssetPicker } from '../../../shared/components/pickers';
import { ContractLineageVisualization } from '../../lineage/components/ContractLineageVisualization';
import { ActivityTimeline } from '../../../shared/components/ActivityTimeline';
import { LineageSubscriptionPanel } from './LineageSubscriptionPanel';
import { RelationshipsPanel } from './RelationshipsPanel';
import type {
  ContractRelationship,
  ContractSchemaObject,
} from '../../../shared/types/contracts';
import { ContractUsedByAssets } from './ContractUsedByAssets';
import { CanonicalIriCard } from '../../semantic/components/CanonicalIriCard';
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
import { InfoHint } from '../../../shared/components/InfoHint';
import './ContractDetailPage.css';
import { Button } from '../../../shared/components/Button';
import { useCapabilities } from '../../../shared/hooks/useCapabilities';

type ContractDetailTab = 'details' | 'lineage' | 'activity';

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
  const isODPSOrODCS = contract?.original_spec_type === 'ODPS' || contract?.original_spec_type === 'ODCS';
  const { data: links } = useContractLinks(isODPSOrODCS ? (id || null) : null);
  const [validationResult, setValidationResult] = useState<ContractValidationResult | null>(null);
  const [lintResult, setLintResult] = useState<ContractLintResult | null>(null);
  const [convertResult, setConvertResult] = useState<ContractConvertResult | null>(null);
  const [linkAssetId, setLinkAssetId] = useState<string | null>(null);
  const updateContract = useUpdateContract();

  const handleLinkAsset = async () => {
    if (!id || !linkAssetId) return;
    try {
      await updateContract.mutateAsync({ id, data: { asset_id: linkAssetId } as never });
      setLinkAssetId(null);
    } catch {
      // Mutation shows toast automatically
    }
  };

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
    // Phase 226.F1.b — testid for stable e2e selector.
    <div className="contract-detail-page" data-testid="contract-detail-page">
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
          {contract.original_spec_type === 'ODPS' && (
            <Button onClick={() => navigate(`/contracts/${id}/link-odps`)} variant="secondary">
              Link ODCS
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
        <button
          type="button"
          role="tab"
          aria-selected={activeTab === 'activity'}
          className={`contract-detail-tab ${activeTab === 'activity' ? 'active' : ''}`}
          onClick={() => setActiveTab('activity')}
          data-testid="contract-tab-activity"
        >
          Activity
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
            <>
              {/* Phase 228.F2.32 — Edit lineage button (capability-flag gated). */}
              <LineageEditEntrypoint contractId={id} />
              {/* Phase 228.F3.13 (REQ-LIN-F3-006) — Subscribe-to-lineage-changes
                  button (capability-flag gated by lineage.change_notifications). */}
              <LineageSubscriptionPanel sourceContractId={id} />
              <ContractLineageVisualization contractId={id} maxDepth={10} />
            </>
          ) : activeTab === 'activity' && id ? (
            <section data-testid="contract-activity">
              <h2>Activity</h2>
              <ActivityTimeline resourceType="CONTRACT" resourceId={id} />
            </section>
          ) : (
            <>
          <h1>{contract.name || 'Unnamed Contract'}</h1>
          {id && (
            <div className="contract-uuid" data-testid="contract-uuid">
              <UuidWithCopy value={id} label="Contract ID" />
            </div>
          )}
          {contract.description && <p className="contract-description">{contract.description}</p>}

          {/* Phase 230.1.5 — surfaced canonical IRI per REQ-SEM-DISCO-001. */}
          {id && (
            <CanonicalIriCard
              iri={contract.canonical_iri}
              resourceType="contract"
              resourceId={id}
            />
          )}

          <div className="contract-detail-metadata">
            {contract.original_spec_type && (
              <div className="metadata-item">
                <label>
                  Spec Type
                  <InfoHint
                    label="About Spec Type"
                    content="The original machine-readable format the contract was authored in (e.g. ODPS, ODCS, OpenAPI, JSON Schema). Meshant normalises each spec type into a common internal contract model so lineage and validation work uniformly across formats."
                  />
                </label>
                <span className={`spec-type-badge spec-type-badge--${contract.original_spec_type.toLowerCase()}`}>
                  {contract.original_spec_type}
                </span>
              </div>
            )}
            <div className="metadata-item">
              <label>Format</label>
              <span>{contract.original_format ?? '—'}</span>
            </div>
            <div className="metadata-item">
              <label>
                Normalization Status
                <InfoHint
                  label="About Normalization Status"
                  content="Tracks whether this contract has been successfully normalised into Meshant's internal canonical form. PENDING → queued; IN_PROGRESS → being converted; SUCCESS → usable for validation and lineage; FAILED → see logs. Contracts must be SUCCESS before lineage edges or DQ checks will bind."
                />
              </label>
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

          {id && <ContractUsedByAssets contractId={id} />}

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

          {/* Link to Asset section (when no asset linked) */}
          {!linkedAssetId && (
            <div className="contract-link-asset" data-testid="contract-link-asset">
              <h2>Link to Asset</h2>
              <div className="link-asset-form">
                <AssetPicker
                  value={linkAssetId}
                  onChange={setLinkAssetId}
                  placeholder="Search and select an asset..."
                  data-testid="contract-asset-picker"
                />
                <Button
                  variant="primary"
                  onClick={handleLinkAsset}
                  disabled={!linkAssetId || updateContract.isPending}
                >
                  {updateContract.isPending ? 'Linking...' : 'Link Asset'}
                </Button>
              </div>
            </div>
          )}

          {/* Linked Contracts section (ODPS ↔ ODCS) */}
          {links && (links.odps_link || links.odcs_link) && (
            <div className="contract-linked-contracts" data-testid="contract-linked-contracts">
              <h2>Linked Contracts</h2>
              {links.odcs_link && (
                <div className="linked-contract-row">
                  <span className="spec-type-badge spec-type-badge--odcs">ODCS</span>
                  <strong>{links.odcs_link.name || 'Unnamed'}</strong>
                  <button
                    type="button"
                    className="btn-link"
                    onClick={() => navigate(`/contracts/${links.odcs_link!.id}`)}
                  >
                    View
                  </button>
                </div>
              )}
              {links.odps_link && (
                <div className="linked-contract-row">
                  <span className="spec-type-badge spec-type-badge--odps">ODPS</span>
                  <strong>{links.odps_link.name || 'Unnamed'}</strong>
                  <button
                    type="button"
                    className="btn-link"
                    onClick={() => navigate(`/contracts/${links.odps_link!.id}`)}
                  >
                    View
                  </button>
                </div>
              )}
            </div>
          )}

          {/* Phase 230.5.6 (REQ-SEM-RELATIONSHIPS-001) — surface
              both structural relationships (from hub_contract_json)
              and the RDF triples returned by the semantic-service
              relationships endpoint.  ``contractId`` enables the
              second fetch; without it the panel only shows
              structural data. */}
          {id && (
            <RelationshipsPanel
              models={(contract as { hub_contract_json?: { models?: ContractSchemaObject[] } }).hub_contract_json?.models}
              schemaRelationships={(contract as { hub_contract_json?: { schema?: { relationships?: ContractRelationship[] } } }).hub_contract_json?.schema?.relationships}
              specVersion={contract.original_spec_version}
              contractId={id}
            />
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

/**
 * Phase 228.F2.32 — Edit-lineage entry-point.  Capability-gated via
 * `useCapabilities()`; renders nothing while the capability resolves
 * (no flicker).  When the capability is not registered (the F2 build
 * isn't compiled in), the button is hidden and the current
 * read-only lineage tab is the only surface.
 */
function LineageEditEntrypoint({ contractId }: { contractId: string }) {
  const { isCapabilityAvailable, isLoading } = useCapabilities();
  const navigate = useNavigate();
  if (isLoading) return null;
  if (!isCapabilityAvailable('contracts.lineage_field_editor')) {
    return null;
  }
  return (
    <div className="lineage-edit-entrypoint" data-testid="lineage-edit-entrypoint">
      <Button
        variant="secondary"
        onClick={() => navigate(`/contracts/${contractId}/lineage/edit`)}
      >
        Edit lineage
      </Button>
    </div>
  );
}

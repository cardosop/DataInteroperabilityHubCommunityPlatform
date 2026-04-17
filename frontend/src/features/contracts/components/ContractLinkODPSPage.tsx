/**
 * ContractLinkODPSPage — Link ODPS ↔ ODCS contracts.
 * Moved from features/odps/components/ODPSLinkPage.tsx (Phase 211.A7).
 */

import { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useContract, useLinkODPS, useUnlinkODPS, useContractLinks } from '../hooks/useContracts';
import { ContractPicker } from '../../../shared/components/pickers';
import { ConfirmDialog } from '../../../shared/components/ConfirmDialog';
import { LoadingSpinner } from '../../../shared/components/LoadingSpinner';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { useToast } from '../../../shared/components/Toast';
import { normalizeError } from '../../../shared/utils/errorUtils';
import { Breadcrumbs } from '../../../shared/components/Breadcrumbs';
import { ContractFormat } from '../../../shared/types/contracts';
import { UuidWithCopy } from '../../../shared/components/UuidWithCopy';
import { Button } from '../../../shared/components/Button';
import { ODPSProductForm, makeEmptyODPSFormData } from './ODPSProductForm';
import { buildODPSDocument } from '../utils/odpsDocumentBuilder';
import type { ODPSFormData } from '../../../shared/types/odps';
import './ContractLinkODPSPage.css';

export function ContractLinkODPSPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { data: contract, isLoading: contractLoading } = useContract(id || null);
  const { data: links, isLoading: linksLoading, refetch: refetchLinks } = useContractLinks(id || null);
  const linkMutation = useLinkODPS();
  const unlinkMutation = useUnlinkODPS();

  // Determine if this is an ODCS or ODPS contract
  const isODCS = contract?.original_spec_type === 'ODCS';
  const isODPS = contract?.original_spec_type === 'ODPS';
  
  // If ODPS, get the linked ODCS contract ID
  const odcsContractId = isODPS && links?.odcs_link ? links.odcs_link.id : (isODCS ? id : null);

  const [linkMode, setLinkMode] = useState<'existing' | 'create'>('existing');
  const [odpsContractId, setOdpsContractId] = useState<string | null>(null);
  const [odpsContent, setOdpsContent] = useState('');
  const [format, setFormat] = useState<ContractFormat>(ContractFormat.JSON);
  const [resolveExternalRefs, setResolveExternalRefs] = useState(true);
  // Guided ODPS form state for "create" mode
  const [odpsFormData, setOdpsFormData] = useState<ODPSFormData>(() => makeEmptyODPSFormData());
  const [showUnlinkConfirm, setShowUnlinkConfirm] = useState(false);
  const toast = useToast();

  const handleLink = async () => {
    if (!odcsContractId) return;

    try {
      if (linkMode === 'existing') {
        if (!odpsContractId) {
          toast.error('Please select an ODPS contract');
          return;
        }
        await linkMutation.mutateAsync({
          odcsContractId: odcsContractId,
          data: { odps_contract_id: odpsContractId },
        });
      } else {
        // "Create and Link" mode — serialize from guided form OR raw content
        let rawContent = odpsContent;
        if (!rawContent.trim()) {
          // No raw paste — try building from guided form
          try {
            rawContent = buildODPSDocument(odpsFormData, format === ContractFormat.YAML ? 'YAML' : 'JSON');
          } catch {
            toast.error('Please fill in the ODPS product details or paste content');
            return;
          }
          if (!rawContent.trim()) {
            toast.error('Please fill in the ODPS product details or paste content');
            return;
          }
        }
        await linkMutation.mutateAsync({
          odcsContractId: odcsContractId,
          data: {
            original_raw: rawContent,
            original_format: format,
            resolve_external_refs: resolveExternalRefs,
          },
        });
      }
      refetchLinks();
      toast.success('ODPS contract linked successfully.');
    } catch (error) {
      toast.error(normalizeError(error).error.message || 'Failed to link ODPS contract');
    }
  };

  const handleUnlinkClick = () => setShowUnlinkConfirm(true);
  const handleUnlinkConfirm = async () => {
    if (!odcsContractId) return;
    setShowUnlinkConfirm(false);
    try {
      await unlinkMutation.mutateAsync(odcsContractId);
      refetchLinks();
      toast.success('ODPS contract unlinked successfully.');
    } catch (err) {
      toast.error(normalizeError(err).error.message || 'Failed to unlink ODPS contract');
    }
  };

  if (contractLoading || linksLoading) {
    // Show error immediately if contract fetch completed with no data while links still loading
    if (!contractLoading && !contract) {
      return <ErrorDisplay error={new Error('Contract not found')} title="Failed to load contract" />;
    }
    return <LoadingSpinner message="Loading contract..." />;
  }

  if (!contract) {
    return <ErrorDisplay error={new Error('Contract not found')} title="Failed to load contract" />;
  }

  // If ODPS contract, redirect to linked ODCS or show message
  if (isODPS && !odcsContractId) {
    return (
      <div className="odps-link-page">
        <div className="error-message">
          <h2>No Linked ODCS Contract</h2>
          <p>This ODPS contract is not linked to an ODCS contract. To link contracts, navigate to the ODCS contract page and use the "Link ODPS" button.</p>
          <Button onClick={() => navigate(`/contracts/${id}`)} variant="primary">
            Back to ODPS Contract
          </Button>
        </div>
      </div>
    );
  }

  // Verify we have an ODCS contract to link from
  if (!isODCS && !odcsContractId) {
    return (
      <div className="odps-link-page">
        <div className="error-message">
          <h2>Invalid Contract Type</h2>
          <p>This contract is not an ODCS contract. Only ODCS contracts can be linked to ODPS contracts.</p>
          <Button onClick={() => navigate(`/contracts/${id}`)} variant="primary">
            Back to Contract
          </Button>
        </div>
      </div>
    );
  }

  const hasODPSLink = links?.odps_link !== null;

  return (
    <div className="odps-link-page">
      <Breadcrumbs
        items={[
          { label: 'Home', href: '/' },
          { label: 'Contracts', href: '/contracts' },
          { label: contract.name || 'Contract', href: id ? `/contracts/${id}` : undefined },
          { label: 'Link ODPS' },
        ]}
      />
      <div className="odps-link-header">
        <Button onClick={() => navigate(`/contracts/${id}`)} variant="ghost">
          ← Back to Contract
        </Button>
        <h1>Link ODPS to ODCS Contract</h1>
      </div>

      <div className="odps-link-content">
        <div className="contract-info">
          <h2>{isODPS ? 'ODPS Contract' : 'ODCS Contract'}</h2>
          <div className="contract-id-with-copy">
            <UuidWithCopy value={contract.id} label={isODPS ? 'ODPS Contract ID' : 'ODCS Contract ID'} />
          </div>
          <p>
            <strong>Name:</strong> {contract.name || 'Unnamed'}
          </p>
          <p>
            <strong>Status:</strong> {contract.normalization_status}
          </p>
          {isODPS && odcsContractId && (
            <div className="linked-odcs-info">
              <UuidWithCopy value={odcsContractId} label="Linked ODCS Contract ID" />
            </div>
          )}
        </div>

        {hasODPSLink ? (
          <div className="existing-link">
            <h2>Linked ODPS Contract</h2>
            <div className="linked-contract">
              <div className="linked-contract-id">
                <UuidWithCopy value={links!.odps_link!.id} label="ODPS Contract ID" />
                <button
                  onClick={() => navigate(`/contracts/${links!.odps_link!.id}`)}
                  className="btn-link"
                  type="button"
                >
                  View
                </button>
              </div>
              <p>
                <strong>Name:</strong> {links!.odps_link!.name || 'Unnamed'}
              </p>
              <p>
                <strong>Status:</strong> {links!.odps_link!.normalization_status}
              </p>
            </div>
            <Button onClick={handleUnlinkClick} loading={unlinkMutation.isPending} variant="danger">
              Unlink ODPS Contract
            </Button>
          </div>
        ) : (
          <div className="link-form">
            <h2>Link ODPS Contract</h2>
            <div className="link-mode-selector">
              <button
                onClick={() => setLinkMode('existing')}
                className={linkMode === 'existing' ? 'active' : ''}
                type="button"
              >
                Link Existing ODPS
              </button>
              <button
                onClick={() => setLinkMode('create')}
                className={linkMode === 'create' ? 'active' : ''}
                type="button"
              >
                Create and Link New ODPS
              </button>
            </div>

            {linkMode === 'existing' ? (
              <div className="form-section">
                <label htmlFor="odps-contract-picker">ODPS Contract</label>
                <ContractPicker
                  value={odpsContractId}
                  onChange={setOdpsContractId}
                  placeholder="Search and select an ODPS contract..."
                  specType="ODPS"
                  data-testid="odps-link-contract-picker"
                />
              </div>
            ) : (
              <div className="form-section odps-guided-create">
                <ODPSProductForm value={odpsFormData} onChange={setOdpsFormData} />

                <div className="form-section">
                  <label htmlFor="odps-format">Output Format</label>
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
                  <label>
                    <input
                      type="checkbox"
                      checked={resolveExternalRefs}
                      onChange={(e) => setResolveExternalRefs(e.target.checked)}
                    />
                    Resolve external $ref references
                  </label>
                </div>
              </div>
            )}

            <div className="form-actions">
              <Button
 onClick={handleLink}
 disabled={linkMutation.isPending || (linkMode === 'existing' && !odpsContractId)}
 variant="primary">
                {linkMutation.isPending ? 'Linking...' : 'Link ODPS Contract'}
              </Button>
            </div>

            {linkMutation.isError && (
              <ErrorDisplay
                error={linkMutation.error}
                title="Failed to link ODPS contract"
                onRetry={() => linkMutation.reset()}
              />
            )}

            {unlinkMutation.isError && (
              <ErrorDisplay
                error={unlinkMutation.error}
                title="Failed to unlink ODPS contract"
                onRetry={() => unlinkMutation.reset()}
              />
            )}
          </div>
        )}

      <ConfirmDialog
        isOpen={showUnlinkConfirm}
        onClose={() => setShowUnlinkConfirm(false)}
        onConfirm={handleUnlinkConfirm}
        title="Unlink ODPS contract"
        message="Are you sure you want to unlink the ODPS contract?"
        confirmLabel="Unlink"
        variant="warning"
      />
      </div>
    </div>
  );
}

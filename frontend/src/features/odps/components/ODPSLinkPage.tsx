/**
 * ODPS Link Page
 * Link ODPS ↔ ODCS contracts
 */

import { useState, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useContract } from '../../contracts/hooks/useContracts';
import { useLinkODPS, useUnlinkODPS, useODPSLinks } from '../hooks/useODPS';
import { LoadingSpinner } from '../../../shared/components/LoadingSpinner';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { ContractFormat } from '../../../shared/types/contracts';
import './ODPSLinkPage.css';

export function ODPSLinkPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { data: contract, isLoading: contractLoading } = useContract(id || null);
  const { data: links, isLoading: linksLoading, refetch: refetchLinks } = useODPSLinks(id || null);
  const linkMutation = useLinkODPS();
  const unlinkMutation = useUnlinkODPS();

  // Determine if this is an ODCS or ODPS contract
  const isODCS = contract?.original_spec_type === 'ODCS';
  const isODPS = contract?.original_spec_type === 'ODPS';
  
  // If ODPS, get the linked ODCS contract ID
  const odcsContractId = isODPS && links?.odcs_link ? links.odcs_link.id : (isODCS ? id : null);

  const [linkMode, setLinkMode] = useState<'existing' | 'create'>('existing');
  const [odpsContractId, setOdpsContractId] = useState('');
  const [odpsContent, setOdpsContent] = useState('');
  const [format, setFormat] = useState<ContractFormat>(ContractFormat.JSON);
  const [resolveExternalRefs, setResolveExternalRefs] = useState(true);
  const fileInputRef = useRef<HTMLInputElement>(null);

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

  const handleLink = async () => {
    if (!odcsContractId) return;

    try {
      if (linkMode === 'existing') {
        if (!odpsContractId.trim()) {
          alert('Please provide ODPS contract ID');
          return;
        }
        await linkMutation.mutateAsync({
          odcsContractId: odcsContractId,
          data: { odps_contract_id: odpsContractId },
        });
      } else {
        if (!odpsContent.trim()) {
          alert('Please provide ODPS content');
          return;
        }
        await linkMutation.mutateAsync({
          odcsContractId: odcsContractId,
          data: {
            original_raw: odpsContent,
            original_format: format,
            resolve_external_refs: resolveExternalRefs,
          },
        });
      }
      refetchLinks();
      alert('ODPS contract linked successfully!');
    } catch (error) {
      console.error('Failed to link ODPS:', error);
    }
  };

  const handleUnlink = async () => {
    if (!odcsContractId || !confirm('Are you sure you want to unlink the ODPS contract?')) return;

    try {
      await unlinkMutation.mutateAsync(odcsContractId);
      refetchLinks();
      alert('ODPS contract unlinked successfully!');
    } catch (error) {
      console.error('Failed to unlink ODPS:', error);
    }
  };

  if (contractLoading || linksLoading) {
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
          <button onClick={() => navigate(`/odps/${id}`)} className="btn-primary" type="button">
            Back to ODPS Contract
          </button>
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
          <button onClick={() => navigate(isODPS ? `/odps/${id}` : `/contracts/${id}`)} className="btn-primary" type="button">
            Back to Contract
          </button>
        </div>
      </div>
    );
  }

  const hasODPSLink = links?.odps_link !== null;

  return (
    <div className="odps-link-page">
      <div className="odps-link-header">
        <button onClick={() => navigate(isODPS ? `/odps/${id}` : `/contracts/${id}`)} className="btn-back" type="button">
          ← Back to Contract
        </button>
        <h1>Link ODPS to ODCS Contract</h1>
      </div>

      <div className="odps-link-content">
        <div className="contract-info">
          <h2>{isODPS ? 'ODPS Contract' : 'ODCS Contract'}</h2>
          <p>
            <strong>ID:</strong> {contract.id}
          </p>
          <p>
            <strong>Name:</strong> {contract.name || 'Unnamed'}
          </p>
          <p>
            <strong>Status:</strong> {contract.normalization_status}
          </p>
          {isODPS && odcsContractId && (
            <div className="linked-odcs-info">
              <p>
                <strong>Linked ODCS Contract ID:</strong> {odcsContractId}
              </p>
            </div>
          )}
        </div>

        {hasODPSLink ? (
          <div className="existing-link">
            <h2>Linked ODPS Contract</h2>
            <div className="linked-contract">
              <p>
                <strong>ID:</strong>{' '}
                <button
                  onClick={() => navigate(`/odps/${links!.odps_link!.id}`)}
                  className="btn-link"
                  type="button"
                >
                  {links!.odps_link!.id}
                </button>
              </p>
              <p>
                <strong>Name:</strong> {links!.odps_link!.name || 'Unnamed'}
              </p>
              <p>
                <strong>Status:</strong> {links!.odps_link!.normalization_status}
              </p>
            </div>
            <button onClick={handleUnlink} disabled={unlinkMutation.isPending} className="btn-danger" type="button">
              {unlinkMutation.isPending ? 'Unlinking...' : 'Unlink ODPS Contract'}
            </button>
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
                <label htmlFor="odps-contract-id">ODPS Contract ID</label>
                <input
                  id="odps-contract-id"
                  type="text"
                  value={odpsContractId}
                  onChange={(e) => setOdpsContractId(e.target.value)}
                  placeholder="Enter ODPS contract UUID"
                />
              </div>
            ) : (
              <>
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
                  <button
                    onClick={() => fileInputRef.current?.click()}
                    className="btn-secondary"
                    type="button"
                  >
                    Select File
                  </button>
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
                    rows={15}
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
              </>
            )}

            <div className="form-actions">
              <button
                onClick={handleLink}
                disabled={linkMutation.isPending || (linkMode === 'existing' && !odpsContractId.trim()) || (linkMode === 'create' && !odpsContent.trim())}
                className="btn-primary"
                type="button"
              >
                {linkMutation.isPending ? 'Linking...' : 'Link ODPS Contract'}
              </button>
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
      </div>
    </div>
  );
}

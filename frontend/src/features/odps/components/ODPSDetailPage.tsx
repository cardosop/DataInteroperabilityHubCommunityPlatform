/**
 * ODPS Detail Page
 * Display ODPS contract details with export/download
 */

import { useParams, useNavigate } from 'react-router-dom';
import { useContract } from '../../contracts/hooks/useContracts';
import { useODPSLinks, useExportODPS, useDownloadODPS } from '../hooks/useODPS';
import { LoadingSpinner } from '../../../shared/components/LoadingSpinner';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { UuidWithCopy } from '../../../shared/components/UuidWithCopy';
import { Breadcrumbs } from '../../../shared/components/Breadcrumbs';
import { useState } from 'react';
import './ODPSDetailPage.css';

export function ODPSDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { data: contract, isLoading, isError, error, refetch, isFetched } = useContract(id || null);
  const { data: links } = useODPSLinks(id || null);
  const exportMutation = useExportODPS();
  const downloadMutation = useDownloadODPS();
  const [exportFormat, setExportFormat] = useState<'json' | 'yaml'>('json');

  const handleExport = async () => {
    if (!id) return;
    try {
      const blob = await exportMutation.mutateAsync({
        contractId: id,
        params: {
          format: 'odps',
          output_format: exportFormat,
        },
      });
      
      // Create download link
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `odps-${id}.${exportFormat === 'json' ? 'json' : 'yaml'}`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
    } catch (err) {
      console.error('Failed to export ODPS:', err);
    }
  };

  const handleDownload = async () => {
    if (!id) return;
    try {
      const blob = await downloadMutation.mutateAsync({
        contractId: id,
        params: {
          format: 'odps',
          output_format: exportFormat,
        },
      });
      
      // Create download link
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `odps-${id}.${exportFormat === 'json' ? 'json' : 'yaml'}`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
    } catch (err) {
      console.error('Failed to download ODPS:', err);
    }
  };

  // Show error when fetch failed (404, network error) or completed with no data
  if (isError || (isFetched && !contract)) {
    return (
      <ErrorDisplay
        error={error || new Error('ODPS contract not found')}
        title="Failed to load ODPS contract"
        onRetry={() => refetch()}
      />
    );
  }
  if (isLoading) return <LoadingSpinner message="Loading ODPS contract..." />;

  // Verify contract is ODPS
  const isODPS = contract.original_spec_type?.toUpperCase() === 'ODPS';

  return (
    <div className="odps-detail-page">
      <div className="odps-detail-header">
        <button onClick={() => navigate('/odps')} className="btn-back" type="button">
          ← Back to ODPS
        </button>
        <div className="odps-detail-actions">
          {isODPS && (
            <button onClick={() => navigate(`/odps/${id}/link`)} className="btn-secondary" type="button">
              Link ODCS
            </button>
          )}
        </div>
      </div>

      <div className="odps-detail-content">
        <Breadcrumbs
          items={[
            { label: 'Home', href: '/' },
            { label: 'ODPS', href: '/odps' },
            { label: contract.name || 'Contract' },
          ]}
        />
        <div className="odps-detail-main">
          <h1>{contract.name || 'Unnamed ODPS Contract'}</h1>
          {contract.description && <p className="odps-description">{contract.description}</p>}

          <div className="odps-detail-metadata">
            <div className="metadata-item">
              <UuidWithCopy value={contract.id} label="Contract ID" />
            </div>
            <div className="metadata-item">
              <label>Format</label>
              <span>{contract.original_format || 'N/A'}</span>
            </div>
            <div className="metadata-item">
              <label>Spec Type</label>
              <span>{contract.original_spec_type || 'N/A'}</span>
            </div>
            <div className="metadata-item">
              <label>Normalization Status</label>
              <span className={`status-badge status-${(contract.normalization_status || 'UNKNOWN').toLowerCase().replace('_', '-')}`}>
                {contract.normalization_status || 'UNKNOWN'}
              </span>
            </div>
            <div className="metadata-item">
              <label>Validation Status</label>
              <span className={`validation-badge validation-${(contract.validation_status || 'UNKNOWN').toLowerCase()}`}>
                {contract.validation_status || 'UNKNOWN'}
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

          {links && (links.odcs_link || links.odps_link) && (
            <div className="odps-links-section">
              <h2>Linked Contracts</h2>
              {links.odcs_link && (
                <div className="linked-contract">
                  <h3>Linked ODCS Contract</h3>
                  <div className="linked-contract-id">
                    <UuidWithCopy value={links.odcs_link.id} label="ODCS Contract ID" />
                    <button
                      onClick={() => navigate(`/contracts/${links.odcs_link!.id}`)}
                      className="btn-link"
                      type="button"
                    >
                      View
                    </button>
                  </div>
                  <p>
                    <strong>Name:</strong> {links.odcs_link.name || 'Unnamed'}
                  </p>
                  <p>
                    <strong>Status:</strong> {links.odcs_link.normalization_status}
                  </p>
                </div>
              )}
              {links.odps_link && (
                <div className="linked-contract">
                  <h3>Linked ODPS Contract</h3>
                  <div className="linked-contract-id">
                    <UuidWithCopy value={links.odps_link.id} label="ODPS Contract ID" />
                    <button
                      onClick={() => navigate(`/odps/${links.odps_link!.id}`)}
                      className="btn-link"
                      type="button"
                    >
                      View
                    </button>
                  </div>
                  <p>
                    <strong>Name:</strong> {links.odps_link.name || 'Unnamed'}
                  </p>
                  <p>
                    <strong>Status:</strong> {links.odps_link.normalization_status}
                  </p>
                </div>
              )}
            </div>
          )}

          {isODPS && (
            <div className="odps-export-section">
              <h2>Export & Download</h2>
              <div className="export-controls">
                <div className="export-format-selector">
                  <label htmlFor="export-format">Format:</label>
                  <select
                    id="export-format"
                    value={exportFormat}
                    onChange={(e) => setExportFormat(e.target.value as 'json' | 'yaml')}
                  >
                    <option value="json">JSON</option>
                    <option value="yaml">YAML</option>
                  </select>
                </div>
                <div className="export-actions">
                  <button
                    onClick={handleExport}
                    disabled={exportMutation.isPending}
                    className="btn-secondary"
                    type="button"
                  >
                    {exportMutation.isPending ? 'Exporting...' : 'Export'}
                  </button>
                  <button
                    onClick={handleDownload}
                    disabled={downloadMutation.isPending}
                    className="btn-primary"
                    type="button"
                  >
                    {downloadMutation.isPending ? 'Downloading...' : 'Download'}
                  </button>
                </div>
              </div>
            </div>
          )}

          <div className="odps-raw">
            <h2>Raw ODPS Contract</h2>
            <pre className="odps-content">{contract.original_raw}</pre>
          </div>
        </div>
      </div>

      {exportMutation.isError && (
        <ErrorDisplay error={exportMutation.error} title="Failed to export ODPS" onRetry={() => exportMutation.reset()} />
      )}

      {downloadMutation.isError && (
        <ErrorDisplay error={downloadMutation.error} title="Failed to download ODPS" onRetry={() => downloadMutation.reset()} />
      )}
    </div>
  );
}

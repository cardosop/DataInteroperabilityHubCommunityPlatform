/**
 * Mesh Domain Detail Page
 * Displays domain details with assets assignment, policies, and compliance
 */

import { useParams, useNavigate } from 'react-router-dom';
import { useState } from 'react';
import { useMeshDomain, useDeleteMeshDomain, useDomainAnalytics, useDomainPolicies, useComplianceReports, useCheckCompliance } from '../hooks/useMesh';
import { ConfirmDialog } from '../../../shared/components/ConfirmDialog';
import { useAssets, useUpdateAsset } from '../../assets/hooks/useAssets';
import { LoadingSpinner } from '../../../shared/components/LoadingSpinner';
import { useToast } from '../../../shared/components/Toast';
import { normalizeError } from '../../../shared/utils/errorUtils';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { UuidWithCopy } from '../../../shared/components/UuidWithCopy';
import { Breadcrumbs } from '../../../shared/components/Breadcrumbs';
import './MeshDomainDetailPage.css';

export function MeshDomainDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { data: domain, isLoading, error, refetch } = useMeshDomain(id);
  const { data: analytics } = useDomainAnalytics(id);
  const { data: policies } = useDomainPolicies(id);
  const { data: complianceReports } = useComplianceReports(id);
  const { data: assetsData } = useAssets({ domain: domain?.name, page_size: 100 });
  const deleteMutation = useDeleteMeshDomain();
  const updateAssetMutation = useUpdateAsset();
  const checkComplianceMutation = useCheckCompliance();
  const toast = useToast();
  
  const [selectedAssetId, setSelectedAssetId] = useState<string>('');
  const [showAssignAsset, setShowAssignAsset] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);

  const handleAssignAsset = async () => {
    if (!id || !domain || !selectedAssetId) return;
    try {
      await updateAssetMutation.mutateAsync({
        id: selectedAssetId,
        data: { domain: domain.name },
      });
      setSelectedAssetId('');
      setShowAssignAsset(false);
      refetch();
    } catch (err) {
      // Error handled by mutation
    }
  };

  const handleRemoveAsset = async (assetId: string) => {
    if (!id || !domain) return;
    try {
      await updateAssetMutation.mutateAsync({
        id: assetId,
        data: { domain: '' },
      });
      refetch();
    } catch (err) {
      // Error handled by mutation
    }
  };

  const handleCheckCompliance = async () => {
    if (!id) return;
    try {
      await checkComplianceMutation.mutateAsync({ domainId: id });
      refetch();
    } catch (err) {
      // Error handled by mutation
    }
  };

  const handleDeleteClick = () => setShowDeleteConfirm(true);
  const handleDeleteConfirm = async () => {
    if (!id) return;
    setShowDeleteConfirm(false);
    try {
      await deleteMutation.mutateAsync(id);
      toast.success('Domain deleted.');
      navigate('/mesh');
    } catch (err) {
      toast.error(normalizeError(err).error.message || 'Failed to delete domain');
    }
  };

  if (error) {
    return <ErrorDisplay error={error} title="Failed to load domain" onRetry={() => refetch()} />;
  }

  if (isLoading || !domain) {
    return <LoadingSpinner message="Loading domain..." />;
  }

  return (
    <div className="mesh-domain-detail-page">
      <div className="mesh-domain-detail-header">
        <button onClick={() => navigate('/mesh/domains')} className="btn-back" type="button">
          ← Back to Domains
        </button>
        <div className="header-actions">
          <button onClick={() => navigate(`/mesh/domains/${id}/edit`)} className="btn-secondary" type="button">
            Edit
          </button>
          <button onClick={handleDeleteClick} className="btn-danger" type="button" disabled={deleteMutation.isPending}>
            {deleteMutation.isPending ? 'Deleting...' : 'Delete'}
          </button>
        </div>
      </div>

      <div className="mesh-domain-detail-content">
        <Breadcrumbs
          items={[
            { label: 'Home', href: '/' },
            { label: 'Mesh', href: '/mesh' },
            { label: domain.name || 'Domain' },
          ]}
        />
        <div className="domain-info-section">
          <h1>{domain.name}</h1>
          {id && (
            <div className="mesh-domain-uuid" data-testid="mesh-domain-uuid">
              <UuidWithCopy value={id} label="Domain ID" />
            </div>
          )}
          {domain.description && <p className="domain-description">{domain.description}</p>}
          
          <div className="domain-metadata">
            <div className="metadata-item">
              <span className="metadata-label">Status:</span>
              <span className={`status-badge status-${domain.status.toLowerCase()}`}>
                {domain.status}
              </span>
            </div>
            {domain.owner_email && (
              <div className="metadata-item">
                <span className="metadata-label">Owner:</span>
                <span>{domain.owner_email}</span>
              </div>
            )}
            <div className="metadata-item">
              <span className="metadata-label">Created:</span>
              <span>{new Date(domain.created_at).toLocaleString()}</span>
            </div>
            <div className="metadata-item">
              <span className="metadata-label">Updated:</span>
              <span>{new Date(domain.updated_at).toLocaleString()}</span>
            </div>
          </div>
        </div>

        {analytics && (
          <div className="domain-analytics-section">
            <h2>Analytics</h2>
            <div className="analytics-grid">
              <div className="analytics-card">
                <div className="analytics-label">Health Score</div>
                <div className="analytics-value">{analytics.health_score ?? 'N/A'}</div>
              </div>
              <div className="analytics-card">
                <div className="analytics-label">Applied Policies</div>
                <div className="analytics-value">{analytics.applied_policies}</div>
              </div>
              <div className="analytics-card">
                <div className="analytics-label">Violations</div>
                <div className="analytics-value">{analytics.violation_count}</div>
              </div>
              <div className="analytics-card">
                <div className="analytics-label">Compliance Status</div>
                <div className="analytics-value">{analytics.compliance_status || 'Unknown'}</div>
              </div>
            </div>
          </div>
        )}

        <div className="domain-assets-section">
          <div className="section-header">
            <h2>Assigned Assets</h2>
            <button onClick={() => setShowAssignAsset(true)} className="btn-primary" type="button">
              Assign Asset
            </button>
          </div>
          
          {showAssignAsset && (
            <div className="assign-asset-form">
              <select
                value={selectedAssetId}
                onChange={(e) => setSelectedAssetId(e.target.value)}
                className="asset-select"
              >
                <option value="">Select an asset...</option>
                {/* Assets would be fetched from backend */}
              </select>
              <button onClick={handleAssignAsset} className="btn-primary" type="button" disabled={!selectedAssetId}>
                Assign
              </button>
              <button onClick={() => setShowAssignAsset(false)} className="btn-secondary" type="button">
                Cancel
              </button>
            </div>
          )}

          {assetsData?.results && assetsData.results.length > 0 ? (
            <div className="assets-list">
              {assetsData.results.map((asset) => (
                <div key={asset.id} className="asset-item">
                  <span>{asset.name}</span>
                  <button
                    onClick={() => handleRemoveAsset(asset.id)}
                    className="btn-link btn-danger"
                    type="button"
                  >
                    Remove
                  </button>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-muted">No assets assigned to this domain.</p>
          )}
        </div>

        <div className="domain-governance-section">
          <div className="section-header">
            <h2>Governance</h2>
            <button onClick={handleCheckCompliance} className="btn-secondary" type="button" disabled={checkComplianceMutation.isPending}>
              {checkComplianceMutation.isPending ? 'Checking...' : 'Check Compliance'}
            </button>
          </div>

          {policies && policies.length > 0 ? (
            <div className="policies-list">
              <h3>Applied Policies</h3>
              {policies.map((policy) => (
                <div key={policy.id} className="policy-item">
                  <span>{policy.policy_name || 'Unknown Policy'}</span>
                  <span className="status-badge status-active">{policy.status}</span>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-muted">No policies applied to this domain.</p>
          )}

          {complianceReports && complianceReports.length > 0 && (
            <div className="compliance-reports-list">
              <h3>Compliance Reports</h3>
              {complianceReports.map((report) => (
                <div key={report.id} className="report-item">
                  <span>{new Date(report.generated_at).toLocaleString()}</span>
                  <span className={`status-badge status-${report.compliance_status.toLowerCase()}`}>
                    {report.compliance_status}
                  </span>
                  <span>{report.violation_count} violations</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      <ConfirmDialog
        isOpen={showDeleteConfirm}
        onClose={() => setShowDeleteConfirm(false)}
        onConfirm={handleDeleteConfirm}
        title="Delete domain"
        message="Are you sure you want to delete this domain? This action cannot be undone."
        confirmLabel="Delete"
        variant="danger"
      />
    </div>
  );
}

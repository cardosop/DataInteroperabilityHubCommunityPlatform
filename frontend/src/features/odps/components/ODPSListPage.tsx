/**
 * ODPS List Page
 * List all ODPS contracts
 */

import { useNavigate } from 'react-router-dom';
import { useContracts } from '../../contracts/hooks/useContracts';
import { ListPageSkeleton } from '../../../shared/components/skeletons/ListPageSkeleton';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import './ODPSListPage.css';
import { Button } from '../../../shared/components/Button';

export function ODPSListPage() {
  const navigate = useNavigate();
  const { data, isLoading, error, refetch } = useContracts({
    // Filter for ODPS contracts only
    // Note: Backend should support filtering by original_spec_type
  });

  // Filter ODPS contracts on the client side if backend doesn't support it
  const odpsContracts = data?.results?.filter(
    (contract) => contract.original_spec_type === 'ODPS'
  ) || [];

  if (isLoading) return <ListPageSkeleton />;
  if (error) {
    return <ErrorDisplay error={error} title="Failed to load ODPS contracts" onRetry={() => refetch()} />;
  }

  return (
    <div className="odps-list-page">
      <div className="odps-list-header">
        <h1>ODPS Contracts</h1>
        <Button onClick={() => navigate('/odps/upload')} variant="primary">
          Create ODPS Product
        </Button>
      </div>

      {odpsContracts.length === 0 ? (
        <div className="odps-empty-state">
          <p>No ODPS contracts found.</p>
          <Button onClick={() => navigate('/odps/upload')} variant="primary">
            Create Your First ODPS Product
          </Button>
        </div>
      ) : (
        <div className="odps-list">
          <table className="odps-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>Name</th>
                <th>Format</th>
                <th>Status</th>
                <th>Created</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {odpsContracts.map((contract) => (
                <tr key={contract.id} data-odps-id={contract.id}>
                  <td>
                    <code className="contract-id">{contract.id.slice(0, 8)}...</code>
                  </td>
                  <td>{contract.name || 'Unnamed'}</td>
                  <td>{contract.original_format}</td>
                  <td>
                    <span className={`status-badge status-${contract.normalization_status.toLowerCase().replace('_', '-')}`}>
                      {contract.normalization_status}
                    </span>
                  </td>
                  <td>{new Date(contract.created_at).toLocaleDateString()}</td>
                  <td>
                    <div className="action-buttons">
                      <button
                        onClick={() => navigate(`/odps/${contract.id}`)}
                        className="btn-link"
                        type="button"
                      >
                        View
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

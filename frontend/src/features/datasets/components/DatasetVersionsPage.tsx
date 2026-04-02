/**
 * Dataset Versions Page
 * Display and compare dataset versions
 */

import { useParams, useNavigate } from 'react-router-dom';
import { useDataset, useDatasetVersions } from '../hooks/useDatasets';
import { datasetService } from '../services/datasetService';
import { LoadingSpinner } from '../../../shared/components/LoadingSpinner';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { Breadcrumbs } from '../../../shared/components/Breadcrumbs';
import { useState } from 'react';
import './DatasetVersionsPage.css';
import { Button } from '../../../shared/components/Button';

export function DatasetVersionsPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { data: dataset } = useDataset(id || null);
  const { data: versions, isLoading, error, refetch } = useDatasetVersions(id || null);
  const [compareMode, setCompareMode] = useState(false);
  const [version1, setVersion1] = useState<string>('');
  const [version2, setVersion2] = useState<string>('');
  const [comparison, setComparison] = useState<{
    differences: Array<{ field: string; version1_value: unknown; version2_value: unknown }>;
  } | null>(null);
  const [isComparing, setIsComparing] = useState(false);

  const handleCompare = async () => {
    if (!id || !version1 || !version2) return;
    setIsComparing(true);
    try {
      const result = await datasetService.compareVersions(id, version1, version2);
      setComparison(result);
    } catch {
      // Handle error
    } finally {
      setIsComparing(false);
    }
  };

  if (isLoading) return <LoadingSpinner message="Loading versions..." />;
  if (error) return <ErrorDisplay error={error} title="Failed to load versions" onRetry={() => refetch()} />;
  if (!versions || versions.length === 0) {
    return (
      <div className="dataset-versions-page">
        <Breadcrumbs
          items={[
            { label: 'Home', href: '/' },
            { label: 'Datasets', href: '/datasets' },
            { label: dataset?.name || 'Dataset', href: id ? `/datasets/${id}` : undefined },
            { label: 'Versions' },
          ]}
        />
        <div className="dataset-versions-header">
          <Button onClick={() => navigate(`/datasets/${id}`)} variant="ghost">
            ← Back to Dataset
          </Button>
          <h1>Versions</h1>
        </div>
        <p>No versions available for this dataset.</p>
      </div>
    );
  }

  return (
    <div className="dataset-versions-page">
      <Breadcrumbs
        items={[
          { label: 'Home', href: '/' },
          { label: 'Datasets', href: '/datasets' },
          { label: dataset?.name || 'Dataset', href: id ? `/datasets/${id}` : undefined },
          { label: 'Versions' },
        ]}
      />
      <div className="dataset-versions-header">
        <Button onClick={() => navigate(`/datasets/${id}`)} variant="ghost">
          ← Back to Dataset
        </Button>
        <h1>Dataset Versions</h1>
        <Button
 onClick={() => setCompareMode(!compareMode)}
 variant="secondary">
          {compareMode ? 'View All' : 'Compare Versions'}
        </Button>
      </div>

      {compareMode ? (
        <div className="version-compare">
          <h2>Compare Versions</h2>
          <div className="compare-controls">
            <select value={version1} onChange={(e) => setVersion1(e.target.value)}>
              <option value="">Select version 1</option>
              {versions.map((v) => (
                <option key={v.version} value={v.version}>
                  {v.version}
                </option>
              ))}
            </select>
            <span>vs</span>
            <select value={version2} onChange={(e) => setVersion2(e.target.value)}>
              <option value="">Select version 2</option>
              {versions.map((v) => (
                <option key={v.version} value={v.version}>
                  {v.version}
                </option>
              ))}
            </select>
            <Button
 onClick={handleCompare}
 disabled={!version1 || !version2 || isComparing}
 variant="primary">
              {isComparing ? 'Comparing...' : 'Compare'}
            </Button>
          </div>

          {comparison && (
            <div className="comparison-results">
              <h3>Differences</h3>
              {comparison.differences.length === 0 ? (
                <p>No differences found.</p>
              ) : (
                <table>
                  <thead>
                    <tr>
                      <th>Field</th>
                      <th>Version 1</th>
                      <th>Version 2</th>
                    </tr>
                  </thead>
                  <tbody>
                    {comparison.differences.map((diff: { field: string; version1_value: unknown; version2_value: unknown }, idx: number) => (
                      <tr key={idx}>
                        <td>{diff.field}</td>
                        <td>{String(diff.version1_value)}</td>
                        <td>{String(diff.version2_value)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          )}
        </div>
      ) : (
        <div className="versions-list">
          <table>
            <thead>
              <tr>
                <th>Version</th>
                <th>Rows</th>
                <th>Size</th>
                <th>Created</th>
                <th>Updated</th>
              </tr>
            </thead>
            <tbody>
              {versions.map((version) => (
                <tr key={version.version}>
                  <td><strong>{version.version}</strong></td>
                  <td>{version.row_count?.toLocaleString() || '-'}</td>
                  <td>{(version.size_bytes / 1024).toFixed(2)} KB</td>
                  <td>{new Date(version.created_at).toLocaleString()}</td>
                  <td>{new Date(version.updated_at).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

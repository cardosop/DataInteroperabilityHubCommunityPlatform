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
import { DatasetVersionDiffView } from './DatasetVersionDiffView';
import type { DatasetVersionCompareResult } from '../../../shared/types/datasets';
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
  const [comparison, setComparison] = useState<DatasetVersionCompareResult | null>(null);
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
 variant="secondary"
 data-testid="dataset-version-compare-toggle">
          {compareMode ? 'View All' : 'Compare Versions'}
        </Button>
      </div>

      {compareMode ? (
        <div className="version-compare">
          <h2>Compare Versions</h2>
          <div className="compare-controls">
            <select
              value={version1}
              onChange={(e) => setVersion1(e.target.value)}
              data-testid="dataset-version-compare-select-1"
            >
              <option value="">Select version 1</option>
              {versions.map((v) => (
                <option key={v.id} value={v.id}>
                  {v.version}
                </option>
              ))}
            </select>
            <span>vs</span>
            <select
              value={version2}
              onChange={(e) => setVersion2(e.target.value)}
              data-testid="dataset-version-compare-select-2"
            >
              <option value="">Select version 2</option>
              {versions.map((v) => (
                <option key={v.id} value={v.id}>
                  {v.version}
                </option>
              ))}
            </select>
            <Button
 onClick={handleCompare}
 disabled={!version1 || !version2 || isComparing}
 variant="primary"
 data-testid="dataset-version-compare-submit">
              {isComparing ? 'Comparing...' : 'Compare'}
            </Button>
          </div>

          {comparison && (
            <DatasetVersionDiffView
              compatibilityLevel={comparison.compatibility_level}
              summary={comparison.summary}
              changes={comparison.changes}
              version1Label={comparison.version1.version}
              version2Label={comparison.version2.version}
            />
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

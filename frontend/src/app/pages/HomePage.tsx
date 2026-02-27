/**
 * Home Page Dashboard
 * Real dashboard with recent assets, datasets, jobs, and quick actions
 */

import { Link } from 'react-router-dom';
import { useAssetRecommendations, useAssets } from '../../features/assets/hooks/useAssets';
import { useAuthStore } from '../../features/auth/store/authStore';
import { useDatasets } from '../../features/datasets/hooks/useDatasets';
import { useJobs } from '../../features/jobs/hooks/useJobs';
import { EmptyState } from '../../shared/components/EmptyState';
import { ErrorDisplay } from '../../shared/components/ErrorDisplay';
import { LoadingSpinner } from '../../shared/components/LoadingSpinner';
import { useHealth } from '../../shared/hooks/useHealth';
import './HomePage.css';

export function HomePage() {
  const { user } = useAuthStore();
  // Fetch recent items (most recent first)
  const recentAssets = useAssets({ ordering: '-created_at', page_size: 5 });
  const recentDatasets = useDatasets({ ordering: '-created_at', page_size: 5 });
  const recentJobs = useJobs({ ordering: '-created_at', page_size: 5 });
  // Skip recommendations when user has no tenant (avoids 400; backend also returns [] for no-tenant)
  const recommendations = useAssetRecommendations(
    { limit: 5 },
    { enabled: !!user?.tenant_id }
  );
  const health = useHealth();

  const formatDate = (dateString: string) => {
    try {
      return new Date(dateString).toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
      });
    } catch {
      return dateString;
    }
  };

  const getStatusBadgeClass = (status: string) => {
    switch (status?.toUpperCase()) {
      case 'ACTIVE':
      case 'COMPLETED':
      case 'SUCCESS':
        return 'status-badge-success';
      case 'PENDING':
      case 'RUNNING':
        return 'status-badge-warning';
      case 'FAILED':
      case 'ERROR':
        return 'status-badge-error';
      default:
        return 'status-badge-default';
    }
  };

  const getHealthStatusBadge = () => {
    if (!health.data) return 'status-unknown';
    const status = health.data.status?.toLowerCase();
    if (status === 'healthy') return 'status-healthy';
    if (status === 'degraded') return 'status-degraded';
    return 'status-unhealthy';
  };

  return (
    <div className="home-page" data-testid="home-page">
      <div className="home-header">
        <div className="header-content">
          <div>
            <h1>Dashboard</h1>
            <p className="subtitle">Welcome to your data interoperability hub</p>
          </div>
          {/* System Status Widget */}
          <div className="system-status-widget" data-testid="home-system-status">
            <span className="system-status-label">System Status:</span>
            {health.isLoading ? (
              <span className="system-status-badge status-loading">Checking...</span>
            ) : health.error ? (
              <span className="system-status-badge status-unknown">Unknown</span>
            ) : (
              <span className={`system-status-badge ${getHealthStatusBadge()}`}>
                {health.data?.status?.toUpperCase() || 'UNKNOWN'}
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Quick Actions */}
      <div className="quick-actions" data-testid="home-quick-actions">
        <h2>Quick Actions</h2>
        <div className="quick-actions-grid">
          <Link to="/assets/create" className="quick-action-card">
            <span className="quick-action-icon">📦</span>
            <span className="quick-action-label">Create Asset</span>
          </Link>
          <Link to="/search" className="quick-action-card">
            <span className="quick-action-icon">🔍</span>
            <span className="quick-action-label">Search</span>
          </Link>
          <Link to="/datasets" className="quick-action-card">
            <span className="quick-action-icon">📊</span>
            <span className="quick-action-label">View Datasets</span>
          </Link>
          <Link to="/jobs" className="quick-action-card">
            <span className="quick-action-icon">⚙️</span>
            <span className="quick-action-label">View Jobs</span>
          </Link>
        </div>
      </div>

      {/* Dashboard Sections */}
      <div className="dashboard-sections">
        {/* Recent Assets */}
        <section className="dashboard-section" data-testid="home-recent-assets">
          <div className="section-header">
            <h2>Recent Assets</h2>
            <Link to="/assets" className="section-link">
              View All →
            </Link>
          </div>
          {recentAssets.isLoading && <LoadingSpinner message="Loading assets..." />}
          {recentAssets.error && (
            <ErrorDisplay error={recentAssets.error} title="Failed to load assets" />
          )}
          {recentAssets.data && (
            <>
              {recentAssets.data.results.length === 0 ? (
                <EmptyState message="No assets yet. Create your first asset to get started." />
              ) : (
                <div className="items-list">
                  {recentAssets.data.results.map((asset) => (
                    <Link key={asset.id} to={`/assets/${asset.id}`} className="item-card">
                      <div className="item-header">
                        <span className="item-title">{asset.name}</span>
                        <span className={`status-badge ${getStatusBadgeClass(asset.status)}`}>
                          {asset.status}
                        </span>
                      </div>
                      {asset.description && <p className="item-description">{asset.description}</p>}
                      <div className="item-meta">
                        <span className="item-date">Created {formatDate(asset.created_at)}</span>
                        {asset.domain && <span className="item-domain">{asset.domain}</span>}
                      </div>
                    </Link>
                  ))}
                </div>
              )}
            </>
          )}
        </section>

        {/* Recent Datasets */}
        <section className="dashboard-section" data-testid="home-recent-datasets">
          <div className="section-header">
            <h2>Recent Datasets</h2>
            <Link to="/datasets" className="section-link">
              View All →
            </Link>
          </div>
          {recentDatasets.isLoading && <LoadingSpinner message="Loading datasets..." />}
          {recentDatasets.error && (
            <ErrorDisplay error={recentDatasets.error} title="Failed to load datasets" />
          )}
          {recentDatasets.data && (
            <>
              {recentDatasets.data.results.length === 0 ? (
                <EmptyState message="No datasets yet." />
              ) : (
                <div className="items-list">
                  {recentDatasets.data.results.map((dataset) => (
                    <Link key={dataset.id} to={`/datasets/${dataset.id}`} className="item-card">
                      <div className="item-header">
                        <span className="item-title">{dataset.name}</span>
                        {dataset.format && <span className="item-format">{dataset.format}</span>}
                      </div>
                      {dataset.description && (
                        <p className="item-description">{dataset.description}</p>
                      )}
                      <div className="item-meta">
                        <span className="item-date">Created {formatDate(dataset.created_at)}</span>
                      </div>
                    </Link>
                  ))}
                </div>
              )}
            </>
          )}
        </section>

        {/* Recent Jobs */}
        <section className="dashboard-section" data-testid="home-recent-jobs">
          <div className="section-header">
            <h2>Recent Jobs</h2>
            <Link to="/jobs" className="section-link">
              View All →
            </Link>
          </div>
          {recentJobs.isLoading && <LoadingSpinner message="Loading jobs..." />}
          {recentJobs.error && (
            <ErrorDisplay error={recentJobs.error} title="Failed to load jobs" />
          )}
          {recentJobs.data && (
            <>
              {recentJobs.data.results.length === 0 ? (
                <EmptyState message="No jobs yet." />
              ) : (
                <div className="items-list">
                  {recentJobs.data.results.map((job) => (
                    <Link key={job.id} to={`/jobs/${job.id}`} className="item-card">
                      <div className="item-header">
                        <span className="item-title">{job.type}</span>
                        <span className={`status-badge ${getStatusBadgeClass(job.status)}`}>
                          {job.status}
                        </span>
                      </div>
                      {job.resource_type && (
                        <p className="item-description">
                          {job.resource_type}: {job.resource_id?.substring(0, 8)}...
                        </p>
                      )}
                      <div className="item-meta">
                        <span className="item-date">Created {formatDate(job.created_at)}</span>
                      </div>
                    </Link>
                  ))}
                </div>
              )}
            </>
          )}
        </section>

        {/* Recommendations (Optional) */}
        {recommendations.data && recommendations.data.length > 0 && (
          <section className="dashboard-section" data-testid="home-recommendations">
            <div className="section-header">
              <h2>Recommended Assets</h2>
            </div>
            <div className="items-list">
              {recommendations.data.slice(0, 5).map((rec) => (
                <Link key={rec.asset_id} to={`/assets/${rec.asset_id}`} className="item-card">
                  <div className="item-header">
                    <span className="item-title">{rec.asset_name}</span>
                    {rec.score != null && (
                      <span className="item-score">
                        {Math.round(rec.score * 100)}% match
                      </span>
                    )}
                  </div>
                  {rec.reasons?.length ? (
                    <p className="item-description">{rec.reasons.map((r) => r.reason).join(', ')}</p>
                  ) : null}
                </Link>
              ))}
            </div>
          </section>
        )}
      </div>
    </div>
  );
}

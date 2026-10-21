/**
 * Developer Portal Page
 * Displays plugins marketplace and SDK documentation
 */

import { useState } from 'react';
import { usePlugins, useSDKDocumentation } from '../hooks/useDeveloper';
import { LoadingSpinner } from '../../../shared/components/LoadingSpinner';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { EmptyState } from '../../../shared/components/EmptyState';
import { PluginCategory, PluginStatus, SDKLanguage } from '../../../shared/types/developer';
import './DeveloperPortalPage.css';

type TabType = 'plugins' | 'sdk';

export function DeveloperPortalPage() {
  const [activeTab, setActiveTab] = useState<TabType>('plugins');
  const [pluginCategory, setPluginCategory] = useState<PluginCategory | ''>('');
  const [pluginStatus, setPluginStatus] = useState<PluginStatus | ''>('');
  const [pluginSearch, setPluginSearch] = useState('');
  const [sdkLanguage, setSDKLanguage] = useState<SDKLanguage | ''>('');

  const { data: pluginsData, isLoading: pluginsLoading, error: pluginsError } = usePlugins({
    page_size: 50,
    category: pluginCategory || undefined,
    status: pluginStatus || undefined,
    search: pluginSearch || undefined,
  });

  const { data: sdkData, isLoading: sdkLoading, error: sdkError } = useSDKDocumentation({
    page_size: 50,
    language: sdkLanguage || undefined,
  });

  return (
    <div className="developer-portal-page">
      <div className="developer-portal-header">
        <h1>Developer Portal</h1>
        <p className="subtitle">Discover plugins and access SDK documentation</p>
      </div>

      <div className="developer-portal-tabs">
        <button
          className={`portal-tab ${activeTab === 'plugins' ? 'active' : ''}`}
          onClick={() => setActiveTab('plugins')}
          type="button"
        >
          Plugins Marketplace
        </button>
        <button
          className={`portal-tab ${activeTab === 'sdk' ? 'active' : ''}`}
          onClick={() => setActiveTab('sdk')}
          type="button"
        >
          SDK Documentation
        </button>
      </div>

      <div className="developer-portal-content">
        {activeTab === 'plugins' && (
          <div className="plugins-section">
            <div className="plugins-filters">
              <input
                type="text"
                placeholder="Search plugins..."
                value={pluginSearch}
                onChange={(e) => setPluginSearch(e.target.value)}
                className="filter-input"
              />
              <select
                value={pluginCategory}
                onChange={(e) => setPluginCategory(e.target.value as PluginCategory | '')}
                className="filter-select"
              >
                <option value="">All Categories</option>
                {Object.values(PluginCategory).map(cat => (
                  <option key={cat} value={cat}>{cat}</option>
                ))}
              </select>
              <select
                value={pluginStatus}
                onChange={(e) => setPluginStatus(e.target.value as PluginStatus | '')}
                className="filter-select"
              >
                <option value="">All Status</option>
                {Object.values(PluginStatus).map(status => (
                  <option key={status} value={status}>{status}</option>
                ))}
              </select>
            </div>

            {pluginsLoading && <LoadingSpinner message="Loading plugins..." />}
            {pluginsError && <ErrorDisplay error={pluginsError} title="Failed to load plugins" />}
            {pluginsData && pluginsData.results.length === 0 && (
              <EmptyState title="No plugins found" message="Try adjusting your filters." />
            )}
            {pluginsData && pluginsData.results.length > 0 && (
              <div className="plugins-grid">
                {pluginsData.results.map(plugin => (
                  <div key={plugin.id} className="plugin-card">
                    <div className="plugin-header">
                      <h3>{plugin.name}</h3>
                      <span className={`plugin-status status-${plugin.status.toLowerCase()}`}>
                        {plugin.status}
                      </span>
                    </div>
                    <p className="plugin-description">{plugin.description}</p>
                    <div className="plugin-meta">
                      <span>v{plugin.version}</span>
                      <span>by {plugin.author}</span>
                      <span>{plugin.download_count} downloads</span>
                      {plugin.rating && <span>⭐ {plugin.rating.toFixed(1)}</span>}
                    </div>
                    <div className="plugin-category">{plugin.category}</div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {activeTab === 'sdk' && (
          <div className="sdk-section">
            <div className="sdk-filters">
              <select
                value={sdkLanguage}
                onChange={(e) => setSDKLanguage(e.target.value as SDKLanguage | '')}
                className="filter-select"
              >
                <option value="">All Languages</option>
                {Object.values(SDKLanguage).map(lang => (
                  <option key={lang} value={lang}>{lang}</option>
                ))}
              </select>
            </div>

            {sdkLoading && <LoadingSpinner message="Loading SDK documentation..." />}
            {sdkError && <ErrorDisplay error={sdkError} title="Failed to load SDK documentation" />}
            {sdkData && sdkData.results.length === 0 && (
              <EmptyState title="No SDK documentation found" message="SDK documentation will be available soon." />
            )}
            {sdkData && sdkData.results.length > 0 && (
              <div className="sdk-list">
                {sdkData.results.map(sdk => (
                  <div key={sdk.id} className="sdk-card">
                    <div className="sdk-header">
                      <h3>{sdk.language.toUpperCase()} SDK</h3>
                      <span className="sdk-version">v{sdk.version}</span>
                    </div>
                    <div className="sdk-actions">
                      <a href={sdk.documentation_url} target="_blank" rel="noopener noreferrer" className="btn-primary">
                        View Documentation
                      </a>
                      {sdk.download_url && (
                        <a href={sdk.download_url} className="btn-secondary">
                          Download
                        </a>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

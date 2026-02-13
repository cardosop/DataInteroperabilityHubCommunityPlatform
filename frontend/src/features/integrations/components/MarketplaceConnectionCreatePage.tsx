/**
 * Marketplace Connection Create Page
 * Form for creating a new marketplace connection (OpenAPI create schema)
 */

import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useCreateMarketplaceConnection } from '../hooks/useMarketplaceConnections';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { MarketplaceType } from '../../../shared/types/integrations';
import './MarketplaceConnectionCreatePage.css';

const MARKETPLACE_TYPE_OPTIONS = Object.entries(MarketplaceType).map(([key, value]) => ({
  value,
  label: key.replace(/_/g, ' '),
}));

export function MarketplaceConnectionCreatePage() {
  const navigate = useNavigate();
  const createMutation = useCreateMarketplaceConnection();
  const [formData, setFormData] = useState<{
    name: string;
    marketplace_type: MarketplaceType;
    config_json: string;
    is_active: boolean;
  }>({
    name: '',
    marketplace_type: MarketplaceType.GCP_DATA_EXCHANGE,
    config_json: '{}',
    is_active: true,
  });
  const [errors, setErrors] = useState<Record<string, string>>({});

  const validate = (): boolean => {
    const newErrors: Record<string, string> = {};
    if (!formData.name.trim()) {
      newErrors.name = 'Name is required';
    }
    try {
      JSON.parse(formData.config_json || '{}');
    } catch (e) {
      newErrors.config_json = 'Config must be valid JSON';
    }
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!validate()) return;
    try {
      const configObj = JSON.parse(formData.config_json || '{}') as Record<string, unknown>;
      const connection = await createMutation.mutateAsync({
        name: formData.name.trim(),
        marketplace_type: formData.marketplace_type,
        config_json: configObj,
        is_active: formData.is_active,
      });
      navigate(`/integrations/connections/${connection.id}`);
    } catch {
      // Error handled by mutation
    }
  };

  return (
    <div className="marketplace-connection-create-page">
      <div className="marketplace-connection-create-header">
        <button
          onClick={() => navigate('/integrations/connections')}
          className="btn-back"
          type="button"
        >
          ← Back to Connections
        </button>
        <h1>Create Marketplace Connection</h1>
      </div>

      {createMutation.isError && (
        <ErrorDisplay
          error={createMutation.error}
          title="Failed to create connection"
          onRetry={() => createMutation.reset()}
        />
      )}

      <form onSubmit={handleSubmit} className="marketplace-connection-create-form">
        <div className="form-group">
          <label htmlFor="name">
            Connection Name <span className="required">*</span>
          </label>
          <input
            id="name"
            type="text"
            value={formData.name}
            onChange={(e) => setFormData({ ...formData, name: e.target.value })}
            className={errors.name ? 'error' : ''}
            required
            placeholder="e.g. My GCP Marketplace"
          />
          {errors.name && <span className="error-message">{errors.name}</span>}
        </div>

        <div className="form-group">
          <label htmlFor="marketplace_type">Marketplace Type <span className="required">*</span></label>
          <select
            id="marketplace_type"
            value={formData.marketplace_type}
            onChange={(e) =>
              setFormData({ ...formData, marketplace_type: e.target.value as MarketplaceType })
            }
          >
            {MARKETPLACE_TYPE_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>

        <div className="form-group">
          <label htmlFor="config_json">Configuration (JSON)</label>
          <textarea
            id="config_json"
            value={formData.config_json}
            onChange={(e) => setFormData({ ...formData, config_json: e.target.value })}
            className={errors.config_json ? 'error' : ''}
            rows={8}
            placeholder='{"api_key": "...", "project_id": "..."}'
          />
          {errors.config_json && (
            <span className="error-message">{errors.config_json}</span>
          )}
        </div>

        <div className="form-group form-group-checkbox">
          <label>
            <input
              type="checkbox"
              checked={formData.is_active}
              onChange={(e) => setFormData({ ...formData, is_active: e.target.checked })}
            />
            Active (connection enabled for sync)
          </label>
        </div>

        <div className="form-actions">
          <button
            type="button"
            onClick={() => navigate('/integrations/connections')}
            className="btn-secondary"
            disabled={createMutation.isPending}
          >
            Cancel
          </button>
          <button
            type="submit"
            className="btn-primary"
            disabled={createMutation.isPending}
          >
            {createMutation.isPending ? 'Creating...' : 'Create Connection'}
          </button>
        </div>
      </form>
    </div>
  );
}

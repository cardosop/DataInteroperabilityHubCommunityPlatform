/**
 * Marketplace Connection Edit Page
 * Form for updating an existing marketplace connection
 */

import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  useMarketplaceConnection,
  useUpdateMarketplaceConnection,
} from '../hooks/useMarketplaceConnections';
import { LoadingSpinner } from '../../../shared/components/LoadingSpinner';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { MarketplaceType } from '../../../shared/types/integrations';
import './MarketplaceConnectionCreatePage.css';

const MARKETPLACE_TYPE_OPTIONS = Object.entries(MarketplaceType).map(([key, value]) => ({
  value,
  label: key.replace(/_/g, ' '),
}));

export function MarketplaceConnectionEditPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { data: connection, isLoading, error, refetch } = useMarketplaceConnection(id ?? null);
  const updateMutation = useUpdateMarketplaceConnection();
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
  const [initialized, setInitialized] = useState(false);

  useEffect(() => {
    if (connection && !initialized) {
      setFormData({
        name: connection.name,
        marketplace_type: connection.marketplace_type,
        config_json: JSON.stringify(connection.config_json ?? {}, null, 2),
        is_active: connection.is_active,
      });
      setInitialized(true);
    }
  }, [connection, initialized]);

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
    if (!id || !validate()) return;
    try {
      const configObj = JSON.parse(formData.config_json || '{}') as Record<string, unknown>;
      await updateMutation.mutateAsync({
        id,
        data: {
          name: formData.name.trim(),
          config_json: configObj,
          is_active: formData.is_active,
        },
      });
      navigate(`/integrations/connections/${id}`);
    } catch {
      // Error handled by mutation
    }
  };

  if (error) {
    return (
      <ErrorDisplay error={error} title="Failed to load connection" onRetry={() => refetch()} />
    );
  }

  if (isLoading || !connection) {
    return <LoadingSpinner message="Loading connection..." />;
  }

  return (
    <div className="marketplace-connection-create-page marketplace-connection-edit-page">
      <div className="marketplace-connection-create-header">
        <button
          onClick={() => navigate(`/integrations/connections/${id}`)}
          className="btn-back"
          type="button"
        >
          ← Back to Connection
        </button>
        <h1>Edit Marketplace Connection</h1>
      </div>

      {updateMutation.isError && (
        <ErrorDisplay
          error={updateMutation.error}
          title="Failed to update connection"
          onRetry={() => updateMutation.reset()}
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
            onClick={() => navigate(`/integrations/connections/${id}`)}
            className="btn-secondary"
            disabled={updateMutation.isPending}
          >
            Cancel
          </button>
          <button
            type="submit"
            className="btn-primary"
            disabled={updateMutation.isPending}
          >
            {updateMutation.isPending ? 'Saving...' : 'Save Changes'}
          </button>
        </div>
      </form>
    </div>
  );
}

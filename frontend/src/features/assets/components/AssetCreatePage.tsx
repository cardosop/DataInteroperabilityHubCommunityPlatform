/**
 * Asset Create Page
 * Form for creating new assets
 */

import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useCreateAsset } from '../hooks/useAssets';
import { LoadingSpinner } from '../../../shared/components/LoadingSpinner';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { useToast } from '../../../shared/components/Toast';
import { normalizeError } from '../../../shared/utils/errorUtils';
import type { AssetVisibility } from '../../../shared/types/assets';
import './AssetCreatePage.css';
import { Button } from '../../../shared/components/Button';

export function AssetCreatePage() {
  const navigate = useNavigate();
  const toast = useToast();
  const createMutation = useCreateAsset();
  const [formData, setFormData] = useState({
    key: '',
    name: '',
    description: '',
    domain: '',
    visibility: 'INTERNAL' as AssetVisibility,
  });
  const [errors, setErrors] = useState<Record<string, string>>({});

  const validate = (): boolean => {
    const newErrors: Record<string, string> = {};
    
    if (!formData.key.trim()) {
      newErrors.key = 'Key is required';
    } else if (!/^[a-z0-9-]+$/.test(formData.key)) {
      newErrors.key = 'Key must contain only lowercase letters, numbers, and hyphens';
    }
    
    if (!formData.name.trim()) {
      newErrors.name = 'Name is required';
    }
    
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!validate()) {
      return;
    }

    try {
      const asset = await createMutation.mutateAsync({
        key: formData.key.trim(),
        name: formData.name.trim(),
        description: formData.description.trim() || undefined,
        domain: formData.domain.trim() || undefined,
        visibility: formData.visibility,
      });
      toast.success('Asset created successfully.');
      navigate(`/assets/${asset.id}`);
    } catch (error) {
      toast.error(normalizeError(error).error.message || 'Failed to create asset');
    }
  };

  const handleIHaveDataClick = () => {
    navigate('/datasets/create?linkMode=create_new');
  };

  return (
    <div className="asset-create-page">
      <div className="asset-create-header">
        <Button onClick={() => navigate('/assets')} variant="ghost">
          ← Back to Assets
        </Button>
        <h1>Create Asset</h1>
      </div>

      <div className="asset-create-flow-choice" role="group" aria-label="Asset creation method">
        <button
          type="button"
          className="flow-choice-card flow-choice-data-first"
          onClick={handleIHaveDataClick}
          data-testid="flow-i-have-data"
          aria-label="I have data to upload - create asset with file upload"
        >
          <span className="flow-choice-icon">📤</span>
          <span className="flow-choice-title">I have data to upload</span>
          <span className="flow-choice-desc">
            Upload a file and create an asset with dataset and contract automatically
          </span>
        </button>
      </div>

      <div className="asset-create-divider">
        <span>or create from metadata</span>
      </div>

      {createMutation.isError && (
        <ErrorDisplay
          error={createMutation.error}
          title="Failed to create asset"
          onRetry={() => createMutation.reset()}
        />
      )}

      <form onSubmit={handleSubmit} className="asset-create-form">
        <div className="form-group">
          <label htmlFor="key">
            Key <span className="required">*</span>
          </label>
          <input
            id="key"
            type="text"
            value={formData.key}
            onChange={(e) => setFormData({ ...formData, key: e.target.value })}
            className={errors.key ? 'error' : ''}
            placeholder="my-asset-key"
            required
          />
          {errors.key && <span className="error-message">{errors.key}</span>}
          <p className="field-hint">Unique identifier (lowercase, numbers, hyphens only)</p>
        </div>

        <div className="form-group">
          <label htmlFor="name">
            Name <span className="required">*</span>
          </label>
          <input
            id="name"
            type="text"
            value={formData.name}
            onChange={(e) => setFormData({ ...formData, name: e.target.value })}
            className={errors.name ? 'error' : ''}
            placeholder="My Asset"
            required
          />
          {errors.name && <span className="error-message">{errors.name}</span>}
        </div>

        <div className="form-group">
          <label htmlFor="description">Description</label>
          <textarea
            id="description"
            value={formData.description}
            onChange={(e) => setFormData({ ...formData, description: e.target.value })}
            rows={4}
            placeholder="Asset description..."
          />
        </div>

        <div className="form-group">
          <label htmlFor="domain">Domain</label>
          <input
            id="domain"
            type="text"
            value={formData.domain}
            onChange={(e) => setFormData({ ...formData, domain: e.target.value })}
            placeholder="marketing, sales, etc."
          />
        </div>

        <div className="form-group">
          <label htmlFor="visibility">Visibility</label>
          <select
            id="visibility"
            value={formData.visibility}
            onChange={(e) => setFormData({ ...formData, visibility: e.target.value as AssetVisibility })}
          >
            <option value="INTERNAL">Internal</option>
            <option value="EXTERNAL">External</option>
            <option value="PUBLIC">Public</option>
          </select>
        </div>

        <div className="form-actions">
          <Button
 onClick={() => navigate('/assets')}
 variant="secondary"
 loading={createMutation.isPending}>
            Cancel
          </Button>
          <Button
 type="submit"
 variant="primary"
 loading={createMutation.isPending}>
            {createMutation.isPending ? (
              <>
                <LoadingSpinner size="small" />
                Creating...
              </>
            ) : (
              'Create Asset'
            )}
          </Button>
        </div>
      </form>
    </div>
  );
}

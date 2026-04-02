/**
 * Mesh Domain Create Page
 * Form for creating new mesh domains
 */

import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useCreateMeshDomain } from '../hooks/useMesh';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { isValidUUID } from '../../../shared/utils/validation';
import { DomainStatus } from '../../../shared/types/mesh';
import './MeshDomainCreatePage.css';
import { Button } from '../../../shared/components/Button';

export function MeshDomainCreatePage() {
  const navigate = useNavigate();
  const createMutation = useCreateMeshDomain();
  const [formData, setFormData] = useState<{
    name: string;
    description: string;
    owner_id: string;
    status: DomainStatus;
  }>({
    name: '',
    description: '',
    owner_id: '',
    status: DomainStatus.ACTIVE,
  });
  const [errors, setErrors] = useState<Record<string, string>>({});

  const validate = (): boolean => {
    const newErrors: Record<string, string> = {};

    if (!formData.name.trim()) {
      newErrors.name = 'Name is required';
    }

    const ownerId = formData.owner_id.trim();
    if (ownerId && !isValidUUID(ownerId)) {
      newErrors.owner_id = 'Owner ID must be a valid UUID';
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
      const domain = await createMutation.mutateAsync({
        name: formData.name.trim(),
        description: formData.description.trim() || undefined,
        owner_id: formData.owner_id.trim() || undefined,
        status: formData.status,
      });
      navigate(`/mesh/${domain.id}`);
    } catch {
      // Error handled by mutation
    }
  };

  return (
    <div className="mesh-domain-create-page">
      <div className="mesh-domain-create-header">
        <Button onClick={() => navigate('/mesh')} variant="ghost">
          ← Back to Domains
        </Button>
        <h1>Create Mesh Domain</h1>
      </div>

      {createMutation.isError && (
        <ErrorDisplay
          error={createMutation.error}
          title="Failed to create domain"
          onRetry={() => createMutation.reset()}
        />
      )}

      <form onSubmit={handleSubmit} className="mesh-domain-create-form">
        <div className="form-group">
          <label htmlFor="name">
            Domain Name <span className="required">*</span>
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
          <label htmlFor="description">Description</label>
          <textarea
            id="description"
            value={formData.description}
            onChange={(e) => setFormData({ ...formData, description: e.target.value })}
            rows={4}
          />
        </div>

        <div className="form-group">
          <label htmlFor="owner_id">Owner ID (optional)</label>
          <input
            id="owner_id"
            type="text"
            value={formData.owner_id}
            onChange={(e) => setFormData({ ...formData, owner_id: e.target.value })}
            placeholder="UUID of the owner user"
            className={errors.owner_id ? 'error' : ''}
          />
          {errors.owner_id && <span className="error-message">{errors.owner_id}</span>}
        </div>

        <div className="form-group">
          <label htmlFor="status">Status</label>
          <select
            id="status"
            value={formData.status}
            onChange={(e) => setFormData({ ...formData, status: e.target.value as DomainStatus })}
          >
            <option value={DomainStatus.ACTIVE}>Active</option>
            <option value={DomainStatus.INACTIVE}>Inactive</option>
            <option value={DomainStatus.ARCHIVED}>Archived</option>
          </select>
        </div>

        <div className="form-actions">
          <Button
 onClick={() => navigate('/mesh')}
 variant="secondary"
 loading={createMutation.isPending}>
            Cancel
          </Button>
          <Button
 type="submit"
 variant="primary"
 loading={createMutation.isPending}>
            Create Domain
          </Button>
        </div>
      </form>
    </div>
  );
}

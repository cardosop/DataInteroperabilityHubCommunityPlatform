/**
 * Virtual Dataset Edit Page
 * Form for updating an existing virtual dataset (reuses create form logic)
 */

import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useVirtualDataset, useUpdateVirtualDataset } from '../hooks/useVirtualization';
import { LoadingSpinner } from '../../../shared/components/LoadingSpinner';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { VirtualDatasetStatus, QueryType } from '../../../shared/types/virtualization';
import './VirtualDatasetCreatePage.css';

export function VirtualDatasetEditPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { data: dataset, isLoading, error, refetch } = useVirtualDataset(id);
  const updateMutation = useUpdateVirtualDataset();
  const [formData, setFormData] = useState<{
    name: string;
    description: string;
    query: string;
    query_type: QueryType;
    schema: string;
    sources: string;
    status: VirtualDatasetStatus;
  }>({
    name: '',
    description: '',
    query: '',
    query_type: QueryType.SQL,
    schema: '{}',
    sources: '[]',
    status: VirtualDatasetStatus.DRAFT,
  });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [initialized, setInitialized] = useState(false);

  useEffect(() => {
    if (dataset && !initialized) {
      setFormData({
        name: dataset.name,
        description: dataset.description ?? '',
        query: dataset.query,
        query_type: dataset.query_type,
        schema: JSON.stringify(dataset.schema ?? {}, null, 2),
        sources: JSON.stringify(dataset.sources ?? [], null, 2),
        status: dataset.status,
      });
      setInitialized(true);
    }
  }, [dataset, initialized]);

  const validate = (): boolean => {
    const newErrors: Record<string, string> = {};

    if (!formData.name.trim()) {
      newErrors.name = 'Name is required';
    }

    if (!formData.query.trim()) {
      newErrors.query = 'Query is required';
    }

    try {
      JSON.parse(formData.schema || '{}');
    } catch (e) {
      newErrors.schema = 'Schema must be valid JSON';
    }

    try {
      JSON.parse(formData.sources || '[]');
    } catch (e) {
      newErrors.sources = 'Sources must be valid JSON array';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!id || !validate()) return;

    try {
      let schemaObj: Record<string, unknown> = {};
      let sourcesArr: unknown[] = [];

      try {
        schemaObj = JSON.parse(formData.schema || '{}') as Record<string, unknown>;
      } catch {
        // Already validated
      }

      try {
        sourcesArr = JSON.parse(formData.sources || '[]') as unknown[];
      } catch {
        // Already validated
      }

      await updateMutation.mutateAsync({
        id,
        data: {
          name: formData.name.trim(),
          description: formData.description.trim() || undefined,
          query: formData.query.trim(),
          query_type: formData.query_type,
          schema: Object.keys(schemaObj).length > 0 ? schemaObj : undefined,
          sources: sourcesArr.length > 0 ? sourcesArr : undefined,
          status: formData.status,
        },
      });
      navigate(`/virtualization/${id}`);
    } catch {
      // Error handled by mutation
    }
  };

  if (error) {
    return <ErrorDisplay error={error} title="Failed to load dataset" onRetry={() => refetch()} />;
  }

  if (isLoading || !dataset) {
    return <LoadingSpinner message="Loading dataset..." />;
  }

  return (
    <div className="virtual-dataset-create-page virtual-dataset-edit-page">
      <div className="virtual-dataset-create-header">
        <button onClick={() => navigate('/virtualization')} className="btn-back" type="button">
          ← Back to Datasets
        </button>
        <h1>Edit Virtual Dataset</h1>
      </div>

      {updateMutation.isError && (
        <ErrorDisplay
          error={updateMutation.error}
          title="Failed to update dataset"
          onRetry={() => updateMutation.reset()}
        />
      )}

      <form onSubmit={handleSubmit} className="virtual-dataset-create-form">
        <div className="form-group">
          <label htmlFor="name">
            Dataset Name <span className="required">*</span>
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
            rows={3}
          />
        </div>

        <div className="form-group">
          <label htmlFor="query_type">Query Type <span className="required">*</span></label>
          <select
            id="query_type"
            value={formData.query_type}
            onChange={(e) => setFormData({ ...formData, query_type: e.target.value as QueryType })}
          >
            <option value={QueryType.SQL}>SQL</option>
            <option value={QueryType.SPARQL}>SPARQL</option>
            <option value={QueryType.FEDERATED}>Federated</option>
            <option value={QueryType.GRAPHQL}>GraphQL</option>
            <option value={QueryType.REST}>REST</option>
          </select>
        </div>

        <div className="form-group">
          <label htmlFor="query">
            Query <span className="required">*</span>
          </label>
          <textarea
            id="query"
            value={formData.query}
            onChange={(e) => setFormData({ ...formData, query: e.target.value })}
            className={errors.query ? 'error' : ''}
            rows={10}
            required
            placeholder="SELECT * FROM table WHERE condition = ?"
          />
          {errors.query && <span className="error-message">{errors.query}</span>}
        </div>

        <div className="form-group">
          <label htmlFor="schema">Schema (JSON)</label>
          <textarea
            id="schema"
            value={formData.schema}
            onChange={(e) => setFormData({ ...formData, schema: e.target.value })}
            className={errors.schema ? 'error' : ''}
            rows={5}
            placeholder='{"field1": "string", "field2": "number"}'
          />
          {errors.schema && <span className="error-message">{errors.schema}</span>}
        </div>

        <div className="form-group">
          <label htmlFor="sources">Sources (JSON Array)</label>
          <textarea
            id="sources"
            value={formData.sources}
            onChange={(e) => setFormData({ ...formData, sources: e.target.value })}
            className={errors.sources ? 'error' : ''}
            rows={5}
            placeholder='[{"type": "database", "connection": "..."}]'
          />
          {errors.sources && <span className="error-message">{errors.sources}</span>}
        </div>

        <div className="form-group">
          <label htmlFor="status">Status</label>
          <select
            id="status"
            value={formData.status}
            onChange={(e) => setFormData({ ...formData, status: e.target.value as VirtualDatasetStatus })}
          >
            <option value={VirtualDatasetStatus.DRAFT}>Draft</option>
            <option value={VirtualDatasetStatus.ACTIVE}>Active</option>
            <option value={VirtualDatasetStatus.INACTIVE}>Inactive</option>
          </select>
        </div>

        <div className="form-actions">
          <button
            type="button"
            onClick={() => navigate(`/virtualization/${id}`)}
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

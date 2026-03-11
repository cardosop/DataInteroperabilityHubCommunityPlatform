/**
 * Virtual Dataset Create Page
 * Form for creating new virtual datasets
 */

import { useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useCreateVirtualDataset } from '../hooks/useVirtualization';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { VirtualDatasetStatus, QueryType } from '../../../shared/types/virtualization';
import { VirtualDatasetSourceBuilder, type SourceEntry } from './VirtualDatasetSourceBuilder';
import './VirtualDatasetCreatePage.css';

export function VirtualDatasetCreatePage() {
  const navigate = useNavigate();
  const createMutation = useCreateVirtualDataset();
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

  const handleSourcesChange = useCallback((sources: SourceEntry[]) => {
    setFormData((prev) => ({
      ...prev,
      sources: JSON.stringify(sources, null, 2),
    }));
  }, []);

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
    
    if (!validate()) {
      return;
    }

    try {
      let schemaObj = {};
      let sourcesArr: any[] = [];

      try {
        schemaObj = JSON.parse(formData.schema || '{}');
      } catch (e) {
        // Already validated
      }

      try {
        sourcesArr = JSON.parse(formData.sources || '[]');
      } catch (e) {
        // Already validated
      }

      const dataset = await createMutation.mutateAsync({
        name: formData.name.trim(),
        description: formData.description.trim() || undefined,
        query: formData.query.trim(),
        query_type: formData.query_type,
        schema: Object.keys(schemaObj).length > 0 ? schemaObj : undefined,
        sources: sourcesArr.length > 0 ? sourcesArr : undefined,
        status: formData.status,
      });
      navigate(`/virtualization/${dataset.id}`);
    } catch (error) {
      // Error handled by mutation
    }
  };

  return (
    <div className="virtual-dataset-create-page">
      <div className="virtual-dataset-create-header">
        <button onClick={() => navigate('/virtualization')} className="btn-back" type="button">
          ← Back to Datasets
        </button>
        <h1>Create Virtual Dataset</h1>
      </div>

      {createMutation.isError && (
        <ErrorDisplay
          error={createMutation.error}
          title="Failed to create dataset"
          onRetry={() => createMutation.reset()}
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
          <VirtualDatasetSourceBuilder
            sources={(() => {
              try {
                return JSON.parse(formData.sources || '[]') as SourceEntry[];
              } catch {
                return [];
              }
            })()}
            onChange={handleSourcesChange}
            errors={errors}
          />
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
            onClick={() => navigate('/virtualization')}
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
            {createMutation.isPending ? 'Creating...' : 'Create Dataset'}
          </button>
        </div>
      </form>
    </div>
  );
}

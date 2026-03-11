/**
 * Transformation Pipeline Create Page
 * Placeholder create form (backend returns id but does not persist)
 */

import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { apiClient } from '../../../shared/api/client';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import './TransformationPipelineCreatePage.css';

export function TransformationPipelineCreatePage() {
  const navigate = useNavigate();
  const [name, setName] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      const response = await apiClient
        .getClient()
        .post<{ id: string; name: string; status: string }>('transformation/pipelines/', {
          name: name.trim() || 'New Pipeline',
        });
      navigate(`/transformation/pipelines/${response.data.id}`);
    } catch (err) {
      setError(err instanceof Error ? err : new Error('Failed to create pipeline'));
    } finally {
      setIsSubmitting(false);
    }
  };

  if (error) {
    return (
      <div className="transformation-create-page">
        <ErrorDisplay error={error} title="Failed to create pipeline" />
      </div>
    );
  }

  return (
    <div className="transformation-create-page">
      <h1>Create Transformation Pipeline</h1>
      <form onSubmit={handleSubmit} className="transformation-create-form">
        <label htmlFor="pipeline-name">Name</label>
        <input
          id="pipeline-name"
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="New Pipeline"
        />
        <div className="form-actions">
          <button type="button" onClick={() => navigate('/transformation')}>
            Cancel
          </button>
          <button type="submit" className="btn-primary" disabled={isSubmitting}>
            {isSubmitting ? 'Creating...' : 'Create Pipeline'}
          </button>
        </div>
      </form>
    </div>
  );
}

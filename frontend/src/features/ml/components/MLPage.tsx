/**
 * ML/ODH Page
 * Displays ML models, training jobs, and inference deployments
 */

import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  useMLModels,
  useTrainingJobs,
  useInferenceDeployments,
} from '../hooks/useML';
import { LoadingSpinner } from '../../../shared/components/LoadingSpinner';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { EmptyState } from '../../../shared/components/EmptyState';
import { ModelType, ModelStatus, TrainingJobStatus, InferenceDeploymentStatus } from '../../../shared/types/ml';
import './MLPage.css';

type TabType = 'models' | 'training-jobs' | 'inference';

export function MLPage() {
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState<TabType>('models');
  const [modelTypeFilter, setModelTypeFilter] = useState<ModelType | ''>('');
  const [statusFilter, setStatusFilter] = useState<ModelStatus | TrainingJobStatus | InferenceDeploymentStatus | ''>('');

  const { data: modelsData, isLoading: modelsLoading, error: modelsError } = useMLModels({
    page_size: 50,
    model_type: modelTypeFilter || undefined,
    status: statusFilter || undefined,
  });

  const { data: trainingJobsData, isLoading: trainingLoading, error: trainingError } = useTrainingJobs({
    page_size: 50,
    status: statusFilter || undefined,
  });

  const { data: inferenceData, isLoading: inferenceLoading, error: inferenceError } = useInferenceDeployments({
    page_size: 50,
    status: statusFilter || undefined,
  });

  const handleModelClick = (id: string) => {
    navigate(`/ml/models/${id}`);
  };

  return (
    <div className="ml-page">
      <div className="ml-header">
        <h1>ML/ODH Platform</h1>
        <p className="subtitle">Manage ML models, training jobs, and inference deployments</p>
      </div>

      <div className="ml-tabs">
        <button
          className={`ml-tab ${activeTab === 'models' ? 'active' : ''}`}
          onClick={() => setActiveTab('models')}
          type="button"
        >
          Models
        </button>
        <button
          className={`ml-tab ${activeTab === 'training-jobs' ? 'active' : ''}`}
          onClick={() => setActiveTab('training-jobs')}
          type="button"
        >
          Training Jobs
        </button>
        <button
          className={`ml-tab ${activeTab === 'inference' ? 'active' : ''}`}
          onClick={() => setActiveTab('inference')}
          type="button"
        >
          Inference Deployments
        </button>
      </div>

      <div className="ml-content">
        {activeTab === 'models' && (
          <div className="models-section">
            <div className="section-header">
              <h2>ML Models</h2>
            </div>

            <div className="filters">
              <select
                value={modelTypeFilter}
                onChange={(e) => setModelTypeFilter(e.target.value as ModelType | '')}
                className="filter-select"
              >
                <option value="">All Types</option>
                {Object.values(ModelType).map(type => (
                  <option key={type} value={type}>{type}</option>
                ))}
              </select>
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value as ModelStatus | '')}
                className="filter-select"
              >
                <option value="">All Status</option>
                {Object.values(ModelStatus).map(status => (
                  <option key={status} value={status}>{status}</option>
                ))}
              </select>
            </div>

            {modelsLoading && <LoadingSpinner message="Loading models..." />}
            {modelsError && <ErrorDisplay error={modelsError} title="Failed to load models" />}
            {modelsData && modelsData.results.length === 0 && (
              <EmptyState title="No models found" message="Create or link your first ML model." />
            )}
            {modelsData && modelsData.results.length > 0 && (
              <div className="models-list">
                {modelsData.results.map(model => (
                  <div
                    key={model.id}
                    className="model-card"
                    onClick={() => handleModelClick(model.id)}
                  >
                    <div className="model-header">
                      <h3>{model.odh_model_name}</h3>
                      <span className={`status-badge status-${model.status.toLowerCase()}`}>
                        {model.status}
                      </span>
                    </div>
                    <div className="model-meta">
                      <span>Version: {model.odh_model_version}</span>
                      <span>Type: {model.model_type}</span>
                      {model.asset_id && <span>Linked to Asset</span>}
                    </div>
                    <div className="model-id">ODH ID: {model.odh_model_id}</div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {activeTab === 'training-jobs' && (
          <div className="training-jobs-section">
            <div className="section-header">
              <h2>Training Jobs</h2>
            </div>

            <div className="filters">
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value as TrainingJobStatus | '')}
                className="filter-select"
              >
                <option value="">All Status</option>
                {Object.values(TrainingJobStatus).map(status => (
                  <option key={status} value={status}>{status}</option>
                ))}
              </select>
            </div>

            {trainingLoading && <LoadingSpinner message="Loading training jobs..." />}
            {trainingError && <ErrorDisplay error={trainingError} title="Failed to load training jobs" />}
            {trainingJobsData && trainingJobsData.results.length === 0 && (
              <EmptyState title="No training jobs" message="Submit your first training job to get started." />
            )}
            {trainingJobsData && trainingJobsData.results.length > 0 && (
              <div className="training-jobs-list">
                {trainingJobsData.results.map(job => (
                  <div key={job.id} className="job-card">
                    <div className="job-header">
                      <h3>Training Job {job.id.substring(0, 8)}...</h3>
                      <span className={`status-badge status-${job.status.toLowerCase()}`}>
                        {job.status}
                      </span>
                    </div>
                    <div className="job-meta">
                      <span>Model: {job.model_id.substring(0, 8)}...</span>
                      <span>Dataset: {job.dataset_id.substring(0, 8)}...</span>
                      {job.started_at && (
                        <span>Started: {new Date(job.started_at).toLocaleString()}</span>
                      )}
                      {job.completed_at && (
                        <span>Completed: {new Date(job.completed_at).toLocaleString()}</span>
                      )}
                    </div>
                    {job.error_message && (
                      <div className="job-error">Error: {job.error_message}</div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {activeTab === 'inference' && (
          <div className="inference-section">
            <div className="section-header">
              <h2>Inference Deployments</h2>
            </div>

            <div className="filters">
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value as InferenceDeploymentStatus | '')}
                className="filter-select"
              >
                <option value="">All Status</option>
                {Object.values(InferenceDeploymentStatus).map(status => (
                  <option key={status} value={status}>{status}</option>
                ))}
              </select>
            </div>

            {inferenceLoading && <LoadingSpinner message="Loading inference deployments..." />}
            {inferenceError && <ErrorDisplay error={inferenceError} title="Failed to load inference deployments" />}
            {inferenceData && inferenceData.results.length === 0 && (
              <EmptyState title="No inference deployments" message="Deploy your first model for inference." />
            )}
            {inferenceData && inferenceData.results.length > 0 && (
              <div className="inference-list">
                {inferenceData.results.map(deployment => (
                  <div key={deployment.id} className="deployment-card">
                    <div className="deployment-header">
                      <h3>Deployment {deployment.id.substring(0, 8)}...</h3>
                      <span className={`status-badge status-${deployment.status.toLowerCase()}`}>
                        {deployment.status}
                      </span>
                    </div>
                    <div className="deployment-meta">
                      <span>Model: {deployment.model_id.substring(0, 8)}...</span>
                      {deployment.replicas && <span>Replicas: {deployment.replicas}</span>}
                      {deployment.endpoint && (
                        <a href={deployment.endpoint} target="_blank" rel="noopener noreferrer">
                          Endpoint: {deployment.endpoint}
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

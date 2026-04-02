/**
 * Transformation Pipeline Create Page
 * Form with name, description, version, and step composer
 */

import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { Button } from '../../../shared/components/Button';
import { Breadcrumbs } from '../../../shared/components/Breadcrumbs';
import { useCreateTransformationPipeline } from '../hooks/useTransformationPipelines';
import type { PipelineStep } from '../../../shared/types/transformation';
import './TransformationPipelineCreatePage.css';

const STEP_TYPES = ['filter', 'aggregate', 'transform', 'join', 'output', 'sql'] as const;

interface StepFormEntry {
  key: number;
  name: string;
  type: string;
  configJson: string;
}

let stepKeyCounter = 0;

function createEmptyStep(): StepFormEntry {
  stepKeyCounter += 1;
  return { key: stepKeyCounter, name: '', type: 'filter', configJson: '{}' };
}

export function TransformationPipelineCreatePage() {
  const navigate = useNavigate();
  const createMutation = useCreateTransformationPipeline();

  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [version, setVersion] = useState('1.0.0');
  const [steps, setSteps] = useState<StepFormEntry[]>([createEmptyStep()]);
  const [validationError, setValidationError] = useState<string | null>(null);

  const addStep = () => {
    setSteps((prev) => [...prev, createEmptyStep()]);
  };

  const removeStep = (key: number) => {
    setSteps((prev) => prev.filter((s) => s.key !== key));
  };

  const updateStep = (key: number, field: keyof StepFormEntry, value: string) => {
    setSteps((prev) =>
      prev.map((s) => (s.key === key ? { ...s, [field]: value } : s)),
    );
  };

  const moveStep = (index: number, direction: -1 | 1) => {
    const newIndex = index + direction;
    if (newIndex < 0 || newIndex >= steps.length) return;
    const updated = [...steps];
    [updated[index], updated[newIndex]] = [updated[newIndex], updated[index]];
    setSteps(updated);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setValidationError(null);

    if (!name.trim()) {
      setValidationError('Pipeline name is required.');
      return;
    }

    // Parse step configs
    const parsedSteps: PipelineStep[] = [];
    for (let i = 0; i < steps.length; i++) {
      const step = steps[i];
      if (!step.name.trim()) {
        setValidationError(`Step ${i + 1} requires a name.`);
        return;
      }
      let config: Record<string, unknown> = {};
      try {
        config = JSON.parse(step.configJson || '{}');
      } catch {
        setValidationError(`Step ${i + 1} ("${step.name}") has invalid JSON config.`);
        return;
      }
      parsedSteps.push({
        name: step.name.trim(),
        type: step.type,
        config,
      });
    }

    createMutation.mutate(
      {
        name: name.trim(),
        description: description.trim() || undefined,
        version: version.trim() || '1.0.0',
        pipeline_definition: {
          version: version.trim() || '1.0.0',
          steps: parsedSteps,
        },
      },
      {
        onSuccess: (data) => {
          navigate(`/transformation/pipelines/${data.id}`);
        },
      },
    );
  };

  return (
    <div className="transformation-create-page">
      <Breadcrumbs
        items={[
          { label: 'Home', href: '/' },
          { label: 'Transformations', href: '/transformation' },
          { label: 'Create Pipeline' },
        ]}
      />

      <h1>Create Transformation Pipeline</h1>

      {validationError && (
        <div className="transformation-create-validation-error" role="alert">
          {validationError}
        </div>
      )}

      {createMutation.isError && (
        <ErrorDisplay
          error={createMutation.error as Error}
          title="Failed to create pipeline"
        />
      )}

      <form onSubmit={handleSubmit} className="transformation-create-form">
        <div className="form-field">
          <label htmlFor="pipeline-name">Name *</label>
          <input
            id="pipeline-name"
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="My Pipeline"
            required
          />
        </div>

        <div className="form-field">
          <label htmlFor="pipeline-description">Description</label>
          <textarea
            id="pipeline-description"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Describe what this pipeline does..."
            rows={3}
          />
        </div>

        <div className="form-field">
          <label htmlFor="pipeline-version">Version</label>
          <input
            id="pipeline-version"
            type="text"
            value={version}
            onChange={(e) => setVersion(e.target.value)}
            placeholder="1.0.0"
          />
        </div>

        <div className="step-composer">
          <div className="step-composer-header">
            <h2>Pipeline Steps</h2>
            <Button type="button" variant="secondary" onClick={addStep}>
              Add Step
            </Button>
          </div>

          {steps.length === 0 && (
            <p className="step-composer-empty">No steps added. Add at least one step.</p>
          )}

          {steps.map((step, index) => (
            <div key={step.key} className="step-card">
              <div className="step-card-header">
                <span className="step-number">Step {index + 1}</span>
                <div className="step-card-actions">
                  <button
                    type="button"
                    className="step-move-btn"
                    onClick={() => moveStep(index, -1)}
                    disabled={index === 0}
                    aria-label="Move step up"
                    title="Move up"
                  >
                    &uarr;
                  </button>
                  <button
                    type="button"
                    className="step-move-btn"
                    onClick={() => moveStep(index, 1)}
                    disabled={index === steps.length - 1}
                    aria-label="Move step down"
                    title="Move down"
                  >
                    &darr;
                  </button>
                  <button
                    type="button"
                    className="step-remove-btn"
                    onClick={() => removeStep(step.key)}
                    aria-label={`Remove step ${index + 1}`}
                    title="Remove step"
                  >
                    &times;
                  </button>
                </div>
              </div>

              <div className="step-card-fields">
                <div className="form-field">
                  <label htmlFor={`step-name-${step.key}`}>Step Name *</label>
                  <input
                    id={`step-name-${step.key}`}
                    type="text"
                    value={step.name}
                    onChange={(e) => updateStep(step.key, 'name', e.target.value)}
                    placeholder="e.g. Filter invalid rows"
                  />
                </div>

                <div className="form-field">
                  <label htmlFor={`step-type-${step.key}`}>Type</label>
                  <select
                    id={`step-type-${step.key}`}
                    value={step.type}
                    onChange={(e) => updateStep(step.key, 'type', e.target.value)}
                  >
                    {STEP_TYPES.map((t) => (
                      <option key={t} value={t}>
                        {t.charAt(0).toUpperCase() + t.slice(1)}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="form-field">
                  <label htmlFor={`step-config-${step.key}`}>
                    Config (JSON){step.type === 'sql' ? ' / SQL query' : ''}
                  </label>
                  <textarea
                    id={`step-config-${step.key}`}
                    className="step-config-textarea"
                    value={step.configJson}
                    onChange={(e) => updateStep(step.key, 'configJson', e.target.value)}
                    placeholder={
                      step.type === 'sql'
                        ? '{"query": "SELECT * FROM source WHERE active = true"}'
                        : '{}'
                    }
                    rows={4}
                    spellCheck={false}
                  />
                </div>
              </div>
            </div>
          ))}
        </div>

        <div className="form-actions">
          <button type="button" onClick={() => navigate('/transformation')}>
            Cancel
          </button>
          <Button type="submit" variant="primary" disabled={createMutation.isPending}>
            {createMutation.isPending ? 'Creating...' : 'Create Pipeline'}
          </Button>
        </div>
      </form>
    </div>
  );
}

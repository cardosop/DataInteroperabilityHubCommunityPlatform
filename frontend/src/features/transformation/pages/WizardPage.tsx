/**
 * 285.9.4.1 — TransformationPipelineWizard guided setup flow.
 *
 * Steps: Choose direction → Configure dbt project → Review contract /
 * Download scaffold → Execute pipeline.
 */
import React, { useCallback, useState } from 'react';
import { useParams } from 'react-router-dom';
import { useTransformationWizard } from '../hooks/useTransformationWizard';
import { WizardDirectionPicker } from '../components/WizardDirectionPicker';
import { WizardDbtConfig } from '../components/WizardDbtConfig';
import { WizardReviewStep } from '../components/WizardReviewStep';
import './WizardPage.css';

type WizardStep = 'direction' | 'config' | 'review' | 'executing';

export function WizardPage(): React.ReactElement {
  const { id: pipelineId } = useParams<{ id: string }>();
  const [step, setStep] = useState<WizardStep>('direction');
  const { state, update, submit, loading, error } = useTransformationWizard(pipelineId!);

  const handleDirection = useCallback(
    (dir: 'code-first' | 'contract-first') => {
      update('direction', dir);
      setStep('config');
    },
    [update],
  );

  const handleConfig = useCallback(
    (config: Record<string, unknown>) => {
      update('config', config);
      setStep('review');
    },
    [update],
  );

  const handleExecute = useCallback(async () => {
    setStep('executing');
    await submit();
  }, [submit]);

  if (loading) return <div aria-busy="true">Loading pipeline config...</div>;

  return (
    <div className="transformation-wizard" role="region" aria-label="Pipeline setup wizard">
      <h1>Pipeline Setup Wizard</h1>

      {step === 'direction' && (
        <WizardDirectionPicker
          current={state.direction}
          onSelect={handleDirection}
        />
      )}

      {step === 'config' && (
        <WizardDbtConfig
          pipelineId={pipelineId!}
          onSubmit={handleConfig}
          onBack={() => setStep('direction')}
        />
      )}

      {step === 'review' && (
        <WizardReviewStep
          direction={state.direction}
          config={state.config}
          pipelineId={pipelineId!}
          onExecute={handleExecute}
          onBack={() => setStep('config')}
        />
      )}

      {step === 'executing' && (
        <div aria-live="polite">Executing pipeline... Redirecting to run detail...</div>
      )}

      {error && <div role="alert" className="error">{error}</div>}
    </div>
  );
}

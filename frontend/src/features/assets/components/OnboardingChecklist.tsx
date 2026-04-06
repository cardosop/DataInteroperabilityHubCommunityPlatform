/**
 * Onboarding Checklist Component
 * Shows a 6-step checklist for DRAFT assets guiding users through activation prerequisites.
 * Each step dynamically reflects the current state of the asset and its linked resources.
 */

import { useNavigate } from 'react-router-dom';
import type { Contract } from '../../../shared/types/contracts';
import type { Dataset } from '../../../shared/types/datasets';
import './OnboardingChecklist.css';

export interface OnboardingChecklistProps {
  contracts: Contract[];
  datasets: Dataset[];
  dqStatus: string;
  complianceStatus: string;
  assetId?: string;
  datasetId?: string;
  onRunDQ?: () => void;
  onRunCompliance?: () => void;
}

interface ChecklistStep {
  key: string;
  label: string;
  description: string;
  completed: boolean;
  actionLabel?: string;
  onAction?: () => void;
}

function getSteps(
  contracts: Contract[],
  datasets: Dataset[],
  dqStatus: string,
  complianceStatus: string,
  navigate: (path: string) => void,
  onRunDQ?: () => void,
  onRunCompliance?: () => void,
): ChecklistStep[] {
  const hasContract = contracts.length > 0;
  const hasActiveContract = contracts.some(
    (c) =>
      c.normalization_status === 'NORMALIZED_OK' ||
      c.normalization_status === 'NORMALIZED_WITH_WARNINGS'
  );
  const hasValidContract = contracts.some(
    (c) => c.validation_status === 'VALID' || c.validation_status === 'WARNING_ONLY'
  );
  const hasDataset = datasets.length > 0;
  const dqPassed = dqStatus === 'PASS' || dqStatus === 'PASSED' || dqStatus === 'WARN' || dqStatus === 'WARNING';
  const compliancePassed =
    complianceStatus === 'PASS' ||
    complianceStatus === 'PASSED' ||
    complianceStatus === 'COMPLIANT' ||
    complianceStatus === 'WARN' ||
    complianceStatus === 'WARNING';

  return [
    {
      key: 'create-asset',
      label: '1. Create Asset',
      description: 'Asset has been created in DRAFT status.',
      completed: true, // always true on this page
    },
    {
      key: 'attach-contract',
      label: '2. Attach Contract',
      description: hasContract
        ? `${contracts.length} contract(s) linked.`
        : 'Link a data contract to define schema and rules.',
      completed: hasContract,
      actionLabel: hasContract ? undefined : 'Attach Contract',
      onAction: hasContract
        ? undefined
        : () => {
            const section = document.querySelector(
              '[data-testid="asset-contracts-section"]'
            );
            const stepEl = document.querySelector(
              '[data-testid="onboarding-step-attach-contract"]'
            );
            (section ?? stepEl)?.scrollIntoView({ behavior: 'smooth' });
          },
    },
    {
      key: 'validate-contract',
      label: '3. Validate & Normalize Contract',
      description: hasActiveContract && hasValidContract
        ? 'Contract is normalized and validated.'
        : hasContract
          ? 'Contract needs validation or normalization.'
          : 'Attach a contract first.',
      completed: hasActiveContract && hasValidContract,
      actionLabel:
        hasContract && !(hasActiveContract && hasValidContract)
          ? 'View Contract'
          : undefined,
      onAction:
        hasContract && !(hasActiveContract && hasValidContract)
          ? () => navigate(`/contracts/${contracts[0].id}`)
          : undefined,
    },
    {
      key: 'upload-dataset',
      label: '4. Upload Dataset',
      description: hasDataset
        ? `${datasets.length} dataset(s) linked.`
        : 'Upload a file to create a dataset (optional for contract-only assets).',
      completed: hasDataset,
      actionLabel: hasDataset ? undefined : 'Upload File',
      onAction: hasDataset
        ? undefined
        : () => {
            const section = document.querySelector(
              '[data-testid="asset-upload-section"]'
            );
            const stepEl = document.querySelector(
              '[data-testid="onboarding-step-upload-dataset"]'
            );
            (section ?? stepEl)?.scrollIntoView({ behavior: 'smooth' });
          },
    },
    {
      key: 'run-dq',
      label: '5. Pass Data Quality Check',
      description: dqPassed
        ? 'DQ check passed.'
        : hasDataset
          ? 'Run a DQ check on your dataset.'
          : 'Upload a dataset first (or skip for contract-only assets).',
      completed: dqPassed || (!hasDataset && hasContract),
      actionLabel: hasDataset && !dqPassed ? 'Run DQ Check' : undefined,
      onAction: hasDataset && !dqPassed ? onRunDQ : undefined,
    },
    {
      key: 'run-compliance',
      label: '6. Pass Compliance Check',
      description: compliancePassed
        ? 'Compliance check passed.'
        : hasDataset
          ? 'Run a compliance scan on your dataset.'
          : 'Upload a dataset first (or skip for contract-only assets).',
      completed: compliancePassed || (!hasDataset && hasContract),
      actionLabel: hasDataset && !compliancePassed ? 'Run Compliance Scan' : undefined,
      onAction: hasDataset && !compliancePassed ? onRunCompliance : undefined,
    },
  ];
}

export function OnboardingChecklist({
  contracts,
  datasets,
  dqStatus,
  complianceStatus,
  onRunDQ,
  onRunCompliance,
}: OnboardingChecklistProps) {
  const navigate = useNavigate();
  const steps = getSteps(contracts, datasets, dqStatus, complianceStatus, navigate, onRunDQ, onRunCompliance);
  const completedCount = steps.filter((s) => s.completed).length;
  const progressPercent = Math.round((completedCount / steps.length) * 100);

  return (
    <div className="onboarding-checklist" data-testid="onboarding-checklist">
      <div className="onboarding-checklist-header">
        <h2>Activation Checklist</h2>
        <span className="onboarding-progress" data-testid="onboarding-progress">
          {completedCount}/{steps.length} completed
        </span>
      </div>
      <div className="onboarding-progress-bar">
        <div
          className="onboarding-progress-fill"
          style={{ width: `${progressPercent}%` }}
          data-testid="onboarding-progress-bar"
        />
      </div>
      <ol className="onboarding-steps" data-testid="onboarding-steps">
        {steps.map((step) => (
          <li
            key={step.key}
            className={`onboarding-step ${step.completed ? 'completed' : 'pending'}`}
            data-testid={`onboarding-step-${step.key}`}
          >
            <span className="onboarding-step-icon" aria-hidden="true">
              {step.completed ? '\u2713' : '\u25CB'}
            </span>
            <div className="onboarding-step-content">
              <span className="onboarding-step-label">{step.label}</span>
              <span className="onboarding-step-desc">{step.description}</span>
            </div>
            {step.actionLabel && step.onAction && (
              <button
                type="button"
                className="onboarding-step-action"
                onClick={step.onAction}
                data-testid={`onboarding-action-${step.key}`}
              >
                {step.actionLabel}
              </button>
            )}
          </li>
        ))}
      </ol>
    </div>
  );
}

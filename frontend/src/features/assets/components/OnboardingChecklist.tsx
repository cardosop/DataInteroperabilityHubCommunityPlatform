/**
 * Onboarding Checklist Component
 *
 * Shows the activation checklist for DRAFT assets, guiding users through
 * each prerequisite with an inline action (link or button) and marking
 * each step as Required or Optional so the visual hierarchy tells users
 * what they *must* do to activate vs. what is nice-to-have.
 */

import { Link, useNavigate } from 'react-router-dom';
import type { Contract } from '../../../shared/types/contracts';
import type { Dataset } from '../../../shared/types/datasets';
import { useAssetWorkflowStatus } from '../hooks/useAssetWorkflowStatus';
import { WorkflowProgressWidget } from './WorkflowProgressWidget';
import './OnboardingChecklist.css';

export interface OnboardingChecklistProps {
  contracts: Contract[];
  datasets: Dataset[];
  dqStatus: string;
  complianceStatus: string;
  assetId?: string;
  datasetId?: string;
  /**
   * Phase 250.6.C — when set, embeds the `<WorkflowProgressWidget>`
   * at the TOP of the checklist (before the per-step rows) so the
   * user sees BOTH "what's still RUNNING" and "what's left to do
   * once it completes". Pass the workflow_instance_id returned by
   * the data-first endpoint OR by the create-asset mutation.
   * Polling stops automatically when the workflow reaches a
   * terminal state (COMPLETED / FAILED), so it's safe to leave the
   * prop set after the workflow finishes — the widget will surface
   * the terminal state and the hook stops polling.
   */
  workflowInstanceId?: string | null;
  onRunDQ?: () => void;
  onRunCompliance?: () => void;
  /** Called when the user clicks the final "Activate" step. */
  onActivate?: () => void;
  /** Disables the Activate action while a mutation is in flight. */
  isActivating?: boolean;
}

type ActionKind =
  | { kind: 'link'; to: string }
  | { kind: 'button'; onClick: () => void; disabled?: boolean };

interface ChecklistStep {
  key: string;
  label: string;
  description: string;
  completed: boolean;
  /** True for hard prerequisites, false for recommended-but-skippable. */
  required: boolean;
  actionLabel?: string;
  action?: ActionKind;
}

function getSteps(args: {
  contracts: Contract[];
  datasets: Dataset[];
  dqStatus: string;
  complianceStatus: string;
  assetId?: string;
  navigate: (path: string) => void;
  onRunDQ?: () => void;
  onRunCompliance?: () => void;
  onActivate?: () => void;
  isActivating?: boolean;
}): ChecklistStep[] {
  const {
    contracts,
    datasets,
    dqStatus,
    complianceStatus,
    assetId,
    navigate,
    onRunDQ,
    onRunCompliance,
    onActivate,
    isActivating,
  } = args;

  const hasContract = contracts.length > 0;
  const hasActiveContract = contracts.some(
    (c) =>
      c.normalization_status === 'NORMALIZED_OK' ||
      c.normalization_status === 'NORMALIZED_WITH_WARNINGS',
  );
  const hasValidContract = contracts.some(
    (c) => c.validation_status === 'VALID' || c.validation_status === 'WARNING_ONLY',
  );
  const hasDataset = datasets.length > 0;
  const dqPassed =
    dqStatus === 'PASS' ||
    dqStatus === 'PASSED' ||
    dqStatus === 'WARN' ||
    dqStatus === 'WARNING';
  const compliancePassed =
    complianceStatus === 'PASS' ||
    complianceStatus === 'PASSED' ||
    complianceStatus === 'COMPLIANT' ||
    complianceStatus === 'WARN' ||
    complianceStatus === 'WARNING';

  // An asset is eligible for activation once the Required steps are done.
  // Contract-only assets can activate without Upload/DQ/Compliance (matches
  // step 5/6 "completed for contract-only asset" logic below).
  const contractReady = hasContract && hasActiveContract && hasValidContract;
  const dataReady = hasDataset ? dqPassed && compliancePassed : hasContract;
  const canActivate = contractReady && dataReady;

  const attachContractAction: ActionKind | undefined = hasContract
    ? undefined
    : assetId
      ? { kind: 'link', to: `/contracts/create?asset_id=${assetId}` }
      : {
          kind: 'button',
          onClick: () => {
            const section = document.querySelector(
              '[data-testid="asset-contracts-section"]',
            );
            const stepEl = document.querySelector(
              '[data-testid="onboarding-step-attach-contract"]',
            );
            (section ?? stepEl)?.scrollIntoView({ behavior: 'smooth' });
          },
        };

  return [
    {
      key: 'create-asset',
      label: '1. Create Asset',
      description: 'Asset has been created in DRAFT status.',
      completed: true,
      required: true,
    },
    {
      key: 'attach-contract',
      label: '2. Attach Contract',
      description: hasContract
        ? `${contracts.length} contract(s) linked.`
        : 'Link a data contract to define schema and rules.',
      completed: hasContract,
      required: true,
      actionLabel: hasContract ? undefined : 'Attach Contract',
      action: attachContractAction,
    },
    {
      key: 'validate-contract',
      label: '3. Validate & Normalize Contract',
      description:
        hasActiveContract && hasValidContract
          ? 'Contract is normalized and validated.'
          : hasContract
            ? 'Contract needs validation or normalization.'
            : 'Attach a contract first.',
      completed: hasActiveContract && hasValidContract,
      required: true,
      actionLabel:
        hasContract && !(hasActiveContract && hasValidContract)
          ? 'View Contract'
          : undefined,
      action:
        hasContract && !(hasActiveContract && hasValidContract)
          ? { kind: 'button', onClick: () => navigate(`/contracts/${contracts[0].id}`) }
          : undefined,
    },
    {
      key: 'upload-dataset',
      label: '4. Upload Dataset',
      description: hasDataset
        ? `${datasets.length} dataset(s) linked.`
        : 'Upload a file to create a dataset (optional for contract-only assets).',
      completed: hasDataset,
      required: false,
      actionLabel: hasDataset ? undefined : 'Upload File',
      action: hasDataset
        ? undefined
        : {
            kind: 'button',
            onClick: () => {
              const section = document.querySelector(
                '[data-testid="asset-upload-section"]',
              );
              const stepEl = document.querySelector(
                '[data-testid="onboarding-step-upload-dataset"]',
              );
              (section ?? stepEl)?.scrollIntoView({ behavior: 'smooth' });
            },
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
      required: false,
      actionLabel: hasDataset && !dqPassed ? 'Run DQ Check' : undefined,
      action:
        hasDataset && !dqPassed && onRunDQ
          ? { kind: 'button', onClick: onRunDQ }
          : undefined,
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
      required: false,
      actionLabel: hasDataset && !compliancePassed ? 'Run Compliance Scan' : undefined,
      action:
        hasDataset && !compliancePassed && onRunCompliance
          ? { kind: 'button', onClick: onRunCompliance }
          : undefined,
    },
    {
      key: 'activate',
      label: '7. Activate Asset',
      description: canActivate
        ? 'All required prerequisites complete — activate to make this asset live.'
        : 'Finish the required steps above, then activate.',
      completed: false,
      required: true,
      actionLabel: 'Activate',
      action: onActivate
        ? {
            kind: 'button',
            onClick: onActivate,
            disabled: !canActivate || !!isActivating,
          }
        : undefined,
    },
  ];
}

function StepAction({ step }: { step: ChecklistStep }) {
  if (!step.action || !step.actionLabel) return null;
  const testId = `onboarding-action-${step.key}`;
  if (step.action.kind === 'link') {
    return (
      <Link
        to={step.action.to}
        className="onboarding-step-action"
        data-testid={testId}
      >
        {step.actionLabel}
      </Link>
    );
  }
  return (
    <button
      type="button"
      className="onboarding-step-action"
      onClick={step.action.onClick}
      disabled={step.action.disabled}
      data-testid={testId}
    >
      {step.actionLabel}
    </button>
  );
}

export function OnboardingChecklist({
  contracts,
  datasets,
  dqStatus,
  complianceStatus,
  assetId,
  workflowInstanceId,
  onRunDQ,
  onRunCompliance,
  onActivate,
  isActivating,
}: OnboardingChecklistProps) {
  const navigate = useNavigate();
  // Phase 250.6.C — workflow status polling. The hook is gated on
  // `workflowInstanceId` being truthy (its `enabled` option), so when
  // the prop is absent / null the hook is a no-op and no network
  // traffic fires. Same `gcTime: 60_000` memory-leak guard applies
  // — the cache entry GC's 60s after last subscriber unmounts.
  const workflowStatusQuery = useAssetWorkflowStatus(workflowInstanceId);

  const steps = getSteps({
    contracts,
    datasets,
    dqStatus,
    complianceStatus,
    assetId,
    navigate,
    onRunDQ,
    onRunCompliance,
    onActivate,
    isActivating,
  });
  // Progress excludes the terminal "Activate" step so the bar reflects
  // *prerequisite* completion, not whether the user has clicked Activate.
  const prereqSteps = steps.filter((s) => s.key !== 'activate');
  const completedCount = prereqSteps.filter((s) => s.completed).length;
  const progressPercent = Math.round((completedCount / prereqSteps.length) * 100);

  return (
    <div className="onboarding-checklist" data-testid="onboarding-checklist">
      {/*
       * Phase 250.6.C.2 — workflow progress widget rendered ABOVE the
       * checklist when ``workflowInstanceId`` is set. The widget shows
       * the live RUNNING status (step + progress + ETA); the checklist
       * below shows the post-COMPLETED prerequisites the user still
       * needs to walk through to activate.
       */}
      {workflowInstanceId && (
        <WorkflowProgressWidget
          data={workflowStatusQuery.data}
          isLoading={workflowStatusQuery.isLoading}
          isError={workflowStatusQuery.isError}
          className="onboarding-checklist__workflow-widget"
        />
      )}
      <div className="onboarding-checklist-header">
        <h2>Activation Checklist</h2>
        <span className="onboarding-progress" data-testid="onboarding-progress">
          {completedCount}/{prereqSteps.length} completed
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
            className={[
              'onboarding-step',
              step.completed ? 'completed' : 'pending',
              step.required ? 'onboarding-step--required' : 'onboarding-step--optional',
            ].join(' ')}
            data-testid={`onboarding-step-${step.key}`}
            data-required={step.required ? 'true' : 'false'}
          >
            <span className="onboarding-step-icon" aria-hidden="true">
              {step.completed ? '\u2713' : '\u25CB'}
            </span>
            <div className="onboarding-step-content">
              <span className="onboarding-step-label">
                {step.label}
                {!step.required && (
                  <span className="onboarding-step-optional-tag"> (optional)</span>
                )}
              </span>
              <span className="onboarding-step-desc">{step.description}</span>
            </div>
            <StepAction step={step} />
          </li>
        ))}
      </ol>
    </div>
  );
}

/**
 * Phase 272.4 — MultiStepApprovalIndicator
 *
 * Renders the multi-step approval chain progress for an access request.
 * Each step shows: step label, step role, and status (completed/current/pending).
 */
import './MultiStepApprovalIndicator.css';

interface ApprovalStep {
  step: number;
  role: string;
  label: string;
}

interface Props {
  chain: ApprovalStep[] | null;
  currentStep: number;
  status: string;
}

export function MultiStepApprovalIndicator({ chain, currentStep, status }: Props) {
  if (!chain || chain.length === 0) return null;

  const isTerminal = status === 'APPROVED' || status === 'REJECTED'
    || status === 'REVOKED' || status === 'EXPIRED';

  return (
    <div className="multi-step-indicator" data-testid="multi-step-indicator">
      <h4>Approval Progress</h4>
      <ol className="step-list">
        {chain.map((s, i) => {
          let stepState: 'completed' | 'current' | 'pending';
          if (isTerminal && i < chain.length) {
            stepState = 'completed';
          } else if (i < currentStep) {
            stepState = 'completed';
          } else if (i === currentStep) {
            stepState = 'current';
          } else {
            stepState = 'pending';
          }
          return (
            <li
              key={s.step}
              className={`step-item step-${stepState}`}
              data-testid={`step-${stepState}`}
            >
              <span className="step-number">{s.step + 1}</span>
              <span className="step-label">{s.label}</span>
              <span className="step-role">{s.role}</span>
            </li>
          );
        })}
      </ol>
    </div>
  );
}

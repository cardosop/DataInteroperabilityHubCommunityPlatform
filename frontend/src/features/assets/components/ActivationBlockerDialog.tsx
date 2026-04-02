/**
 * Activation Blocker Dialog
 * Displayed when asset activation returns ASSET_ACTIVATION_BLOCKED.
 * Parses the blocker list from the API response and shows actionable items.
 */

import { useNavigate } from 'react-router-dom';
import { Button } from '../../../shared/components/Button';
import './ActivationBlockerDialog.css';

export interface ActivationBlockerDialogProps {
  blockers: string[];
  assetId: string;
  onDismiss: () => void;
}

interface ParsedBlocker {
  message: string;
  actionLabel?: string;
  actionPath?: string;
}

interface ParsedBlockerWithScroll extends ParsedBlocker {
  scrollTarget?: string;
}

function parseBlocker(blocker: string, assetId: string): ParsedBlockerWithScroll {
  const lower = blocker.toLowerCase();

  if (lower.includes('active contract')) {
    return {
      message: blocker,
      actionLabel: 'Attach Contract',
      actionPath: `/assets/${assetId}`,
    };
  }

  if (lower.includes('validation_status')) {
    return {
      message: blocker,
      actionLabel: 'Validate Contract',
      scrollTarget: '[data-testid="asset-contracts-section"]',
    };
  }

  if (lower.includes('normalization_status')) {
    return {
      message: blocker,
      actionLabel: 'View Contract',
      scrollTarget: '[data-testid="asset-contracts-section"]',
    };
  }

  if (lower.includes('dq_status')) {
    return {
      message: blocker,
      actionLabel: 'Run DQ Check',
      scrollTarget: '.asset-quality-gates-section',
    };
  }

  if (lower.includes('compliance_status')) {
    return {
      message: blocker,
      actionLabel: 'Run Compliance Check',
      scrollTarget: '.asset-quality-gates-section',
    };
  }

  return { message: blocker };
}

/**
 * Extracts blocker list from an activation error.
 * Handles the normalized ApiError shape from the client interceptor:
 *   { error: { code: 'ASSET_ACTIVATION_BLOCKED', details: string[] | Record<string, unknown> } }
 * Also handles the raw axios error shape for resilience.
 */
export function extractBlockersFromError(err: unknown): string[] | null {
  if (!err || typeof err !== 'object') return null;

  // Normalized ApiError shape: { error: { code, details } }
  const apiErr = err as {
    error?: { code?: string; details?: unknown };
    response?: { data?: { code?: string; details?: unknown } };
  };

  // Check normalized shape first
  if (apiErr.error?.code === 'ASSET_ACTIVATION_BLOCKED') {
    const details = apiErr.error.details;
    if (Array.isArray(details)) return details as string[];
    if (details && typeof details === 'object') {
      return Object.values(details).flat().map(String);
    }
    return [apiErr.error.code];
  }

  // Fallback: raw axios response shape
  const raw = apiErr.response?.data;
  if (raw && typeof raw === 'object') {
    const data = raw as { code?: string; details?: unknown };
    if (data.code === 'ASSET_ACTIVATION_BLOCKED') {
      const details = data.details;
      if (Array.isArray(details)) return details as string[];
      if (details && typeof details === 'object') {
        return Object.values(details).flat().map(String);
      }
      return [data.code];
    }
  }

  return null;
}

export function ActivationBlockerDialog({
  blockers,
  assetId,
  onDismiss,
}: ActivationBlockerDialogProps) {
  const navigate = useNavigate();
  const parsed = blockers.map((b) => parseBlocker(b, assetId));

  return (
    <div
      className="activation-blocker-overlay"
      data-testid="activation-blocker-dialog"
      role="dialog"
      aria-modal="true"
      aria-labelledby="activation-blocker-title"
      onClick={(e) => {
        if (e.target === e.currentTarget) onDismiss();
      }}
    >
      <div className="activation-blocker-dialog">
        <h2 id="activation-blocker-title">Activation Blocked</h2>
        <p className="activation-blocker-subtitle">
          The following requirements must be met before this asset can be activated:
        </p>
        <ul className="activation-blocker-list" data-testid="activation-blocker-list">
          {parsed.map((item, idx) => (
            <li key={idx} className="activation-blocker-item" data-testid={`blocker-item-${idx}`}>
              <span className="blocker-icon" aria-hidden="true">
                &#x2717;
              </span>
              <span className="blocker-message">{item.message}</span>
              {item.actionLabel && (item.actionPath || item.scrollTarget) && (
                <button
                  type="button"
                  className="blocker-action"
                  onClick={() => {
                    onDismiss();
                    if (item.actionPath) {
                      navigate(item.actionPath);
                    } else if (item.scrollTarget) {
                      const el = document.querySelector(item.scrollTarget);
                      el?.scrollIntoView({ behavior: 'smooth' });
                    }
                  }}
                  data-testid={`blocker-action-${idx}`}
                >
                  {item.actionLabel}
                </button>
              )}
            </li>
          ))}
        </ul>
        <div className="activation-blocker-footer">
          <Button variant="secondary" onClick={onDismiss} data-testid="blocker-dismiss">
            Close
          </Button>
        </div>
      </div>
    </div>
  );
}

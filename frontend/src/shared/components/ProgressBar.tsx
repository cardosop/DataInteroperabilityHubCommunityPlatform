/**
 * ProgressBar — reusable progress indicator for async operations (278.F.4).
 *
 * Supports: determinate (percentage), indeterminate (no known end),
 * loading skeleton, error state, complete state.  Accessible via
 * ``role="progressbar"`` + aria attributes.
 */
import type { FC } from 'react';
import './ProgressBar.css';

export interface ProgressBarProps {
  /** 0-100 percentage. When null/undefined → indeterminate animation. */
  percentage?: number | null;
  /** Label for the current step or operation. */
  label?: string;
  /** Height variant. */
  size?: 'sm' | 'md' | 'lg';
  /** Show the percentage text inside/next to the bar. */
  showPercentage?: boolean;
  /** Error state — shows red bar with error message. */
  error?: string | null;
  /** Bar is complete — shows green bar. */
  complete?: boolean;
}

export const ProgressBar: FC<ProgressBarProps> = ({
  percentage,
  label,
  size = 'md',
  showPercentage = true,
  error,
  complete,
}) => {
  const pct = percentage ?? 0;
  const isIndeterminate = percentage == null && !error && !complete;

  if (error) {
    return (
      <div className={`progress-bar progress-bar--${size}`} data-testid="progress-bar">
        {label && <span className="progress-bar__label">{label}</span>}
        <div className="progress-bar__track progress-bar__track--error" role="progressbar" aria-valuenow={0} aria-valuemin={0} aria-valuemax={100}>
          <div className="progress-bar__fill progress-bar__fill--error" />
        </div>
        <span className="progress-bar__text progress-bar__text--error">{error}</span>
      </div>
    );
  }

  if (complete) {
    return (
      <div className={`progress-bar progress-bar--${size}`} data-testid="progress-bar">
        {label && <span className="progress-bar__label">{label}</span>}
        <div className="progress-bar__track progress-bar__track--complete" role="progressbar" aria-valuenow={100} aria-valuemin={0} aria-valuemax={100}>
          <div className="progress-bar__fill progress-bar__fill--complete" style={{ width: '100%' }} />
        </div>
        {showPercentage && <span className="progress-bar__text">Done</span>}
      </div>
    );
  }

  return (
    <div className={`progress-bar progress-bar--${size}`} data-testid="progress-bar">
      {label && <span className="progress-bar__label">{label}</span>}
      <div
        className={`progress-bar__track ${isIndeterminate ? 'progress-bar__track--indeterminate' : ''}`}
        role="progressbar"
        aria-valuenow={isIndeterminate ? 0 : Math.round(pct)}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={label ?? 'Progress'}
      >
        <div
          className={`progress-bar__fill ${isIndeterminate ? 'progress-bar__fill--indeterminate' : ''}`}
          style={isIndeterminate ? undefined : { width: `${Math.min(pct, 100)}%` }}
        />
      </div>
      {showPercentage && !isIndeterminate && (
        <span className="progress-bar__text">{Math.round(pct)}%</span>
      )}
    </div>
  );
};

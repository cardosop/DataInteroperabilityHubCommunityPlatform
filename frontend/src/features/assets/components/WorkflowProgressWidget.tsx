/**
 * Phase 250.6.C.2 — workflow progress widget.
 *
 * Renders the current state of an asset-creation workflow on the
 * asset detail page during the RUNNING phase, embedded inside the
 * `OnboardingChecklist` so the user sees BOTH:
 *
 *   * "what's still RUNNING" (this widget) AND
 *   * "what's left to do once it completes" (the checklist).
 *
 * Polling + state management lives in `useAssetWorkflowStatus`; this
 * component is purely presentational so it can be unit-tested without
 * a React Query provider (just pass a synthetic data prop).
 *
 * **Skeleton state** (Phase 250.6.C.4): renders during the initial
 * fetch (before the first response arrives). Avoids the "flash of
 * empty content" that a null-render would produce.
 *
 * **ETA**: computed client-side from `started_at` + `progress_percentage`
 * via linear extrapolation. The estimate is intentionally rough — the
 * goal is to give the user a sense of "minutes vs hours", not a
 * scientific prediction. When `progress_percentage` is 0 (workflow
 * has just started or hasn't reported yet), the ETA is suppressed to
 * avoid surfacing a misleading "infinity" value.
 */
import type { AssetWorkflowStatus } from '../../../shared/types/assets';

export interface WorkflowProgressWidgetProps {
  /** When undefined, renders the skeleton state (initial load). */
  data?: AssetWorkflowStatus;
  /** Set true while the first fetch is in flight. */
  isLoading?: boolean;
  /** Set true when the fetch failed. */
  isError?: boolean;
  /** Optional className escape hatch for layout (margin, max-width). */
  className?: string;
}

function computeEtaSeconds(
  startedAtIso: string | null,
  progressPercentage: number,
  now: number = Date.now(),
): number | null {
  if (!startedAtIso) return null;
  if (progressPercentage <= 0) return null;
  if (progressPercentage >= 100) return 0;
  const startedAt = Date.parse(startedAtIso);
  if (Number.isNaN(startedAt)) return null;
  const elapsedMs = now - startedAt;
  if (elapsedMs <= 0) return null;
  // Linear extrapolation: if X% took elapsedMs, (100 - X)% will take
  // ((100 - X) / X) * elapsedMs.
  const remainingMs =
    ((100 - progressPercentage) / progressPercentage) * elapsedMs;
  return Math.round(remainingMs / 1000);
}

function formatEta(etaSeconds: number | null): string | null {
  if (etaSeconds === null) return null;
  if (etaSeconds <= 0) return 'Finishing up…';
  if (etaSeconds < 60) return `~${etaSeconds}s remaining`;
  const minutes = Math.round(etaSeconds / 60);
  if (minutes < 60) return `~${minutes} min remaining`;
  const hours = Math.round(minutes / 60);
  return `~${hours}h remaining`;
}

function humaniseStepName(stepName: string | null): string {
  if (!stepName) return 'Working…';
  // Convert `run_compliance_checks` → `Run compliance checks` for
  // human readers. Keeps the underlying telemetry value intact for
  // dashboards (the FE only humanises the display string).
  return stepName
    .replace(/_/g, ' ')
    .replace(/^\w/, (c) => c.toUpperCase());
}

export function WorkflowProgressWidget({
  data,
  isLoading,
  isError,
  className,
}: WorkflowProgressWidgetProps) {
  // Phase 250.6.C.4 — skeleton state during initial load. Renders a
  // muted progress bar + "Loading…" so the section's visual real
  // estate is committed before the data arrives (avoids layout shift
  // when the response lands).
  if (isLoading && !data) {
    return (
      <section
        className={['workflow-progress-widget', 'is-loading', className]
          .filter(Boolean)
          .join(' ')}
        role="status"
        aria-live="polite"
        aria-label="Loading workflow status"
        data-testid="workflow-progress-widget-skeleton"
      >
        <div className="workflow-progress-widget__skeleton-row">
          <span className="workflow-progress-widget__skeleton-bar" />
          <span className="workflow-progress-widget__skeleton-text">
            Loading workflow status…
          </span>
        </div>
      </section>
    );
  }

  if (isError || !data) {
    return (
      <section
        className={['workflow-progress-widget', 'is-error', className]
          .filter(Boolean)
          .join(' ')}
        role="status"
        aria-live="polite"
        data-testid="workflow-progress-widget-error"
      >
        <p>
          Could not load workflow status. The asset may have been
          created without a tracked workflow, or the polling endpoint
          is temporarily unavailable.
        </p>
      </section>
    );
  }

  const isRunning = data.status === 'RUNNING' || data.status === 'PENDING';
  const isCompleted = data.status === 'COMPLETED';
  const isFailed = data.status === 'FAILED';

  const eta = isRunning
    ? formatEta(computeEtaSeconds(data.started_at, data.progress_percentage))
    : null;

  return (
    <section
      className={[
        'workflow-progress-widget',
        `status-${data.status.toLowerCase()}`,
        className,
      ]
        .filter(Boolean)
        .join(' ')}
      role="status"
      aria-live="polite"
      aria-label={`Workflow ${data.status.toLowerCase()}`}
      data-testid="workflow-progress-widget"
      data-status={data.status}
    >
      <header className="workflow-progress-widget__header">
        <h3>
          {isCompleted && 'Workflow complete'}
          {isFailed && 'Workflow failed'}
          {isRunning && humaniseStepName(data.current_step_name)}
        </h3>
        {eta && (
          <span
            className="workflow-progress-widget__eta"
            data-testid="workflow-progress-widget-eta"
          >
            {eta}
          </span>
        )}
      </header>
      <div
        className="workflow-progress-widget__bar"
        role="progressbar"
        aria-valuenow={data.progress_percentage}
        aria-valuemin={0}
        aria-valuemax={100}
        data-testid="workflow-progress-widget-bar"
      >
        <div
          className="workflow-progress-widget__bar-fill"
          style={{ width: `${data.progress_percentage}%` }}
        />
      </div>
      {isFailed && data.message && (
        <p className="workflow-progress-widget__message">{data.message}</p>
      )}
    </section>
  );
}

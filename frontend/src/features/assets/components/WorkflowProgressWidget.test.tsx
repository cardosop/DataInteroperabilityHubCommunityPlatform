/**
 * Phase 250.6.C TDD pin for `<WorkflowProgressWidget>`.
 *
 * Pure presentational component — tests pass synthetic props
 * (no React Query provider needed). Pins the wire contract:
 *
 *  * Skeleton state during initial load (Phase 250.6.C.4).
 *  * RUNNING shows step + ETA + progress bar.
 *  * COMPLETED shows the "Workflow complete" heading.
 *  * FAILED shows the error message.
 *  * a11y: role=progressbar with aria-valuenow + aria-valuemin/max.
 *  * data-testid + data-status attrs for E2E.
 */
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { WorkflowProgressWidget } from './WorkflowProgressWidget';
import type { AssetWorkflowStatus } from '../../../shared/types/assets';

function makeStatus(
  partial: Partial<AssetWorkflowStatus> = {},
): AssetWorkflowStatus {
  return {
    workflow_instance_id: 'wf-1',
    status: 'RUNNING',
    progress_percentage: 50,
    current_step_name: 'run_compliance_checks',
    asset_id: 'asset-1',
    message: 'Workflow is still running',
    started_at: new Date(Date.now() - 5_000).toISOString(),
    ...partial,
  };
}

describe('WorkflowProgressWidget', () => {
  it('renders the skeleton state when isLoading and no data', () => {
    render(<WorkflowProgressWidget isLoading={true} />);
    expect(
      screen.getByTestId('workflow-progress-widget-skeleton'),
    ).toBeInTheDocument();
    expect(screen.getByText(/Loading workflow status/i)).toBeInTheDocument();
  });

  it('renders the error state when isError and no data', () => {
    render(<WorkflowProgressWidget isError={true} />);
    expect(
      screen.getByTestId('workflow-progress-widget-error'),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Could not load workflow status/i),
    ).toBeInTheDocument();
  });

  it('renders the running state with humanised step + progress + ETA', () => {
    render(
      <WorkflowProgressWidget
        data={makeStatus({
          status: 'RUNNING',
          current_step_name: 'run_compliance_checks',
          progress_percentage: 25,
          // Started 30s ago → ETA ~90s remaining (linear extrapolation)
          started_at: new Date(Date.now() - 30_000).toISOString(),
        })}
      />,
    );
    // Humanised step name in heading.
    expect(screen.getByText('Run compliance checks')).toBeInTheDocument();
    // Progress bar carries the right ARIA + width.
    const bar = screen.getByTestId('workflow-progress-widget-bar');
    expect(bar.getAttribute('aria-valuenow')).toBe('25');
    expect(bar.getAttribute('aria-valuemin')).toBe('0');
    expect(bar.getAttribute('aria-valuemax')).toBe('100');
    // ETA is rendered.
    expect(
      screen.getByTestId('workflow-progress-widget-eta'),
    ).toBeInTheDocument();
  });

  it('suppresses ETA when progress_percentage is 0 (avoid Infinity)', () => {
    render(
      <WorkflowProgressWidget
        data={makeStatus({
          status: 'RUNNING',
          progress_percentage: 0,
          started_at: new Date(Date.now() - 5_000).toISOString(),
        })}
      />,
    );
    expect(screen.queryByTestId('workflow-progress-widget-eta')).toBeNull();
  });

  it('renders the completed state with the success heading', () => {
    render(
      <WorkflowProgressWidget
        data={makeStatus({
          status: 'COMPLETED',
          progress_percentage: 100,
          message: 'Workflow completed successfully',
        })}
      />,
    );
    expect(screen.getByText('Workflow complete')).toBeInTheDocument();
    const widget = screen.getByTestId('workflow-progress-widget');
    expect(widget.getAttribute('data-status')).toBe('COMPLETED');
  });

  it('renders the failed state with the error message', () => {
    render(
      <WorkflowProgressWidget
        data={makeStatus({
          status: 'FAILED',
          progress_percentage: 30,
          message: 'DQ check failed: missing required column',
        })}
      />,
    );
    expect(screen.getByText('Workflow failed')).toBeInTheDocument();
    expect(
      screen.getByText(/DQ check failed: missing required column/i),
    ).toBeInTheDocument();
  });

  it('exposes data-testid + data-status for E2E discoverability', () => {
    render(
      <WorkflowProgressWidget data={makeStatus({ status: 'RUNNING' })} />,
    );
    const widget = screen.getByTestId('workflow-progress-widget');
    expect(widget.getAttribute('data-status')).toBe('RUNNING');
  });
});

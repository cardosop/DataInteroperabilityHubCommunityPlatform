/**
 * JobsPage tests (openspec add-databricks-jobs task 4.5) — the U5 job
 * fleet surface.
 *
 * UI contract pins:
 *  - the mirror list renders each job with its name, schedule presence
 *    and task count,
 *  - "View runs" loads the job's runs (the job-nested endpoint) and
 *    renders each run's reported lifecycle/result state — the Hub
 *    never invents a state,
 *  - a failed load renders the machine-readable CODE in the alert,
 *  - a 403 DATABRICKS_CONTROL_PLANE_DISABLED renders the flag banner,
 *  - the empty state renders with zero rows.
 */
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { DatabricksApiError, listJobRuns, listJobs } from '../services/jobsService';
import { JobsPage } from './JobsPage';

vi.mock('../services/jobsService', () => ({
  DatabricksApiError: class extends Error {
    code?: string;
    constructor(message: string, code?: string) {
      super(message);
      this.code = code;
    }
  },
  listJobs: vi.fn(),
  listJobRuns: vi.fn(),
}));

const mockListJobs = vi.mocked(listJobs);
const mockListRuns = vi.mocked(listJobRuns);

const JOB = {
  job_id: '12345',
  name: 'nightly-etl',
  task_config: [{ task_key: 'ingest' }, { task_key: 'transform' }],
  schedule: { quartz_cron_expression: '0 0 3 * * ?' },
  synced_at: '2026-09-12T19:00:00Z',
};

const RUN = {
  run_id: '67890',
  lifecycle_state: 'TERMINATED',
  result_state: 'SUCCESS',
  duration_ms: 45000,
  error_message: null,
  synced_at: '2026-09-12T19:05:00Z',
};

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/databricks/workspaces/ws-1/jobs']}>
      <Routes>
        <Route path="/databricks/workspaces/:workspaceId/jobs" element={<JobsPage />} />
      </Routes>
    </MemoryRouter>
  );
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe('JobsPage', () => {
  it('renders each job with its name, schedule presence and task count', async () => {
    mockListJobs.mockResolvedValue([
      JOB,
      {
        ...JOB,
        job_id: '23456',
        name: 'ad-hoc',
        schedule: null,
        task_config: [{ task_key: 'single' }],
      },
    ]);
    renderPage();

    await screen.findByText('nightly-etl');
    expect(screen.getByText('ad-hoc')).toBeInTheDocument();
    expect(screen.getAllByText('scheduled').length).toBe(1);
    expect(screen.getAllByText('unscheduled').length).toBe(1);
    expect(screen.getByText('2')).toBeInTheDocument();
    expect(screen.getByText('1')).toBeInTheDocument();
  });

  it('renders each run with its reported states when the job is expanded', async () => {
    mockListJobs.mockResolvedValue([JOB]);
    mockListRuns.mockResolvedValue([
      RUN,
      {
        ...RUN,
        run_id: '88888',
        lifecycle_state: 'RUNNING',
        result_state: null,
        duration_ms: null,
      },
    ]);
    renderPage();

    await screen.findByText('nightly-etl');
    const user = userEvent.setup();
    await user.click(screen.getByText('View runs'));

    await screen.findByText('67890');
    expect(screen.getByText('TERMINATED')).toBeInTheDocument();
    expect(screen.getByText('SUCCESS')).toBeInTheDocument();
    expect(screen.getByText('88888')).toBeInTheDocument();
    expect(screen.getByText('RUNNING')).toBeInTheDocument();
  });

  it('renders the machine-readable code in the failure alert', async () => {
    mockListJobs.mockRejectedValue(
      new DatabricksApiError('jobs list failed', 'DATABRICKS_AUTH_FAILED')
    );
    renderPage();

    await waitFor(() => {
      expect(screen.getByText(/DATABRICKS_AUTH_FAILED/)).toBeInTheDocument();
    });
  });

  it('surfaces the flag-disabled banner with its code', async () => {
    mockListJobs.mockRejectedValue(
      new DatabricksApiError('databricks control plane disabled', 'DATABRICKS_CONTROL_PLANE_DISABLED')
    );
    renderPage();

    await waitFor(() => {
      expect(screen.getByText(/DATABRICKS_CONTROL_PLANE_DISABLED/)).toBeInTheDocument();
    });
  });

  it('renders the empty state with zero rows', async () => {
    mockListJobs.mockResolvedValue([]);
    renderPage();

    await waitFor(() => {
      expect(screen.getByText(/No jobs reported/)).toBeInTheDocument();
    });
  });
});
